#!/usr/bin/env python3
"""Train and evaluate the G7-C sparse strength model without opening hidden evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import statistics
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path

from routellect.evidence_benchmark import CANDIDATE_PARAMETERS, file_sha256
from routellect.profiler import deterministic_profile_v3
from routellect.schemas import AssessorMode
from routellect.sparse_policy import SparseStrengthModel, hashed_features

DIMENSIONS = 4_096
HASH_SEED = "routellect-g7-sparse-v1"
COST_WEIGHT = 0.20
MAXIMUM_COMPUTE = 7_700.0
TUNE_SALT = "routellect-g7-internal-tune-v1|"
CONTROL_SALT = "routellect-g7-content-blind-v1|"
BOOTSTRAP_REPETITIONS = 2_000
BOOTSTRAP_SEED = 314_159


def _read(path: Path) -> list[dict]:
    rows = [json.loads(line) for line in path.read_text().splitlines() if line]
    if not rows:
        raise ValueError(f"{path} contains no rows")
    return rows


def _is_fit(key: str) -> bool:
    digest = hashlib.sha256(f"{TUNE_SALT}{key}".encode()).digest()
    return int.from_bytes(digest[:8], "big") / 2**64 < 0.80


def _targets(row: dict) -> dict[str, float]:
    return {
        model: float(values["correctness_score"])
        for model, values in row["models"].items()
    }


def _compute(row: dict, model: str) -> float:
    return (
        CANDIDATE_PARAMETERS[model]
        * int(row["models"][model]["actual_token_count"])
        / MAXIMUM_COMPUTE
    )


def _train(
    rows: list[dict],
    *,
    learning_rate: float,
    l2: float,
    epochs: int,
    include_profile: bool,
) -> dict[str, object]:
    models = tuple(sorted(CANDIDATE_PARAMETERS))
    means = {
        model: statistics.fmean(_targets(row)[model] for row in rows) for model in models
    }
    weights = {model: defaultdict(float) for model in models}
    accumulators = {model: defaultdict(lambda: 1e-8) for model in models}
    intercepts = dict(means)
    intercept_accumulators = {model: 1e-8 for model in models}
    order = list(range(len(rows)))
    feature_rows = [
        hashed_features(
            str(row["original_prompt"]),
            DIMENSIONS,
            HASH_SEED,
            include_profile=include_profile,
        )
        for row in rows
    ]
    rng = random.Random(2718)
    for _ in range(epochs):
        rng.shuffle(order)
        for row_index in order:
            row = rows[row_index]
            features = feature_rows[row_index]
            targets = _targets(row)
            for model in models:
                model_weights = weights[model]
                prediction = intercepts[model] + sum(
                    model_weights[index] * value for index, value in features.items()
                )
                error = max(-1.0, min(1.0, prediction - targets[model]))
                intercept_accumulators[model] += error * error
                intercepts[model] -= (
                    learning_rate * error / math.sqrt(intercept_accumulators[model])
                )
                model_accumulators = accumulators[model]
                for index, value in features.items():
                    gradient = error * value + l2 * model_weights[index]
                    model_accumulators[index] += gradient * gradient
                    model_weights[index] -= (
                        learning_rate * gradient / math.sqrt(model_accumulators[index])
                    )
    mean_compute = {
        model: statistics.fmean(_compute(row, model) for row in rows) for model in models
    }
    return {
        "schema_version": "routellect-sparse-strength-v1",
        "dimensions": DIMENSIONS,
        "hash_seed": HASH_SEED,
        "include_profile_features": include_profile,
        "cost_weight": COST_WEIGHT,
        "models": list(models),
        "parameter_billions": CANDIDATE_PARAMETERS,
        "intercepts": intercepts,
        "mean_normalized_compute": mean_compute,
        "weights": {
            model: {
                str(index): value
                for index, value in sorted(model_weights.items())
                if abs(value) >= 1e-8
            }
            for model, model_weights in weights.items()
        },
        "training": {
            "algorithm": "deterministic AdaGrad squared-error regression",
            "learning_rate": learning_rate,
            "l2": l2,
            "epochs": epochs,
        },
    }


def _outcomes(rows: list[dict], choices: list[str]) -> list[dict[str, float | str]]:
    result = []
    for row, model in zip(rows, choices, strict=True):
        correctness = float(row["models"][model]["correctness_score"])
        compute = _compute(row, model)
        result.append(
            {
                "key": str(row["key"]),
                "model": model,
                "correctness": correctness,
                "compute": compute,
                "utility": correctness - COST_WEIGHT * compute,
            }
        )
    return result


def _summary(items: list[dict[str, float | str]]) -> dict[str, object]:
    return {
        "rows": len(items),
        "mean_correctness": statistics.fmean(float(item["correctness"]) for item in items),
        "mean_normalized_compute": statistics.fmean(float(item["compute"]) for item in items),
        "mean_utility": statistics.fmean(float(item["utility"]) for item in items),
        "recommendation_share": {
            model: count / len(items)
            for model, count in sorted(Counter(str(item["model"]) for item in items).items())
        },
    }


def _lexical_choices(train: list[dict], rows: list[dict]) -> list[str]:
    totals: dict[str, dict[str, list[float]]] = defaultdict(
        lambda: {model: [0.0, 0.0] for model in CANDIDATE_PARAMETERS}
    )
    global_totals = {model: [0.0, 0.0] for model in CANDIDATE_PARAMETERS}
    for row in train:
        family = deterministic_profile_v3(
            str(row["original_prompt"]), AssessorMode.OFF
        ).task_family
        for model in CANDIDATE_PARAMETERS:
            utility = float(row["models"][model]["correctness_score"]) - COST_WEIGHT * _compute(
                row, model
            )
            totals[family][model][0] += utility
            totals[family][model][1] += 1
            global_totals[model][0] += utility
            global_totals[model][1] += 1
    global_choice = max(
        CANDIDATE_PARAMETERS,
        key=lambda model: (
            global_totals[model][0] / global_totals[model][1],
            -CANDIDATE_PARAMETERS[model],
            model,
        ),
    )
    mapping = {
        family: max(
            CANDIDATE_PARAMETERS,
            key=lambda model: (
                values[model][0] / values[model][1],
                -CANDIDATE_PARAMETERS[model],
                model,
            ),
        )
        for family, values in totals.items()
    }
    return [
        mapping.get(
            deterministic_profile_v3(str(row["original_prompt"]), AssessorMode.OFF).task_family,
            global_choice,
        )
        for row in rows
    ]


def _content_blind_choices(rows: list[dict], shares: dict[str, float]) -> list[str]:
    ordered = sorted(
        range(len(rows)),
        key=lambda index: hashlib.sha256(
            f"{CONTROL_SALT}{rows[index]['key']}".encode()
        ).digest(),
    )
    counts = {model: round(share * len(rows)) for model, share in shares.items()}
    difference = len(rows) - sum(counts.values())
    largest = max(shares, key=lambda model: (shares[model], model))
    counts[largest] += difference
    choices = [largest] * len(rows)
    cursor = 0
    for model in sorted(counts):
        for index in ordered[cursor : cursor + counts[model]]:
            choices[index] = model
        cursor += counts[model]
    return choices


def _paired_intervals(
    sparse: list[dict[str, float | str]],
    fixed: list[dict[str, float | str]],
    content_blind: list[dict[str, float | str]],
    oracle: list[dict[str, float | str]],
) -> dict[str, list[float]]:
    distributions = {
        "quality_retention_vs_fixed": [],
        "compute_reduction_vs_fixed": [],
        "utility_difference_vs_fixed": [],
        "utility_difference_vs_content_blind": [],
        "oracle_regret_reduction_vs_fixed": [],
    }
    size = len(sparse)
    rng = random.Random(BOOTSTRAP_SEED)
    for _ in range(BOOTSTRAP_REPETITIONS):
        indices = [rng.randrange(size) for _ in range(size)]
        sparse_quality = statistics.fmean(
            float(sparse[index]["correctness"]) for index in indices
        )
        fixed_quality = statistics.fmean(
            float(fixed[index]["correctness"]) for index in indices
        )
        sparse_compute = statistics.fmean(float(sparse[index]["compute"]) for index in indices)
        fixed_compute = statistics.fmean(float(fixed[index]["compute"]) for index in indices)
        sparse_utility = statistics.fmean(float(sparse[index]["utility"]) for index in indices)
        fixed_utility = statistics.fmean(float(fixed[index]["utility"]) for index in indices)
        blind_utility = statistics.fmean(
            float(content_blind[index]["utility"]) for index in indices
        )
        oracle_utility = statistics.fmean(float(oracle[index]["utility"]) for index in indices)
        fixed_regret = oracle_utility - fixed_utility
        distributions["quality_retention_vs_fixed"].append(
            sparse_quality / fixed_quality if fixed_quality else 0.0
        )
        distributions["compute_reduction_vs_fixed"].append(
            1 - sparse_compute / fixed_compute if fixed_compute else 0.0
        )
        distributions["utility_difference_vs_fixed"].append(
            sparse_utility - fixed_utility
        )
        distributions["utility_difference_vs_content_blind"].append(
            sparse_utility - blind_utility
        )
        distributions["oracle_regret_reduction_vs_fixed"].append(
            1 - (oracle_utility - sparse_utility) / fixed_regret if fixed_regret else 0.0
        )
    result = {}
    for name, values in distributions.items():
        values.sort()
        result[name] = [
            values[math.floor(0.025 * (len(values) - 1))],
            values[math.ceil(0.975 * (len(values) - 1))],
        ]
    return result


def run(development_path: Path, validation_path: Path, artifact_path: Path) -> dict[str, object]:
    development = _read(development_path)
    fit = [row for row in development if _is_fit(str(row["key"]))]
    tune = [row for row in development if not _is_fit(str(row["key"]))]
    attempts = []
    artifacts: list[dict[str, object]] = []
    for include_profile in (False, True):
        for learning_rate in (0.02, 0.05):
            for l2 in (0.0001, 0.001):
                artifact = _train(
                    fit,
                    learning_rate=learning_rate,
                    l2=l2,
                    epochs=8,
                    include_profile=include_profile,
                )
                predictor = SparseStrengthModel(artifact)
                choices = [
                    predictor.predict(str(row["original_prompt"])).recommended_model
                    for row in tune
                ]
                summary = _summary(_outcomes(tune, choices))
                attempts.append(
                    {
                        "include_profile_features": include_profile,
                        "learning_rate": learning_rate,
                        "l2": l2,
                        **summary,
                    }
                )
                artifacts.append(artifact)
    best_index = max(
        range(len(attempts)),
        key=lambda index: (
            float(attempts[index]["mean_utility"]),
            -float(attempts[index]["mean_normalized_compute"]),
        ),
    )
    chosen = artifacts[best_index]
    training = chosen["training"]
    assert isinstance(training, dict)
    final_artifact = _train(
        development,
        learning_rate=float(training["learning_rate"]),
        l2=float(training["l2"]),
        epochs=int(training["epochs"]),
        include_profile=bool(chosen["include_profile_features"]),
    )
    final_artifact["provenance"] = {
        "development_sha256": file_sha256(development_path),
        "development_rows": len(development),
        "fit_rows": len(fit),
        "tune_rows": len(tune),
        "validation_rows_used_for_training_or_tuning": 0,
        "hidden_rows_used": 0,
        "selected_attempt_index": best_index,
    }
    artifact_path.write_text(json.dumps(final_artifact, indent=2, sort_keys=True) + "\n")

    validation = _read(validation_path)
    final_predictor = SparseStrengthModel(final_artifact)
    sparse_choices = [
        final_predictor.predict(str(row["original_prompt"])).recommended_model
        for row in validation
    ]
    sparse = _outcomes(validation, sparse_choices)
    shares = _summary(sparse)["recommendation_share"]
    assert isinstance(shares, dict)
    lexical = _outcomes(validation, _lexical_choices(development, validation))
    content_blind = _outcomes(
        validation,
        _content_blind_choices(validation, {str(k): float(v) for k, v in shares.items()}),
    )
    fixed = _outcomes(validation, ["Llama-3.1-70B-Instruct"] * len(validation))
    oracle_choices = [
        max(
            CANDIDATE_PARAMETERS,
            key=lambda model: (
                float(row["models"][model]["correctness_score"])
                - COST_WEIGHT * _compute(row, model),
                -CANDIDATE_PARAMETERS[model],
                model,
            ),
        )
        for row in validation
    ]
    oracle = _outcomes(validation, oracle_choices)
    intervals = _paired_intervals(sparse, fixed, content_blind, oracle)
    sparse_summary = _summary(sparse)
    fixed_summary = _summary(fixed)
    oracle_summary = _summary(oracle)
    quality_retention = float(sparse_summary["mean_correctness"]) / float(
        fixed_summary["mean_correctness"]
    )
    compute_reduction = 1 - float(sparse_summary["mean_normalized_compute"]) / float(
        fixed_summary["mean_normalized_compute"]
    )
    fixed_regret = float(oracle_summary["mean_utility"]) - float(
        fixed_summary["mean_utility"]
    )
    sparse_regret = float(oracle_summary["mean_utility"]) - float(
        sparse_summary["mean_utility"]
    )
    result = {
        "protocol": {
            "name": "Routellect G7-C development/validation sparse policy",
            "created_at": datetime.now(UTC).isoformat(),
            "validation_runs": 1,
            "hidden_test_runs": 0,
            "target_model_calls": 0,
            "cost_weight": COST_WEIGHT,
            "bootstrap_repetitions": BOOTSTRAP_REPETITIONS,
            "bootstrap_seed": BOOTSTRAP_SEED,
        },
        "data": {
            "development_sha256": file_sha256(development_path),
            "validation_sha256": file_sha256(validation_path),
            "development_rows": len(development),
            "internal_fit_rows": len(fit),
            "internal_tune_rows": len(tune),
            "validation_rows": len(validation),
        },
        "tuning_attempts": attempts,
        "selected_attempt_index": best_index,
        "artifact": {
            "path": str(artifact_path),
            "sha256": file_sha256(artifact_path),
            "nonzero_coefficients": sum(
                len(values) for values in final_artifact["weights"].values()  # type: ignore[union-attr]
            ),
        },
        "validation": {
            "strongest_fixed": fixed_summary,
            "lexical_v3": _summary(lexical),
            "sparse_v3": sparse_summary,
            "share_matched_content_blind": _summary(content_blind),
            "oracle": oracle_summary,
            "quality_retention_vs_fixed": quality_retention,
            "compute_reduction_vs_fixed": compute_reduction,
            "oracle_regret_reduction_vs_fixed": 1 - sparse_regret / fixed_regret,
            "paired_utility_difference_sparse_vs_fixed": statistics.fmean(
                float(candidate["utility"]) - float(baseline["utility"])
                for candidate, baseline in zip(sparse, fixed, strict=True)
            ),
            "paired_utility_difference_sparse_vs_content_blind": statistics.fmean(
                float(candidate["utility"]) - float(baseline["utility"])
                for candidate, baseline in zip(sparse, content_blind, strict=True)
            ),
            "paired_bootstrap_95ci": intervals,
            "g7_promotion_checks": {
                "quality_retention_lower_95ci_at_least_0_99": (
                    intervals["quality_retention_vs_fixed"][0] >= 0.99
                ),
                "compute_reduction_lower_95ci_at_least_0_40": (
                    intervals["compute_reduction_vs_fixed"][0] >= 0.40
                ),
                "utility_vs_fixed_lower_95ci_above_zero": (
                    intervals["utility_difference_vs_fixed"][0] > 0
                ),
                "utility_vs_content_blind_lower_95ci_above_zero": (
                    intervals["utility_difference_vs_content_blind"][0] > 0
                ),
                "oracle_regret_reduction_at_least_0_20": (
                    1 - sparse_regret / fixed_regret >= 0.20
                ),
            },
        },
        "claim_boundary": (
            "Development/validation-only historical evidence for the frozen R2-Bench pool; "
            "not a production or universal model-quality claim. Hidden evidence remains unopened."
        ),
    }
    return _rounded(result)


def _rounded(value: object) -> object:
    if isinstance(value, float):
        return round(value, 8)
    if isinstance(value, list):
        return [_rounded(item) for item in value]
    if isinstance(value, dict):
        return {key: _rounded(item) for key, item in value.items()}
    return value


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--development", type=Path, default=Path("work/g7-evidence/development.jsonl")
    )
    parser.add_argument(
        "--validation", type=Path, default=Path("work/g7-evidence/validation.jsonl")
    )
    parser.add_argument(
        "--artifact",
        type=Path,
        default=Path("src/routellect/data/g7_sparse_strength.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/phase-7c-validation-results.json"),
    )
    args = parser.parse_args()
    result = run(args.development, args.validation, args.artifact)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result["validation"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
