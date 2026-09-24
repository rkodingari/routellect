"""Reproducible offline evaluation for advisory policies.

This module never invokes a target model. It learns simple segment-level choices from
precomputed public benchmark observations and evaluates those choices on disjoint splits.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
import statistics
import time
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

from routellect.profiler import deterministic_profile
from routellect.schemas import AssessorMode

SPLIT_SALT = "routellect-g5-v1|"
BOOTSTRAP_SEED = 42
SHRINKAGE_STRENGTH = 20
LAMBDAS = (0.0, 0.05, 0.10, 0.20, 0.40)
PRIMARY_LAMBDA = 0.20
STRATEGIES = (
    "always_cheapest",
    "always_best_quality",
    "global_utility",
    "length_segment",
    "task_segment",
    "hybrid_segment",
    "seeded_random",
    "oracle",
)
DEPLOYABLE_STRATEGIES = STRATEGIES[:-1]
CANDIDATE_PARAMETERS = {
    "Qwen3-0.6B": 0.6,
    "Qwen2.5-Math-1.5B-Instruct": 1.5,
    "Qwen2.5-Math-7B-Instruct": 7.0,
    "Llama-3.1-70B-Instruct": 70.0,
}


@dataclass(frozen=True)
class Observation:
    correctness: float
    normalized_compute: float
    actual_token_count: int


@dataclass(frozen=True)
class EvidenceRow:
    key: str
    task_family: str
    length_band: str
    prompt_length: int
    observations: dict[str, Observation]


@dataclass(frozen=True)
class Policy:
    strategy: str
    global_choice: str | None = None
    segment_choices: dict[str, str] | None = None


@dataclass(frozen=True)
class Outcome:
    key: str
    task_family: str
    length_band: str
    model: str
    correctness: float
    normalized_compute: float
    utility: float


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def stable_split(key: str) -> str:
    digest = hashlib.sha256(f"{SPLIT_SALT}{key}".encode()).digest()
    fraction = int.from_bytes(digest[:8], "big") / 2**64
    if fraction < 0.60:
        return "train"
    if fraction < 0.80:
        return "validation"
    return "hidden_test"


def prompt_length_band(length: int) -> str:
    if length < 128:
        return "lt_128"
    if length < 512:
        return "128_511"
    if length < 2_048:
        return "512_2047"
    return "gte_2048"


def _verify_manifest(snapshot_path: Path, manifest_path: Path) -> dict[str, object]:
    manifest = json.loads(manifest_path.read_text())
    expected = manifest.get("snapshot_sha256")
    actual = file_sha256(snapshot_path)
    if expected != actual:
        raise ValueError(f"snapshot digest mismatch: expected {expected}, got {actual}")
    if manifest.get("dataset_revision") is None:
        raise ValueError("manifest does not pin a dataset revision")
    return manifest


def load_evidence(snapshot_path: Path, manifest_path: Path) -> tuple[list[EvidenceRow], dict]:
    manifest = _verify_manifest(snapshot_path, manifest_path)
    raw_rows: list[dict] = []
    maximum_compute = 0.0
    with snapshot_path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            row = json.loads(line)
            models = row.get("models", {})
            if set(models) != set(CANDIDATE_PARAMETERS):
                raise ValueError(f"candidate mismatch on snapshot line {line_number}")
            for model, values in models.items():
                score = float(values["correctness_score"])
                tokens = int(values["actual_token_count"])
                if not 0 <= score <= 1 or tokens < 0:
                    raise ValueError(f"invalid observation on snapshot line {line_number}")
                maximum_compute = max(maximum_compute, CANDIDATE_PARAMETERS[model] * tokens)
            raw_rows.append(row)
    if not raw_rows or maximum_compute <= 0:
        raise ValueError("evidence snapshot contains no usable observations")

    evidence: list[EvidenceRow] = []
    for row in raw_rows:
        prompt = str(row["original_prompt"])
        profile = deterministic_profile(prompt, AssessorMode.OFF)
        observations = {
            model: Observation(
                correctness=float(values["correctness_score"]),
                normalized_compute=(
                    CANDIDATE_PARAMETERS[model] * int(values["actual_token_count"])
                    / maximum_compute
                ),
                actual_token_count=int(values["actual_token_count"]),
            )
            for model, values in row["models"].items()
        }
        evidence.append(
            EvidenceRow(
                key=str(row["key"]),
                task_family=profile.task_family,
                length_band=prompt_length_band(len(prompt)),
                prompt_length=len(prompt),
                observations=observations,
            )
        )
    manifest["normalization"] = {
        "formula": "parameter_billions * actual_token_count / snapshot_maximum",
        "snapshot_maximum": maximum_compute,
        "uses_correctness_labels": False,
    }
    return evidence, manifest


def _means(rows: Iterable[EvidenceRow]) -> dict[str, tuple[float, float, int]]:
    totals = {model: [0.0, 0.0, 0] for model in CANDIDATE_PARAMETERS}
    for row in rows:
        for model, observation in row.observations.items():
            total = totals[model]
            total[0] += observation.correctness
            total[1] += observation.normalized_compute
            total[2] += 1
    return {
        model: (values[0] / values[2], values[1] / values[2], values[2])
        for model, values in totals.items()
        if values[2]
    }


def _best_model(scores: dict[str, float]) -> str:
    return max(
        scores,
        key=lambda model: (
            scores[model],
            -CANDIDATE_PARAMETERS[model],
            model,
        ),
    )


def _segment_key(row: EvidenceRow, strategy: str) -> str:
    if strategy == "length_segment":
        return row.length_band
    if strategy == "task_segment":
        return row.task_family
    if strategy == "hybrid_segment":
        return f"{row.task_family}|{row.length_band}"
    raise ValueError(f"strategy {strategy} does not use segments")


def fit_policy(train_rows: list[EvidenceRow], strategy: str, cost_weight: float) -> Policy:
    if not train_rows:
        raise ValueError("training rows are required")
    global_means = _means(train_rows)
    global_utilities = {
        model: quality - cost_weight * cost
        for model, (quality, cost, _) in global_means.items()
    }
    if strategy == "always_cheapest":
        choice = min(
            global_means,
            key=lambda model: (global_means[model][1], -global_means[model][0], model),
        )
        return Policy(strategy, global_choice=choice)
    if strategy == "always_best_quality":
        choice = _best_model({model: values[0] for model, values in global_means.items()})
        return Policy(strategy, global_choice=choice)
    if strategy == "global_utility":
        return Policy(strategy, global_choice=_best_model(global_utilities))
    if strategy in {"seeded_random", "oracle"}:
        return Policy(strategy)
    if strategy not in {"length_segment", "task_segment", "hybrid_segment"}:
        raise ValueError(f"unknown strategy: {strategy}")

    segment_totals: dict[str, dict[str, list[float]]] = defaultdict(
        lambda: {model: [0.0, 0.0, 0.0] for model in CANDIDATE_PARAMETERS}
    )
    for row in train_rows:
        segment = _segment_key(row, strategy)
        for model, observation in row.observations.items():
            values = segment_totals[segment][model]
            values[0] += observation.correctness
            values[1] += observation.normalized_compute
            values[2] += 1

    segment_choices: dict[str, str] = {}
    for segment, model_totals in segment_totals.items():
        scores: dict[str, float] = {}
        for model, (quality_sum, cost_sum, support) in model_totals.items():
            global_quality, global_cost, _ = global_means[model]
            weight = support / (support + SHRINKAGE_STRENGTH)
            quality = weight * (quality_sum / support) + (1 - weight) * global_quality
            cost = weight * (cost_sum / support) + (1 - weight) * global_cost
            scores[model] = quality - cost_weight * cost
        segment_choices[segment] = _best_model(scores)
    return Policy(
        strategy,
        global_choice=_best_model(global_utilities),
        segment_choices=segment_choices,
    )


def choose_model(policy: Policy, row: EvidenceRow, cost_weight: float) -> str:
    if policy.strategy == "seeded_random":
        candidates = sorted(CANDIDATE_PARAMETERS)
        digest = hashlib.sha256(f"{BOOTSTRAP_SEED}|{row.key}".encode()).digest()
        return candidates[int.from_bytes(digest[:8], "big") % len(candidates)]
    if policy.strategy == "oracle":
        scores = {
            model: observation.correctness - cost_weight * observation.normalized_compute
            for model, observation in row.observations.items()
        }
        return _best_model(scores)
    if policy.segment_choices is not None:
        return policy.segment_choices.get(_segment_key(row, policy.strategy), policy.global_choice)  # type: ignore[arg-type]
    if policy.global_choice is None:
        raise ValueError(f"policy {policy.strategy} has no choice")
    return policy.global_choice


def evaluate_policy(
    policy: Policy, rows: list[EvidenceRow], cost_weight: float
) -> list[Outcome]:
    outcomes = []
    for row in rows:
        model = choose_model(policy, row, cost_weight)
        observation = row.observations[model]
        outcomes.append(
            Outcome(
                key=row.key,
                task_family=row.task_family,
                length_band=row.length_band,
                model=model,
                correctness=observation.correctness,
                normalized_compute=observation.normalized_compute,
                utility=observation.correctness
                - cost_weight * observation.normalized_compute,
            )
        )
    return outcomes


def _mean(values: Iterable[float]) -> float:
    sequence = list(values)
    return statistics.fmean(sequence) if sequence else math.nan


def summarize_outcomes(outcomes: list[Outcome], oracle_mean: float) -> dict[str, object]:
    return {
        "sample_size": len(outcomes),
        "mean_correctness": _mean(item.correctness for item in outcomes),
        "mean_normalized_compute": _mean(item.normalized_compute for item in outcomes),
        "mean_utility": _mean(item.utility for item in outcomes),
        "oracle_regret": oracle_mean - _mean(item.utility for item in outcomes),
        "quality_floor_violation_rate": {
            str(floor): _mean(item.correctness < floor for item in outcomes)
            for floor in (0.4, 0.6, 0.8)
        },
        "recommendation_share": {
            model: count / len(outcomes)
            for model, count in sorted(Counter(item.model for item in outcomes).items())
        },
    }


def slice_summaries(outcomes: list[Outcome]) -> dict[str, dict[str, dict[str, float | int]]]:
    result: dict[str, dict[str, dict[str, float | int]]] = {}
    for attribute in ("task_family", "length_band"):
        groups: dict[str, list[Outcome]] = defaultdict(list)
        for outcome in outcomes:
            groups[str(getattr(outcome, attribute))].append(outcome)
        result[attribute] = {
            name: {
                "sample_size": len(items),
                "mean_correctness": _mean(item.correctness for item in items),
                "mean_normalized_compute": _mean(item.normalized_compute for item in items),
                "mean_utility": _mean(item.utility for item in items),
            }
            for name, items in sorted(groups.items())
        }
    return result


def percentile_interval(values: list[float]) -> list[float]:
    ordered = sorted(values)
    low = ordered[max(0, math.floor(0.025 * (len(ordered) - 1)))]
    high = ordered[min(len(ordered) - 1, math.ceil(0.975 * (len(ordered) - 1)))]
    return [low, high]


def bootstrap_intervals(
    outcomes_by_strategy: dict[str, list[Outcome]],
    *,
    repetitions: int = 2_000,
    seed: int = BOOTSTRAP_SEED,
) -> dict[str, dict[str, list[float]]]:
    """Return query bootstrap intervals using shared resamples across strategies."""
    names = list(outcomes_by_strategy)
    if "global_utility" not in outcomes_by_strategy:
        raise ValueError("global_utility outcomes are required for paired differences")
    sample_size = len(outcomes_by_strategy[names[0]])
    unequal_sizes = any(
        len(items) != sample_size for items in outcomes_by_strategy.values()
    )
    if sample_size == 0 or unequal_sizes:
        raise ValueError("bootstrap strategies must have equal, non-zero sample sizes")

    global_utilities = [item.utility for item in outcomes_by_strategy["global_utility"]]
    dimensions = len(names) * 4
    vectors: list[list[float]] = []
    for index in range(sample_size):
        vector: list[float] = []
        for name in names:
            item = outcomes_by_strategy[name][index]
            vector.extend(
                (
                    item.correctness,
                    item.normalized_compute,
                    item.utility,
                    item.utility - global_utilities[index],
                )
            )
        vectors.append(vector)

    distributions = [[] for _ in range(dimensions)]
    counts = [0] * sample_size
    rng = random.Random(seed)
    for _ in range(repetitions):
        touched: list[int] = []
        for _ in range(sample_size):
            index = rng.randrange(sample_size)
            if counts[index] == 0:
                touched.append(index)
            counts[index] += 1
        sums = [0.0] * dimensions
        for index in touched:
            count = counts[index]
            for dimension, value in enumerate(vectors[index]):
                sums[dimension] += count * value
            counts[index] = 0
        for dimension, total in enumerate(sums):
            distributions[dimension].append(total / sample_size)

    result: dict[str, dict[str, list[float]]] = {}
    metric_names = (
        "mean_correctness_95ci",
        "mean_normalized_compute_95ci",
        "mean_utility_95ci",
        "paired_utility_difference_vs_global_95ci",
    )
    for strategy_index, name in enumerate(names):
        offset = strategy_index * 4
        result[name] = {
            metric: percentile_interval(distributions[offset + metric_index])
            for metric_index, metric in enumerate(metric_names)
        }
    return result


def pareto_front(summaries: dict[str, dict[str, object]]) -> list[str]:
    efficient: list[str] = []
    for name, values in summaries.items():
        quality = float(values["mean_correctness"])
        cost = float(values["mean_normalized_compute"])
        dominated = False
        for other_name, other in summaries.items():
            if other_name == name:
                continue
            other_quality = float(other["mean_correctness"])
            other_cost = float(other["mean_normalized_compute"])
            if (
                other_quality >= quality
                and other_cost <= cost
                and (other_quality > quality or other_cost < cost)
            ):
                dominated = True
                break
        if not dominated:
            efficient.append(name)
    return sorted(efficient)


def routing_overhead(
    policy: Policy,
    rows: list[EvidenceRow],
    cost_weight: float,
    repetitions: int = 10_000,
) -> dict[str, float | int]:
    durations: list[float] = []
    for index in range(repetitions):
        row = rows[index % len(rows)]
        started = time.perf_counter_ns()
        choose_model(policy, row, cost_weight)
        durations.append((time.perf_counter_ns() - started) / 1_000_000)
    durations.sort()
    return {
        "samples": repetitions,
        "p50_ms": durations[round(0.50 * (repetitions - 1))],
        "p95_ms": durations[round(0.95 * (repetitions - 1))],
        "max_ms": durations[-1],
    }


def _slice_regressions(
    candidate: list[Outcome], baseline: list[Outcome], minimum_support: int = 30
) -> list[dict[str, float | int | str]]:
    regressions: list[dict[str, float | int | str]] = []
    for attribute in ("task_family", "length_band"):
        candidate_groups: dict[str, list[Outcome]] = defaultdict(list)
        baseline_groups: dict[str, list[Outcome]] = defaultdict(list)
        for item in candidate:
            candidate_groups[str(getattr(item, attribute))].append(item)
        for item in baseline:
            baseline_groups[str(getattr(item, attribute))].append(item)
        for name, items in candidate_groups.items():
            if len(items) < minimum_support:
                continue
            difference = _mean(item.utility for item in items) - _mean(
                item.utility for item in baseline_groups[name]
            )
            if difference < -0.02:
                regressions.append(
                    {
                        "slice_type": attribute,
                        "slice": name,
                        "sample_size": len(items),
                        "utility_difference": difference,
                    }
                )
    return regressions


def promotion_decision(
    outcomes_by_strategy: dict[str, list[Outcome]], overhead: dict[str, float | int]
) -> dict[str, object]:
    hybrid = outcomes_by_strategy["hybrid_segment"]
    global_baseline = outcomes_by_strategy["global_utility"]
    utility_difference = _mean(item.utility for item in hybrid) - _mean(
        item.utility for item in global_baseline
    )
    regressions = _slice_regressions(hybrid, global_baseline)
    checks = {
        "utility_not_below_global": utility_difference >= 0,
        "no_task_or_length_slice_regression_gt_0_02": not regressions,
        "routing_p95_below_25ms": float(overhead["p95_ms"]) < 25,
        "zero_target_model_calls": True,
    }
    return {
        "eligible_for_separate_offline_policy_review": all(checks.values()),
        "production_changed": False,
        "validation_utility_difference_vs_global": utility_difference,
        "checks": checks,
        "regressions": regressions,
    }


def _rounded(value: object) -> object:
    if isinstance(value, float):
        return round(value, 8)
    if isinstance(value, list):
        return [_rounded(item) for item in value]
    if isinstance(value, dict):
        return {key: _rounded(item) for key, item in value.items()}
    return value


def run_benchmark(
    rows: list[EvidenceRow],
    *,
    bootstrap_repetitions: int = 2_000,
    progress: Callable[[str], None] | None = None,
) -> dict[str, object]:
    notify = progress or (lambda _message: None)
    splits = {
        name: [row for row in rows if stable_split(row.key) == name]
        for name in ("train", "validation", "hidden_test")
    }
    if any(not values for values in splits.values()):
        raise ValueError("stable split produced an empty partition")
    train_rows = splits["train"]
    sensitivity: dict[str, object] = {}
    primary_outcomes: dict[str, dict[str, list[Outcome]]] = {}
    primary_policies: dict[str, Policy] = {}

    for cost_weight in LAMBDAS:
        label = f"{cost_weight:.2f}"
        policies = {
            strategy: fit_policy(train_rows, strategy, cost_weight)
            for strategy in STRATEGIES
        }
        split_results: dict[str, object] = {}
        for split_name in ("validation", "hidden_test"):
            outcomes = {
                strategy: evaluate_policy(policy, splits[split_name], cost_weight)
                for strategy, policy in policies.items()
            }
            oracle_mean = _mean(item.utility for item in outcomes["oracle"])
            summaries = {
                strategy: summarize_outcomes(items, oracle_mean)
                for strategy, items in outcomes.items()
            }
            split_results[split_name] = {
                "strategies": summaries,
                "pareto_front": pareto_front(
                    {name: summaries[name] for name in DEPLOYABLE_STRATEGIES}
                ),
            }
            if cost_weight == PRIMARY_LAMBDA:
                primary_outcomes[split_name] = outcomes
                primary_policies = policies
        sensitivity[label] = split_results

    primary: dict[str, object] = {}
    for split_index, split_name in enumerate(("validation", "hidden_test")):
        notify(f"Bootstrapping {split_name} at λ={PRIMARY_LAMBDA:.2f}...")
        outcomes = primary_outcomes[split_name]
        intervals = bootstrap_intervals(
            outcomes,
            repetitions=bootstrap_repetitions,
            seed=BOOTSTRAP_SEED + split_index,
        )
        oracle_mean = _mean(item.utility for item in outcomes["oracle"])
        summaries: dict[str, object] = {}
        for strategy, items in outcomes.items():
            summary = summarize_outcomes(items, oracle_mean)
            summary.update(intervals[strategy])
            summary["paired_utility_difference_vs_global"] = _mean(
                item.utility - baseline.utility
                for item, baseline in zip(items, outcomes["global_utility"], strict=True)
            )
            summary["slices"] = slice_summaries(items)
            summaries[strategy] = summary
        primary[split_name] = {
            "strategies": summaries,
            "pareto_front": pareto_front(
                {name: summaries[name] for name in DEPLOYABLE_STRATEGIES}  # type: ignore[dict-item]
            ),
        }

    overhead = routing_overhead(
        primary_policies["hybrid_segment"], splits["validation"], PRIMARY_LAMBDA
    )
    promotion = promotion_decision(primary_outcomes["validation"], overhead)
    train_means = _means(train_rows)
    return _rounded(
        {
            "protocol": {
                "name": "Routellect G5 preregistered R2-Bench evaluation",
                "seed": BOOTSTRAP_SEED,
                "split_salt": SPLIT_SALT,
                "lambdas": list(LAMBDAS),
                "primary_lambda": PRIMARY_LAMBDA,
                "bootstrap_repetitions": bootstrap_repetitions,
                "shrinkage_strength": SHRINKAGE_STRENGTH,
                "target_model_calls": 0,
                "hidden_test_runs": 1,
            },
            "data": {
                "total_rows": len(rows),
                "split_counts": {name: len(values) for name, values in splits.items()},
                "task_family_counts": dict(
                    sorted(Counter(row.task_family for row in rows).items())
                ),
                "length_band_counts": dict(
                    sorted(Counter(row.length_band for row in rows).items())
                ),
                "missing_observations": 0,
                "excluded_rows": 0,
                "candidate_parameter_billions": CANDIDATE_PARAMETERS,
                "train_candidate_means": {
                    model: {
                        "correctness": values[0],
                        "normalized_compute": values[1],
                        "sample_size": values[2],
                    }
                    for model, values in train_means.items()
                },
            },
            "sensitivity_point_estimates": sensitivity,
            "primary_confirmatory_results": primary,
            "routing_overhead": overhead,
            "promotion": promotion,
            "claim_boundary": (
                "Offline advisory evidence on one fixed public snapshot; not a universal "
                "best-router claim and not provider price or target-model latency evidence."
            ),
        }
    )
