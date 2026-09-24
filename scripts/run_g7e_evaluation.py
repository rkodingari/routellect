#!/usr/bin/env python3
"""Execute the one-time, outcome-joined G7-E confirmatory evaluation."""

from __future__ import annotations

import argparse
import json
import os
import random
import statistics
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path

from g7e_common import (
    BOOTSTRAP_REPETITIONS,
    BOOTSTRAP_SEED,
    CANDIDATE_PARAMETERS,
    COST_WEIGHT,
    FROZEN_ARTIFACT_SHA256,
    MAXIMUM_COMPUTE,
    STRONG_MODEL,
    file_sha256,
)

MAJOR_SLICE_MINIMUM_ROWS = 100
MAJOR_SLICE_QUALITY_FLOOR = 0.95


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]


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


def _percentile(values: list[float], fraction: float) -> float:
    values.sort()
    return values[round(fraction * (len(values) - 1))]


def _bootstrap(
    candidate: list[dict[str, float | str]],
    fixed: list[dict[str, float | str]],
    content_blind: list[dict[str, float | str]],
    oracle: list[dict[str, float | str]],
    *,
    repetitions: int = BOOTSTRAP_REPETITIONS,
    seed: int = BOOTSTRAP_SEED,
) -> dict[str, list[float]]:
    arrays = {
        "cq": [float(item["correctness"]) for item in candidate],
        "cc": [float(item["compute"]) for item in candidate],
        "cu": [float(item["utility"]) for item in candidate],
        "fq": [float(item["correctness"]) for item in fixed],
        "fc": [float(item["compute"]) for item in fixed],
        "fu": [float(item["utility"]) for item in fixed],
        "bu": [float(item["utility"]) for item in content_blind],
        "ou": [float(item["utility"]) for item in oracle],
    }
    distributions: dict[str, list[float]] = defaultdict(list)
    size = len(candidate)
    rng = random.Random(seed)
    for _ in range(repetitions):
        indices = [rng.randrange(size) for _ in range(size)]
        means = {
            name: sum(values[index] for index in indices) / size
            for name, values in arrays.items()
        }
        fixed_regret = means["ou"] - means["fu"]
        distributions["quality_retention_vs_fixed"].append(
            means["cq"] / means["fq"] if means["fq"] else 0.0
        )
        distributions["compute_reduction_vs_fixed"].append(
            1 - means["cc"] / means["fc"] if means["fc"] else 0.0
        )
        distributions["utility_difference_vs_fixed"].append(
            means["cu"] - means["fu"]
        )
        distributions["utility_difference_vs_content_blind"].append(
            means["cu"] - means["bu"]
        )
        distributions["oracle_regret_reduction_vs_fixed"].append(
            1 - (means["ou"] - means["cu"]) / fixed_regret
            if fixed_regret
            else 0.0
        )
    return {
        name: [_percentile(values, 0.025), _percentile(values, 0.975)]
        for name, values in distributions.items()
    }


def _quality_interval(
    candidate: list[dict[str, float | str]],
    fixed: list[dict[str, float | str]],
    seed: int,
) -> list[float]:
    candidate_values = [float(item["correctness"]) for item in candidate]
    fixed_values = [float(item["correctness"]) for item in fixed]
    size = len(candidate)
    rng = random.Random(seed)
    values = []
    for _ in range(BOOTSTRAP_REPETITIONS):
        indices = [rng.randrange(size) for _ in range(size)]
        candidate_mean = sum(candidate_values[index] for index in indices) / size
        fixed_mean = sum(fixed_values[index] for index in indices) / size
        values.append(candidate_mean / fixed_mean if fixed_mean else 0.0)
    return [_percentile(values, 0.025), _percentile(values, 0.975)]


def _calibration(probabilities: list[float], labels: list[float]) -> dict[str, float]:
    error = 0.0
    for bin_index in range(10):
        lower = bin_index / 10
        upper = (bin_index + 1) / 10
        indices = [
            index
            for index, probability in enumerate(probabilities)
            if lower <= probability < upper or (upper == 1 and probability == 1)
        ]
        if indices:
            predicted = statistics.fmean(probabilities[index] for index in indices)
            observed = statistics.fmean(labels[index] for index in indices)
            error += len(indices) / len(labels) * abs(predicted - observed)
    return {
        "brier_score": statistics.fmean(
            (probability - label) ** 2
            for probability, label in zip(probabilities, labels, strict=True)
        ),
        "expected_calibration_error_10_bin": error,
    }


def _round(value: object) -> object:
    if isinstance(value, float):
        return round(value, 8)
    if isinstance(value, list):
        return [_round(item) for item in value]
    if isinstance(value, dict):
        return {key: _round(item) for key, item in value.items()}
    return value


def evaluate(evidence_dir: Path) -> dict[str, object]:
    recommendation_manifest = json.loads(
        (evidence_dir / "recommendation-manifest.json").read_text()
    )
    outcome_manifest = json.loads((evidence_dir / "outcome-manifest.json").read_text())
    recommendation_path = evidence_dir / str(
        recommendation_manifest["recommendations_file"]
    )
    outcome_path = evidence_dir / str(outcome_manifest["outcomes_file"])
    if file_sha256(recommendation_path) != recommendation_manifest["recommendations_sha256"]:
        raise ValueError("recommendation commitment digest mismatch")
    if file_sha256(outcome_path) != outcome_manifest["outcomes_sha256"]:
        raise ValueError("outcome snapshot digest mismatch")
    if recommendation_manifest["candidate_artifact_sha256"] != FROZEN_ARTIFACT_SHA256:
        raise ValueError("candidate identity differs from the G7-D freeze")
    if outcome_manifest["recommendations_sha256"] != recommendation_manifest[
        "recommendations_sha256"
    ]:
        raise ValueError("outcomes were not acquired against this recommendation commitment")

    recommendations = _read_jsonl(recommendation_path)
    outcomes = _read_jsonl(outcome_path)
    recommendations_by_id = {int(row["prompts_id"]): row for row in recommendations}
    outcomes_by_id = {int(row["prompts_id"]): row for row in outcomes}
    if set(recommendations_by_id) != set(outcomes_by_id):
        raise ValueError("recommendation and outcome row identities differ")
    prompt_ids = sorted(recommendations_by_id)
    aligned_recommendations = [recommendations_by_id[value] for value in prompt_ids]
    aligned_outcomes = [outcomes_by_id[value] for value in prompt_ids]
    for recommendation, outcome in zip(
        aligned_recommendations, aligned_outcomes, strict=True
    ):
        if recommendation["key"] != outcome["key"]:
            raise ValueError("recommendation and outcome keys differ")

    choices = {
        "candidate": [str(row["candidate_model"]) for row in aligned_recommendations],
        "g7c": [str(row["g7c_model"]) for row in aligned_recommendations],
        "lower_tier": [str(row["lower_tier_model"]) for row in aligned_recommendations],
        "fixed": [str(row["fixed_model"]) for row in aligned_recommendations],
        "content_blind": [
            str(row["content_blind_model"]) for row in aligned_recommendations
        ],
        "oracle": [_oracle(row) for row in aligned_outcomes],
    }
    evaluated = {
        name: _outcomes(aligned_outcomes, model_choices)
        for name, model_choices in choices.items()
    }
    summaries = {name: _summary(items) for name, items in evaluated.items()}
    candidate = summaries["candidate"]
    fixed = summaries["fixed"]
    oracle = summaries["oracle"]
    intervals = _bootstrap(
        evaluated["candidate"],
        evaluated["fixed"],
        evaluated["content_blind"],
        evaluated["oracle"],
    )
    fixed_regret = float(oracle["mean_utility"]) - float(fixed["mean_utility"])
    candidate_regret = float(oracle["mean_utility"]) - float(candidate["mean_utility"])
    points = {
        "quality_retention_vs_fixed": float(candidate["mean_correctness"])
        / float(fixed["mean_correctness"]),
        "compute_reduction_vs_fixed": 1
        - float(candidate["mean_normalized_compute"])
        / float(fixed["mean_normalized_compute"]),
        "utility_difference_vs_fixed": float(candidate["mean_utility"])
        - float(fixed["mean_utility"]),
        "utility_difference_vs_content_blind": float(candidate["mean_utility"])
        - float(summaries["content_blind"]["mean_utility"]),
        "oracle_regret_reduction_vs_fixed": 1 - candidate_regret / fixed_regret,
    }

    slice_indices: dict[str, list[int]] = defaultdict(list)
    for index, row in enumerate(aligned_recommendations):
        slice_indices[f"task:{row['task_family']}"].append(index)
        slice_indices[f"difficulty:{row['difficulty']}"].append(index)
    slices = {}
    major_slice_checks = {}
    for slice_number, (name, indices) in enumerate(sorted(slice_indices.items())):
        candidate_slice = [evaluated["candidate"][index] for index in indices]
        fixed_slice = [evaluated["fixed"][index] for index in indices]
        candidate_summary = _summary(candidate_slice)
        fixed_summary = _summary(fixed_slice)
        interval = None
        if len(indices) >= MAJOR_SLICE_MINIMUM_ROWS:
            interval = _quality_interval(
                candidate_slice,
                fixed_slice,
                BOOTSTRAP_SEED + slice_number + 1,
            )
            major_slice_checks[name] = interval[0] >= MAJOR_SLICE_QUALITY_FLOOR
        slices[name] = {
            "rows": len(indices),
            "candidate": candidate_summary,
            "fixed": fixed_summary,
            "quality_retention_vs_fixed": (
                float(candidate_summary["mean_correctness"])
                / float(fixed_summary["mean_correctness"])
                if float(fixed_summary["mean_correctness"])
                else 0.0
            ),
            "quality_retention_95ci": interval,
            "major_slice": len(indices) >= MAJOR_SLICE_MINIMUM_ROWS,
        }

    model_fixed_summaries = {
        model: _summary(_outcomes(aligned_outcomes, [model] * len(aligned_outcomes)))
        for model in CANDIDATE_PARAMETERS
    }
    empirical_best_quality = max(
        model_fixed_summaries,
        key=lambda model: (
            float(model_fixed_summaries[model]["mean_correctness"]),
            -CANDIDATE_PARAMETERS[model],
            model,
        ),
    )
    empirical_best_utility = max(
        model_fixed_summaries,
        key=lambda model: (
            float(model_fixed_summaries[model]["mean_utility"]),
            -CANDIDATE_PARAMETERS[model],
            model,
        ),
    )
    calibration = _calibration(
        [float(row["candidate_strong_probability"]) for row in aligned_recommendations],
        [1.0 if model == STRONG_MODEL else 0.0 for model in choices["oracle"]],
    )

    g7d_validation = json.loads(Path("outputs/phase-7d-validation-results.json").read_text())
    g7d_podman = json.loads(Path("outputs/phase-7d-podman-results.json").read_text())
    inherited_checks = {
        "g7d_freeze_checks": all(g7d_validation["freeze_checks"].values()),
        "g7d_podman_checks": all(g7d_podman["acceptance_checks"].values()),
    }
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
        "all_major_slices_quality_lower_at_least_0_95": all(
            major_slice_checks.values()
        ),
        "all_g7d_freeze_and_podman_checks_remain_valid": all(
            inherited_checks.values()
        ),
        "one_outcome_evaluation_run": True,
    }
    return _round(
        {
            "protocol": {
                "name": "Routellect G7-E one-time untouched exact-pool evaluation",
                "created_at": datetime.now(UTC).isoformat(),
                "confirmatory": True,
                "bootstrap_repetitions": BOOTSTRAP_REPETITIONS,
                "bootstrap_seed": BOOTSTRAP_SEED,
                "evaluation_runs": 1,
                "target_model_calls": 0,
                "existing_hidden_partition_runs": 0,
                "candidate_retrained": False,
                "threshold_reselected": False,
            },
            "inputs": {
                "rows": len(aligned_outcomes),
                "source_commit": recommendation_manifest["source_commit"],
                "candidate_artifact_sha256": recommendation_manifest[
                    "candidate_artifact_sha256"
                ],
                "recommendations_sha256": recommendation_manifest[
                    "recommendations_sha256"
                ],
                "outcomes_sha256": outcome_manifest["outcomes_sha256"],
            },
            "controls": summaries,
            "fixed_model_diagnostics": model_fixed_summaries,
            "empirical_best_single_quality_model": empirical_best_quality,
            "empirical_best_single_utility_model": empirical_best_utility,
            "candidate": {
                "point_metrics": points,
                "paired_bootstrap_95ci": intervals,
                "strong_tier_calibration": calibration,
                "slices": slices,
            },
            "major_slice_checks": major_slice_checks,
            "inherited_checks": inherited_checks,
            "promotion_checks": promotion_checks,
            "promotion_recommended": all(promotion_checks.values()),
            "production_activated": False,
            "claim_boundary": (
                "Untouched exact-pool historical evidence at one R2-Bench revision and token "
                "budget. It does not establish current-provider, latency, price, or broad "
                "source-generalization performance."
            ),
        }
    )


def run_once(evidence_dir: Path, output_path: Path) -> dict[str, object]:
    receipt_path = evidence_dir / "evaluation-run-receipt.json"
    descriptor = {
        "schema_version": "routellect-g7e-run-receipt-v1",
        "started_at": datetime.now(UTC).isoformat(),
        "status": "started",
        "evaluation_runs": 1,
        "result_sha256": None,
    }
    try:
        descriptor_handle = os.fdopen(
            os.open(receipt_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w"
        )
    except FileExistsError as exc:
        raise RuntimeError("G7-E evaluation receipt already exists; rerun is forbidden") from exc
    with descriptor_handle:
        json.dump(descriptor, descriptor_handle, indent=2, sort_keys=True)
        descriptor_handle.write("\n")
    try:
        result = evaluate(evidence_dir)
        output_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
        descriptor.update(
            {
                "completed_at": datetime.now(UTC).isoformat(),
                "status": "complete",
                "result_path": str(output_path),
                "result_sha256": file_sha256(output_path),
                "promotion_recommended": result["promotion_recommended"],
            }
        )
        receipt_path.write_text(json.dumps(descriptor, indent=2, sort_keys=True) + "\n")
        return result
    except Exception:
        descriptor.update(
            {"failed_at": datetime.now(UTC).isoformat(), "status": "failed"}
        )
        receipt_path.write_text(json.dumps(descriptor, indent=2, sort_keys=True) + "\n")
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--evidence-dir", type=Path, default=Path("work/g7e-evidence")
    )
    parser.add_argument(
        "--output", type=Path, default=Path("outputs/phase-7e-results.json")
    )
    args = parser.parse_args()
    result = run_once(args.evidence_dir, args.output)
    print(json.dumps({
        "promotion_checks": result["promotion_checks"],
        "promotion_recommended": result["promotion_recommended"],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
