#!/usr/bin/env python3
"""Train and audit the bounded G7-C2 multi-source prompt-strength candidate."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import statistics
import time
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path

from train_g7_sparse_policy import _compute, _is_fit, _train

from routellect.evidence_benchmark import CANDIDATE_PARAMETERS, file_sha256
from routellect.sparse_policy import (
    MultiSourceStrengthModel,
    SparseStrengthModel,
    hashed_features,
)

DIMENSIONS = 8_192
HASH_SEED = "routellect-g7c2-strong-v2"
LEARNING_RATE = 0.05
L2 = 0.001
EPOCHS = 5
COST_WEIGHT = 0.20
STRONG_MODEL = "Llama-3.1-70B-Instruct"
THRESHOLDS = tuple(value / 100 for value in range(20, 66, 5))
BOOTSTRAP_REPETITIONS = 2_000
BOOTSTRAP_SEED = 271_828
CONTROL_SALT = "routellect-g7c2-content-blind-v1|"
_TRAINING_FEATURE_CACHE: dict[str, dict[int, float]] = {}


def _read(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        rows = [json.loads(line) for line in handle if line.strip()]
    if not rows:
        raise ValueError(f"{path} contains no rows")
    return rows


def _oracle(row: dict) -> str:
    return max(
        CANDIDATE_PARAMETERS,
        key=lambda model: (
            float(row["models"][model]["correctness_score"])
            - COST_WEIGHT * _compute(row, model),
            -CANDIDATE_PARAMETERS[model],
            model,
        ),
    )


def _train_strong_head(
    r2_rows: list[dict], auxiliary: list[dict]
) -> tuple[dict[int, float], float]:
    examples: list[tuple[str, float, float]] = [
        (
            str(row["original_prompt"]),
            1.0 if _oracle(row) == STRONG_MODEL else 0.0,
            1.0,
        )
        for row in r2_rows
    ]
    positives = sum(row["label"] == "strong" for row in auxiliary)
    negatives = len(auxiliary) - positives
    source_weight = 0.5 * len(r2_rows) / len(auxiliary)
    for row in auxiliary:
        target = 1.0 if row["label"] == "strong" else 0.0
        class_weight = (
            len(auxiliary) / (2 * positives)
            if target
            else len(auxiliary) / (2 * negatives)
        )
        examples.append((str(row["prompt"]), target, source_weight * class_weight))

    feature_rows = []
    for text, _, _ in examples:
        features = _TRAINING_FEATURE_CACHE.get(text)
        if features is None:
            features = hashed_features(
                text, DIMENSIONS, HASH_SEED, include_profile=True
            )
            _TRAINING_FEATURE_CACHE[text] = features
        feature_rows.append(features)

    weights: dict[int, float] = defaultdict(float)
    accumulators: dict[int, float] = defaultdict(lambda: 1e-8)
    intercept = 0.0
    intercept_accumulator = 1e-8
    order = list(range(len(examples)))
    rng = random.Random(41)
    for _ in range(EPOCHS):
        rng.shuffle(order)
        for index in order:
            _, target, sample_weight = examples[index]
            features = feature_rows[index]
            value = intercept + sum(
                weights[feature] * amount for feature, amount in features.items()
            )
            probability = 1 / (1 + math.exp(-max(-20.0, min(20.0, value))))
            error = (probability - target) * sample_weight
            intercept_accumulator += error * error
            intercept -= LEARNING_RATE * error / math.sqrt(intercept_accumulator)
            for feature, amount in features.items():
                gradient = error * amount + L2 * weights[feature]
                accumulators[feature] += gradient * gradient
                weights[feature] -= (
                    LEARNING_RATE * gradient / math.sqrt(accumulators[feature])
                )
    return dict(weights), intercept


def _artifact(
    weights: dict[int, float],
    intercept: float,
    threshold: float,
    lower_tier: dict[str, object],
    provenance: dict[str, object],
) -> dict[str, object]:
    return {
        "schema_version": "routellect-multisource-strength-v1",
        "dimensions": DIMENSIONS,
        "hash_seed": HASH_SEED,
        "strong_model": STRONG_MODEL,
        "strong_threshold": threshold,
        "strong_intercept": intercept,
        "strong_weights": {
            str(index): value
            for index, value in sorted(weights.items())
            if abs(value) >= 1e-8
        },
        "lower_tier_model": lower_tier,
        "training": {
            "algorithm": "weighted multi-source binary AdaGrad plus G7 sparse regression",
            "learning_rate": LEARNING_RATE,
            "l2": L2,
            "epochs": EPOCHS,
            "threshold_candidates": list(THRESHOLDS),
            "cost_weight": COST_WEIGHT,
        },
        "provenance": provenance,
    }


def _outcomes(rows: list[dict], choices: list[str]) -> list[dict[str, float | str]]:
    outcomes = []
    for row, model in zip(rows, choices, strict=True):
        correctness = float(row["models"][model]["correctness_score"])
        compute = _compute(row, model)
        outcomes.append(
            {
                "key": str(row["key"]),
                "model": model,
                "correctness": correctness,
                "compute": compute,
                "utility": correctness - COST_WEIGHT * compute,
            }
        )
    return outcomes


def _summary(outcomes: list[dict[str, float | str]]) -> dict[str, object]:
    return {
        "rows": len(outcomes),
        "mean_correctness": statistics.fmean(
            float(item["correctness"]) for item in outcomes
        ),
        "mean_normalized_compute": statistics.fmean(
            float(item["compute"]) for item in outcomes
        ),
        "mean_utility": statistics.fmean(float(item["utility"]) for item in outcomes),
        "recommendation_share": {
            model: count / len(outcomes)
            for model, count in sorted(
                Counter(str(item["model"]) for item in outcomes).items()
            )
        },
    }


def _content_blind_choices(rows: list[dict], shares: dict[str, float]) -> list[str]:
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


def _select_threshold(
    tune_rows: list[dict],
    weights: dict[int, float],
    intercept: float,
    lower_tier: dict[str, object],
    provenance: dict[str, object],
) -> tuple[float, list[dict[str, object]]]:
    attempts = []
    for threshold in THRESHOLDS:
        model = MultiSourceStrengthModel(
            _artifact(weights, intercept, threshold, lower_tier, provenance)
        )
        summary = _summary(
            _outcomes(
                tune_rows,
                [model.choose(str(row["original_prompt"])) for row in tune_rows],
            )
        )
        attempts.append({"threshold": threshold, **summary})
    selected = max(
        attempts,
        key=lambda item: (
            float(item["mean_utility"]),
            float(item["mean_correctness"]),
            -float(item["mean_normalized_compute"]),
        ),
    )
    return float(selected["threshold"]), attempts


def _intervals(
    candidate: list[dict[str, float | str]],
    prior: list[dict[str, float | str]],
    fixed: list[dict[str, float | str]],
    content_blind: list[dict[str, float | str]],
) -> dict[str, list[float]]:
    distributions = {
        "utility_vs_prior": [],
        "utility_vs_fixed": [],
        "utility_vs_content_blind": [],
        "quality_retention": [],
        "compute_reduction": [],
    }
    rng = random.Random(BOOTSTRAP_SEED)
    size = len(candidate)
    for _ in range(BOOTSTRAP_REPETITIONS):
        indices = [rng.randrange(size) for _ in range(size)]
        candidate_quality = statistics.fmean(
            float(candidate[index]["correctness"]) for index in indices
        )
        fixed_quality = statistics.fmean(
            float(fixed[index]["correctness"]) for index in indices
        )
        candidate_compute = statistics.fmean(
            float(candidate[index]["compute"]) for index in indices
        )
        fixed_compute = statistics.fmean(
            float(fixed[index]["compute"]) for index in indices
        )
        distributions["utility_vs_prior"].append(
            statistics.fmean(
                float(candidate[index]["utility"]) - float(prior[index]["utility"])
                for index in indices
            )
        )
        distributions["utility_vs_fixed"].append(
            statistics.fmean(
                float(candidate[index]["utility"]) - float(fixed[index]["utility"])
                for index in indices
            )
        )
        distributions["utility_vs_content_blind"].append(
            statistics.fmean(
                float(candidate[index]["utility"])
                - float(content_blind[index]["utility"])
                for index in indices
            )
        )
        distributions["quality_retention"].append(candidate_quality / fixed_quality)
        distributions["compute_reduction"].append(1 - candidate_compute / fixed_compute)
    result = {}
    for name, values in distributions.items():
        values.sort()
        result[name] = [
            values[math.floor(0.025 * (len(values) - 1))],
            values[math.ceil(0.975 * (len(values) - 1))],
        ]
    return result


def _crossfit_fold(key: str, folds: int) -> int:
    digest = hashlib.sha256(f"routellect-g7c2-crossfit-v1|{key}".encode()).digest()
    return int.from_bytes(digest[:8], "big") % folds


def _crossfit(
    visible_rows: list[dict],
    auxiliary: list[dict],
    threshold: float,
    provenance: dict[str, object],
    folds: int = 3,
) -> dict[str, object]:
    outcomes: list[dict[str, float | str]] = []
    fold_counts = []
    for fold in range(folds):
        train_rows = [
            row
            for row in visible_rows
            if _crossfit_fold(str(row["key"]), folds) != fold
        ]
        test_rows = [
            row
            for row in visible_rows
            if _crossfit_fold(str(row["key"]), folds) == fold
        ]
        lower = _train(
            train_rows,
            learning_rate=0.02,
            l2=0.001,
            epochs=8,
            include_profile=True,
        )
        weights, intercept = _train_strong_head(train_rows, auxiliary)
        model = MultiSourceStrengthModel(
            _artifact(weights, intercept, threshold, lower, provenance)
        )
        outcomes.extend(
            _outcomes(
                test_rows,
                [model.choose(str(row["original_prompt"])) for row in test_rows],
            )
        )
        fold_counts.append(
            {"fold": fold, "training_rows": len(train_rows), "test_rows": len(test_rows)}
        )
    fixed = _outcomes(
        [{**row} for row in visible_rows],
        [STRONG_MODEL] * len(visible_rows),
    )
    candidate_summary = _summary(outcomes)
    fixed_summary = _summary(fixed)
    shares = {
        str(model): float(share)
        for model, share in candidate_summary["recommendation_share"].items()  # type: ignore[union-attr]
    }
    ordered_rows = sorted(visible_rows, key=lambda row: str(row["key"]))
    ordered_outcomes = sorted(outcomes, key=lambda item: str(item["key"]))
    fixed = _outcomes(ordered_rows, [STRONG_MODEL] * len(ordered_rows))
    content_blind = _outcomes(
        ordered_rows, _content_blind_choices(ordered_rows, shares)
    )
    intervals = _intervals(
        ordered_outcomes, ordered_outcomes, fixed, content_blind
    )
    return {
        "folds": folds,
        "fold_counts": fold_counts,
        "threshold": threshold,
        "threshold_note": (
            "Threshold was selected on the original internal development tune split before "
            "cross-fitting; this is exploratory, not nested confirmatory cross-validation."
        ),
        "candidate": candidate_summary,
        "fixed_v2": fixed_summary,
        "share_matched_content_blind": _summary(content_blind),
        "paired_bootstrap_95ci": {
            "quality_retention": intervals["quality_retention"],
            "compute_reduction": intervals["compute_reduction"],
            "utility_vs_fixed": intervals["utility_vs_fixed"],
            "utility_vs_content_blind": intervals["utility_vs_content_blind"],
        },
        "point_quality_retention_vs_fixed": float(candidate_summary["mean_correctness"])
        / float(fixed_summary["mean_correctness"]),
        "point_compute_reduction_vs_fixed": 1
        - float(candidate_summary["mean_normalized_compute"])
        / float(fixed_summary["mean_normalized_compute"]),
        "point_utility_difference_vs_fixed": float(candidate_summary["mean_utility"])
        - float(fixed_summary["mean_utility"]),
    }


def run(
    development_path: Path,
    validation_path: Path,
    auxiliary_path: Path,
    auxiliary_manifest_path: Path,
    prior_artifact_path: Path,
    artifact_path: Path,
) -> dict[str, object]:
    development = _read(development_path)
    validation = _read(validation_path)
    auxiliary = _read(auxiliary_path)
    auxiliary_manifest = json.loads(auxiliary_manifest_path.read_text())
    if file_sha256(auxiliary_path) != auxiliary_manifest["evidence_sha256"]:
        raise ValueError("auxiliary evidence digest mismatch")
    if auxiliary_manifest["raw_model_responses_persisted"] is not False:
        raise ValueError("raw response persistence is forbidden")

    fit = [row for row in development if _is_fit(str(row["key"]))]
    tune = [row for row in development if not _is_fit(str(row["key"]))]
    fit_lower = _train(
        fit,
        learning_rate=0.02,
        l2=0.001,
        epochs=8,
        include_profile=True,
    )
    fit_weights, fit_intercept = _train_strong_head(fit, auxiliary)
    base_provenance = {
        "r2_development_sha256": file_sha256(development_path),
        "routellm_auxiliary_sha256": file_sha256(auxiliary_path),
        "routellm_revision": auxiliary_manifest["dataset_revision"],
        "routellm_license": auxiliary_manifest["declared_license"],
        "validation_rows_used_for_training_or_tuning": 0,
        "hidden_rows_used": 0,
        "raw_model_responses_used": 0,
    }
    threshold, threshold_attempts = _select_threshold(
        tune, fit_weights, fit_intercept, fit_lower, base_provenance
    )

    final_lower = _train(
        development,
        learning_rate=0.02,
        l2=0.001,
        epochs=8,
        include_profile=True,
    )
    final_weights, final_intercept = _train_strong_head(development, auxiliary)
    final_provenance = {
        **base_provenance,
        "r2_fit_rows": len(fit),
        "r2_tune_rows": len(tune),
        "r2_final_training_rows": len(development),
        "routellm_auxiliary_rows": len(auxiliary),
        "selected_threshold": threshold,
    }
    artifact = _artifact(
        final_weights, final_intercept, threshold, final_lower, final_provenance
    )
    artifact_path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n")

    candidate_model = MultiSourceStrengthModel(artifact)
    prior_model = SparseStrengthModel(json.loads(prior_artifact_path.read_text()))
    candidate = _outcomes(
        validation,
        [candidate_model.choose(str(row["original_prompt"])) for row in validation],
    )
    prior = _outcomes(
        validation,
        [
            prior_model.predict(str(row["original_prompt"])).recommended_model
            for row in validation
        ],
    )
    fixed = _outcomes(validation, [STRONG_MODEL] * len(validation))
    candidate_summary = _summary(candidate)
    prior_summary = _summary(prior)
    fixed_summary = _summary(fixed)
    shares = {
        str(model): float(share)
        for model, share in candidate_summary["recommendation_share"].items()  # type: ignore[union-attr]
    }
    content_blind = _outcomes(
        validation, _content_blind_choices(validation, shares)
    )
    content_blind_summary = _summary(content_blind)
    oracle = _outcomes(validation, [_oracle(row) for row in validation])
    oracle_summary = _summary(oracle)
    intervals = _intervals(candidate, prior, fixed, content_blind)
    fixed_regret = float(oracle_summary["mean_utility"]) - float(
        fixed_summary["mean_utility"]
    )
    candidate_regret = float(oracle_summary["mean_utility"]) - float(
        candidate_summary["mean_utility"]
    )
    durations = []
    for index in range(2_000):
        prompt = str(validation[index % len(validation)]["original_prompt"])
        started = time.perf_counter_ns()
        candidate_model.choose(prompt)
        durations.append((time.perf_counter_ns() - started) / 1_000_000)
    durations.sort()
    crossfit = _crossfit(
        development + validation,
        auxiliary,
        threshold,
        {**base_provenance, "crossfit_only": True},
    )
    result = {
        "protocol": {
            "name": "Routellect G7-C2 bounded multi-source visible-evidence audit",
            "created_at": datetime.now(UTC).isoformat(),
            "bootstrap_repetitions": BOOTSTRAP_REPETITIONS,
            "bootstrap_seed": BOOTSTRAP_SEED,
            "target_model_calls": 0,
            "hidden_test_runs": 0,
            "confirmatory": False,
        },
        "data": {
            "r2_development_rows": len(development),
            "r2_visible_validation_rows": len(validation),
            "routellm_auxiliary_rows": len(auxiliary),
            "routellm_license": auxiliary_manifest["declared_license"],
            "routellm_revision": auxiliary_manifest["dataset_revision"],
            "raw_model_responses_persisted": False,
        },
        "threshold_attempts": threshold_attempts,
        "selected_threshold": threshold,
        "artifact": {
            "path": str(artifact_path),
            "sha256": file_sha256(artifact_path),
            "strong_nonzero_coefficients": len(artifact["strong_weights"]),
        },
        "visible_validation": {
            "fixed_v2": fixed_summary,
            "g7c_single_source": prior_summary,
            "g7c2_multi_source": candidate_summary,
            "share_matched_content_blind": content_blind_summary,
            "oracle": oracle_summary,
            "paired_bootstrap_95ci": intervals,
            "point_utility_difference_vs_g7c": float(candidate_summary["mean_utility"])
            - float(prior_summary["mean_utility"]),
            "point_quality_retention_vs_fixed": float(candidate_summary["mean_correctness"])
            / float(fixed_summary["mean_correctness"]),
            "point_compute_reduction_vs_fixed": 1
            - float(candidate_summary["mean_normalized_compute"])
            / float(fixed_summary["mean_normalized_compute"]),
            "point_utility_difference_vs_content_blind": float(
                candidate_summary["mean_utility"]
            )
            - float(content_blind_summary["mean_utility"]),
            "point_oracle_regret_reduction_vs_fixed": 1
            - candidate_regret / fixed_regret,
        },
        "runtime": {
            "samples": len(durations),
            "p50_ms": durations[round(0.50 * (len(durations) - 1))],
            "p95_ms": durations[round(0.95 * (len(durations) - 1))],
            "p99_ms": durations[round(0.99 * (len(durations) - 1))],
            "max_ms": durations[-1],
        },
        "grouped_crossfit_visible_evidence": crossfit,
        "promotion_eligible": False,
        "claim_boundary": (
            "Exploratory visible-evidence result. The R2 validation set was inspected in G7-C, "
            "and cross-source overlap with the sealed hidden partition is unknown."
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
        "--auxiliary",
        type=Path,
        default=Path("work/g7c2-evidence/routellm-development.jsonl"),
    )
    parser.add_argument(
        "--auxiliary-manifest",
        type=Path,
        default=Path("work/g7c2-evidence/manifest.json"),
    )
    parser.add_argument(
        "--prior-artifact",
        type=Path,
        default=Path("src/routellect/data/g7_sparse_strength.json"),
    )
    parser.add_argument(
        "--artifact",
        type=Path,
        default=Path("src/routellect/data/g7c2_multisource_strength.json"),
    )
    parser.add_argument(
        "--output", type=Path, default=Path("outputs/phase-7c2-results.json")
    )
    args = parser.parse_args()
    result = run(
        args.development,
        args.validation,
        args.auxiliary,
        args.auxiliary_manifest,
        args.prior_artifact,
        args.artifact,
    )
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result["visible_validation"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
