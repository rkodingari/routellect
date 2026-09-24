#!/usr/bin/env python3
"""Audit and freeze the G7-C2 candidate without training or hidden-test access."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import random
import re
import statistics
import subprocess
import sys
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from routellect.evidence_benchmark import CANDIDATE_PARAMETERS, file_sha256
from routellect.profiler import deterministic_profile_v3
from routellect.schemas import AssessorMode
from routellect.sparse_policy import MultiSourceStrengthModel, SparseStrengthModel

COST_WEIGHT = 0.20
MAXIMUM_COMPUTE = 7_700.0
STRONG_MODEL = "Llama-3.1-70B-Instruct"
BOOTSTRAP_REPETITIONS = 10_000
BOOTSTRAP_SEED = 1_618_033
CONTROL_SALT = "routellect-g7c2-content-blind-v1|"
FROZEN_THRESHOLD = 0.30
SENSITIVITY_THRESHOLDS = (0.25, FROZEN_THRESHOLD, 0.35)


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    rows = [json.loads(line) for line in path.read_text().splitlines() if line]
    if not rows:
        raise ValueError(f"{path} contains no rows")
    return rows


def _compute(row: dict[str, object], model: str) -> float:
    models = row["models"]
    assert isinstance(models, dict)
    values = models[model]
    assert isinstance(values, dict)
    return (
        CANDIDATE_PARAMETERS[model]
        * int(values["actual_token_count"])
        / MAXIMUM_COMPUTE
    )


def _correctness(row: dict[str, object], model: str) -> float:
    models = row["models"]
    assert isinstance(models, dict)
    values = models[model]
    assert isinstance(values, dict)
    return float(values["correctness_score"])


def _utility(row: dict[str, object], model: str) -> float:
    return _correctness(row, model) - COST_WEIGHT * _compute(row, model)


def _oracle(row: dict[str, object]) -> str:
    return max(
        CANDIDATE_PARAMETERS,
        key=lambda model: (
            _utility(row, model),
            -CANDIDATE_PARAMETERS[model],
            model,
        ),
    )


def _lower_tier_choice(model: MultiSourceStrengthModel, prompt: str) -> str:
    prediction = model.lower_tier.predict(prompt)
    candidates = [name for name in prediction.predicted_utility if name != STRONG_MODEL]
    return min(
        candidates,
        key=lambda name: (
            -prediction.predicted_utility[name],
            model.lower_tier.parameter_billions[name],
            name,
        ),
    )


def _outcomes(
    rows: list[dict[str, object]], choices: list[str]
) -> list[dict[str, float | str]]:
    return [
        {
            "model": model,
            "correctness": _correctness(row, model),
            "compute": _compute(row, model),
            "utility": _utility(row, model),
        }
        for row, model in zip(rows, choices, strict=True)
    ]


def _summary(items: list[dict[str, float | str]]) -> dict[str, object]:
    return {
        "rows": len(items),
        "mean_correctness": statistics.fmean(
            float(item["correctness"]) for item in items
        ),
        "mean_normalized_compute": statistics.fmean(
            float(item["compute"]) for item in items
        ),
        "mean_utility": statistics.fmean(float(item["utility"]) for item in items),
        "recommendation_share": {
            model: count / len(items)
            for model, count in sorted(
                Counter(str(item["model"]) for item in items).items()
            )
        },
    }


def _content_blind_choices(
    rows: list[dict[str, object]], shares: dict[str, float]
) -> list[str]:
    ordered = sorted(
        range(len(rows)),
        key=lambda index: hashlib.sha256(
            f"{CONTROL_SALT}{rows[index]['key']}".encode()
        ).digest(),
    )
    counts = {model: round(share * len(rows)) for model, share in shares.items()}
    largest = max(shares, key=lambda model: (shares[model], model))
    counts[largest] += len(rows) - sum(counts.values())
    choices = [largest] * len(rows)
    cursor = 0
    for model in sorted(counts):
        for index in ordered[cursor : cursor + counts[model]]:
            choices[index] = model
        cursor += counts[model]
    return choices


def _percentile(values: list[float], fraction: float) -> float:
    values.sort()
    return values[round(fraction * (len(values) - 1))]


def _paired_intervals(
    candidate: list[dict[str, float | str]],
    fixed: list[dict[str, float | str]],
    content_blind: list[dict[str, float | str]],
    oracle: list[dict[str, float | str]],
) -> dict[str, list[float]]:
    distributions: dict[str, list[float]] = {
        "quality_retention_vs_fixed": [],
        "compute_reduction_vs_fixed": [],
        "utility_difference_vs_fixed": [],
        "utility_difference_vs_content_blind": [],
        "oracle_regret_reduction_vs_fixed": [],
    }
    candidate_quality = [float(item["correctness"]) for item in candidate]
    candidate_compute = [float(item["compute"]) for item in candidate]
    candidate_utility = [float(item["utility"]) for item in candidate]
    fixed_quality = [float(item["correctness"]) for item in fixed]
    fixed_compute = [float(item["compute"]) for item in fixed]
    fixed_utility = [float(item["utility"]) for item in fixed]
    blind_utility = [float(item["utility"]) for item in content_blind]
    oracle_utility = [float(item["utility"]) for item in oracle]
    size = len(candidate)
    rng = random.Random(BOOTSTRAP_SEED)
    for _ in range(BOOTSTRAP_REPETITIONS):
        indices = [rng.randrange(size) for _ in range(size)]
        cq = sum(candidate_quality[index] for index in indices) / size
        cc = sum(candidate_compute[index] for index in indices) / size
        cu = sum(candidate_utility[index] for index in indices) / size
        fq = sum(fixed_quality[index] for index in indices) / size
        fc = sum(fixed_compute[index] for index in indices) / size
        fu = sum(fixed_utility[index] for index in indices) / size
        bu = sum(blind_utility[index] for index in indices) / size
        ou = sum(oracle_utility[index] for index in indices) / size
        fixed_regret = ou - fu
        distributions["quality_retention_vs_fixed"].append(cq / fq if fq else 0.0)
        distributions["compute_reduction_vs_fixed"].append(1 - cc / fc if fc else 0.0)
        distributions["utility_difference_vs_fixed"].append(cu - fu)
        distributions["utility_difference_vs_content_blind"].append(cu - bu)
        distributions["oracle_regret_reduction_vs_fixed"].append(
            1 - (ou - cu) / fixed_regret if fixed_regret else 0.0
        )
    return {
        name: [_percentile(values, 0.025), _percentile(values, 0.975)]
        for name, values in distributions.items()
    }


def _metric_points(
    candidate: dict[str, object], fixed: dict[str, object], oracle: dict[str, object]
) -> dict[str, float]:
    fixed_regret = float(oracle["mean_utility"]) - float(fixed["mean_utility"])
    candidate_regret = float(oracle["mean_utility"]) - float(candidate["mean_utility"])
    return {
        "quality_retention_vs_fixed": float(candidate["mean_correctness"])
        / float(fixed["mean_correctness"]),
        "compute_reduction_vs_fixed": 1
        - float(candidate["mean_normalized_compute"])
        / float(fixed["mean_normalized_compute"]),
        "utility_difference_vs_fixed": float(candidate["mean_utility"])
        - float(fixed["mean_utility"]),
        "oracle_regret_reduction_vs_fixed": 1 - candidate_regret / fixed_regret,
    }


def _calibration(
    probabilities: list[float], labels: list[float]
) -> dict[str, float | list[dict[str, float | int]]]:
    bins: list[dict[str, float | int]] = []
    calibration_error = 0.0
    for lower_index in range(10):
        lower = lower_index / 10
        upper = (lower_index + 1) / 10
        indices = [
            index
            for index, probability in enumerate(probabilities)
            if lower <= probability < upper or (upper == 1 and probability == 1)
        ]
        if not indices:
            continue
        mean_probability = statistics.fmean(probabilities[index] for index in indices)
        observed_rate = statistics.fmean(labels[index] for index in indices)
        calibration_error += len(indices) / len(labels) * abs(
            mean_probability - observed_rate
        )
        bins.append(
            {
                "lower": lower,
                "upper": upper,
                "rows": len(indices),
                "mean_probability": mean_probability,
                "observed_strong_oracle_rate": observed_rate,
            }
        )
    return {
        "brier_score": statistics.fmean(
            (probability - label) ** 2
            for probability, label in zip(probabilities, labels, strict=True)
        ),
        "expected_calibration_error_10_bin": calibration_error,
        "bins": bins,
    }


def _fullwidth_ascii(text: str) -> str:
    return "".join(
        chr(ord(character) + 0xFEE0)
        if "!" <= character <= "~"
        else character
        for character in text
    )


def _normalization_stability(
    model: MultiSourceStrengthModel, prompts: list[str]
) -> dict[str, object]:
    variants = {
        "case": str.upper,
        "nfkc_equivalent": _fullwidth_ascii,
        "outer_whitespace": lambda text: f"\n \t{text}\r\n ",
        "line_endings": lambda text: text.replace("\n", "\r\n"),
        "collapsed_whitespace": lambda text: re.sub(r"\s+", " ", text).strip(),
    }
    baseline = [model.choose(prompt) for prompt in prompts]
    rates = {}
    for name, transform in variants.items():
        matching = sum(
            model.choose(transform(prompt)) == expected
            for prompt, expected in zip(prompts, baseline, strict=True)
        )
        rates[name] = matching / len(prompts)
    return {
        "rows": len(prompts),
        "per_variant_choice_stability": rates,
        "minimum_choice_stability": min(rates.values()),
    }


def _cross_process_determinism(
    artifact_path: Path, prompts: list[str]
) -> dict[str, object]:
    code = (
        "import json,sys;from pathlib import Path;"
        "from routellect.sparse_policy import MultiSourceStrengthModel;"
        "m=MultiSourceStrengthModel(json.loads(Path(sys.argv[1]).read_text()));"
        "p=json.load(sys.stdin);json.dump([m.choose(x) for x in p],sys.stdout)"
    )
    digests = []
    for seed in ("1", "7", "31337"):
        environment = {**os.environ, "PYTHONHASHSEED": seed}
        completed = subprocess.run(  # noqa: S603
            [sys.executable, "-c", code, str(artifact_path)],
            check=True,
            text=True,
            input=json.dumps(prompts),
            capture_output=True,
            env=environment,
        )
        digests.append(hashlib.sha256(completed.stdout.encode()).hexdigest())
    return {
        "processes": len(digests),
        "python_hash_seeds": 3,
        "distinct_decision_digests": len(set(digests)),
        "byte_stable": len(set(digests)) == 1,
        "decision_digest_sha256": digests[0],
    }


def _slices(
    rows: list[dict[str, object]], candidate_choices: list[str]
) -> dict[str, object]:
    groups: dict[str, list[int]] = {}
    for index, row in enumerate(rows):
        profile = deterministic_profile_v3(
            str(row["original_prompt"]), AssessorMode.OFF
        )
        groups.setdefault(f"task:{profile.task_family}", []).append(index)
        groups.setdefault(f"difficulty:{profile.difficulty}", []).append(index)
    result = {}
    for name, indices in sorted(groups.items()):
        selected_rows = [rows[index] for index in indices]
        candidate = _summary(
            _outcomes(selected_rows, [candidate_choices[index] for index in indices])
        )
        fixed = _summary(_outcomes(selected_rows, [STRONG_MODEL] * len(indices)))
        result[name] = {
            "candidate": candidate,
            "fixed": fixed,
            "quality_retention_vs_fixed": (
                float(candidate["mean_correctness"]) / float(fixed["mean_correctness"])
                if float(fixed["mean_correctness"])
                else 0.0
            ),
            "compute_reduction_vs_fixed": 1
            - float(candidate["mean_normalized_compute"])
            / float(fixed["mean_normalized_compute"]),
        }
    return result


def _round(value: object) -> object:
    if isinstance(value, float):
        return round(value, 8)
    if isinstance(value, list):
        return [_round(item) for item in value]
    if isinstance(value, dict):
        return {key: _round(item) for key, item in value.items()}
    return value


def run(
    validation_path: Path,
    artifact_path: Path,
    prior_artifact_path: Path,
) -> dict[str, object]:
    rows = _read_jsonl(validation_path)
    artifact = json.loads(artifact_path.read_text())
    if float(artifact["strong_threshold"]) != FROZEN_THRESHOLD:
        raise ValueError("candidate threshold does not match the frozen G7-D protocol")
    provenance = artifact["provenance"]
    assert isinstance(provenance, dict)
    if int(provenance["hidden_rows_used"]) != 0:
        raise ValueError("candidate provenance reports hidden data use")

    model = MultiSourceStrengthModel(artifact)
    prior = SparseStrengthModel(json.loads(prior_artifact_path.read_text()))
    prompts = [str(row["original_prompt"]) for row in rows]
    candidate_choices = [model.choose(prompt) for prompt in prompts]
    prior_choices = [prior.predict(prompt).recommended_model for prompt in prompts]
    lower_choices = [_lower_tier_choice(model, prompt) for prompt in prompts]
    fixed_choices = [STRONG_MODEL] * len(rows)
    oracle_choices = [_oracle(row) for row in rows]

    candidate = _outcomes(rows, candidate_choices)
    fixed = _outcomes(rows, fixed_choices)
    oracle = _outcomes(rows, oracle_choices)
    candidate_summary = _summary(candidate)
    fixed_summary = _summary(fixed)
    oracle_summary = _summary(oracle)
    shares = {
        str(name): float(share)
        for name, share in candidate_summary["recommendation_share"].items()  # type: ignore[union-attr]
    }
    content_blind = _outcomes(rows, _content_blind_choices(rows, shares))
    content_blind_summary = _summary(content_blind)
    intervals = _paired_intervals(candidate, fixed, content_blind, oracle)
    points = _metric_points(candidate_summary, fixed_summary, oracle_summary)
    points["utility_difference_vs_content_blind"] = float(
        candidate_summary["mean_utility"]
    ) - float(content_blind_summary["mean_utility"])

    threshold_sensitivity = []
    for threshold in SENSITIVITY_THRESHOLDS:
        changed = copy.deepcopy(artifact)
        changed["strong_threshold"] = threshold
        sensitivity_model = MultiSourceStrengthModel(changed)
        choices = [sensitivity_model.choose(prompt) for prompt in prompts]
        summary = _summary(_outcomes(rows, choices))
        threshold_sensitivity.append(
            {
                "threshold": threshold,
                "selected_for_candidate": threshold == FROZEN_THRESHOLD,
                **summary,
            }
        )

    probabilities = [model.strong_probability(prompt) for prompt in prompts]
    labels = [1.0 if choice == STRONG_MODEL else 0.0 for choice in oracle_choices]
    stability = _normalization_stability(model, prompts)
    cross_process = _cross_process_determinism(artifact_path, prompts[:100])

    durations = []
    for index in range(2_000):
        started = time.perf_counter_ns()
        model.choose(prompts[index % len(prompts)])
        durations.append((time.perf_counter_ns() - started) / 1_000_000)

    promotion_checks = {
        "quality_retention_lower_at_least_0_99": intervals[
            "quality_retention_vs_fixed"
        ][0]
        >= 0.99,
        "compute_reduction_lower_at_least_0_40": intervals[
            "compute_reduction_vs_fixed"
        ][0]
        >= 0.40,
        "utility_vs_fixed_lower_above_zero": intervals[
            "utility_difference_vs_fixed"
        ][0]
        > 0,
        "utility_vs_content_blind_lower_above_zero": intervals[
            "utility_difference_vs_content_blind"
        ][0]
        > 0,
        "oracle_regret_reduction_at_least_0_20": points[
            "oracle_regret_reduction_vs_fixed"
        ]
        >= 0.20,
        "untouched_confirmatory_evidence": False,
    }
    freeze_checks = {
        "artifact_threshold_is_0_30": float(artifact["strong_threshold"])
        == FROZEN_THRESHOLD,
        "hidden_rows_used_equals_zero": int(provenance["hidden_rows_used"]) == 0,
        "normalization_choice_stability_at_least_0_99": float(
            stability["minimum_choice_stability"]
        )
        >= 0.99,
        "cross_process_decisions_are_byte_stable": bool(cross_process["byte_stable"]),
        "uncached_p95_below_10ms": _percentile(durations.copy(), 0.95) < 10,
        "zero_target_model_calls": True,
        "zero_hidden_test_runs": True,
        "zero_raw_prompts_in_report": True,
    }

    return _round(
        {
            "protocol": {
                "name": "Routellect G7-D frozen-candidate visible validation audit",
                "created_at": datetime.now(UTC).isoformat(),
                "confirmatory": False,
                "candidate_retrained": False,
                "threshold_reselected": False,
                "bootstrap_repetitions": BOOTSTRAP_REPETITIONS,
                "bootstrap_seed": BOOTSTRAP_SEED,
                "hidden_test_runs": 0,
                "target_model_calls": 0,
                "raw_prompts_persisted": 0,
            },
            "inputs": {
                "visible_validation_rows": len(rows),
                "validation_sha256": file_sha256(validation_path),
                "candidate_artifact_sha256": file_sha256(artifact_path),
                "prior_artifact_sha256": file_sha256(prior_artifact_path),
                "strong_threshold": float(artifact["strong_threshold"]),
                "candidate_pool": sorted(CANDIDATE_PARAMETERS),
                "cost_weight": COST_WEIGHT,
            },
            "controls": {
                "fixed_best_single": fixed_summary,
                "g7c_single_source": _summary(_outcomes(rows, prior_choices)),
                "lower_tier_only": _summary(_outcomes(rows, lower_choices)),
                "share_matched_content_blind": content_blind_summary,
                "oracle": oracle_summary,
            },
            "candidate": {
                "summary": candidate_summary,
                "point_metrics": points,
                "paired_bootstrap_95ci": intervals,
                "strong_tier_calibration": _calibration(probabilities, labels),
                "threshold_sensitivity_not_used_for_selection": threshold_sensitivity,
                "visible_slices": _slices(rows, candidate_choices),
            },
            "robustness": {
                "normalization": stability,
                "cross_process_determinism": cross_process,
            },
            "runtime": {
                "samples": len(durations),
                "p50_ms": _percentile(durations.copy(), 0.50),
                "p95_ms": _percentile(durations.copy(), 0.95),
                "p99_ms": _percentile(durations.copy(), 0.99),
                "max_ms": max(durations),
            },
            "freeze_checks": freeze_checks,
            "ready_to_freeze": all(freeze_checks.values()),
            "promotion_checks": promotion_checks,
            "promotion_eligible": False,
            "claim_boundary": (
                "G7-D reuses already inspected validation evidence for robustness and freeze "
                "checks only. It is not confirmatory accuracy evidence and cannot promote v3."
            ),
        }
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--validation",
        type=Path,
        default=Path("work/g7-evidence/validation.jsonl"),
    )
    parser.add_argument(
        "--artifact",
        type=Path,
        default=Path("src/routellect/data/g7c2_multisource_strength.json"),
    )
    parser.add_argument(
        "--prior-artifact",
        type=Path,
        default=Path("src/routellect/data/g7_sparse_strength.json"),
    )
    parser.add_argument(
        "--output", type=Path, default=Path("outputs/phase-7d-validation-results.json")
    )
    args = parser.parse_args()
    result = run(args.validation, args.artifact, args.prior_artifact)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "ready_to_freeze": result["ready_to_freeze"],
        "promotion_checks": result["promotion_checks"],
        "runtime": result["runtime"],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
