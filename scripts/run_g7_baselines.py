#!/usr/bin/env python3
"""Measure G7-B development/validation baselines without opening hidden evidence."""

from __future__ import annotations

import argparse
import json
import statistics
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from routellect.evidence_benchmark import (
    CANDIDATE_PARAMETERS,
    PRIMARY_LAMBDA,
    STRATEGIES,
    EvidenceRow,
    Observation,
    bootstrap_intervals,
    evaluate_policy,
    file_sha256,
    fit_policy,
    pareto_front,
    prompt_length_band,
    routing_overhead,
    slice_summaries,
    summarize_outcomes,
)
from routellect.profiler import deterministic_profile
from routellect.schemas import AssessorMode

BOOTSTRAP_REPETITIONS = 2_000
BOOTSTRAP_SEED = 73


def _read_raw(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            row = json.loads(line)
            if set(row.get("models", {})) != set(CANDIDATE_PARAMETERS):
                raise ValueError(f"candidate mismatch on {path.name} line {line_number}")
            for values in row["models"].values():
                score = float(values["correctness_score"])
                tokens = int(values["actual_token_count"])
                if not 0 <= score <= 1 or tokens < 0:
                    raise ValueError(f"invalid observation on {path.name} line {line_number}")
            rows.append(row)
    if not rows:
        raise ValueError(f"{path} has no evidence rows")
    return rows


def _development_maximum_compute(rows: list[dict]) -> float:
    maximum = max(
        CANDIDATE_PARAMETERS[model] * int(values["actual_token_count"])
        for row in rows
        for model, values in row["models"].items()
    )
    if maximum <= 0:
        raise ValueError("development evidence has no positive compute observation")
    return maximum


def _profile_rows(rows: list[dict], maximum_compute: float) -> list[EvidenceRow]:
    evidence: list[EvidenceRow] = []
    for row in rows:
        prompt = str(row["original_prompt"])
        profile = deterministic_profile(prompt, AssessorMode.OFF)
        evidence.append(
            EvidenceRow(
                key=str(row["key"]),
                task_family=profile.task_family,
                length_band=prompt_length_band(len(prompt)),
                prompt_length=len(prompt),
                observations={
                    model: Observation(
                        correctness=float(values["correctness_score"]),
                        normalized_compute=(
                            CANDIDATE_PARAMETERS[model]
                            * int(values["actual_token_count"])
                            / maximum_compute
                        ),
                        actual_token_count=int(values["actual_token_count"]),
                    )
                    for model, values in row["models"].items()
                },
            )
        )
    return evidence


def _round(value: object) -> object:
    if isinstance(value, float):
        return round(value, 8)
    if isinstance(value, list):
        return [_round(item) for item in value]
    if isinstance(value, dict):
        return {key: _round(item) for key, item in value.items()}
    return value


def run(
    development_path: Path,
    validation_path: Path,
    manifest_path: Path,
    *,
    bootstrap_repetitions: int = BOOTSTRAP_REPETITIONS,
) -> dict[str, object]:
    manifest = json.loads(manifest_path.read_text())
    persisted = manifest["persisted_partitions"]
    for name, path in (
        ("development", development_path),
        ("validation", validation_path),
    ):
        expected = persisted[name]["sha256"]
        actual = file_sha256(path)
        if actual != expected:
            raise ValueError(f"{name} digest mismatch: expected {expected}, got {actual}")
    if manifest["hidden_partition"]["outcomes_persisted"] is not False:
        raise ValueError("G7-B baseline run requires an unopened hidden partition")

    raw_development = _read_raw(development_path)
    raw_validation = _read_raw(validation_path)
    maximum_compute = _development_maximum_compute(raw_development)
    started = time.perf_counter()
    development = _profile_rows(raw_development, maximum_compute)
    validation = _profile_rows(raw_validation, maximum_compute)
    profiling_ms = (time.perf_counter() - started) * 1_000

    policies = {
        strategy: fit_policy(development, strategy, PRIMARY_LAMBDA)
        for strategy in STRATEGIES
    }
    outcomes = {
        strategy: evaluate_policy(policy, validation, PRIMARY_LAMBDA)
        for strategy, policy in policies.items()
    }
    oracle_mean = statistics.fmean(item.utility for item in outcomes["oracle"])
    summaries: dict[str, dict[str, object]] = {}
    intervals = bootstrap_intervals(
        outcomes,
        repetitions=bootstrap_repetitions,
        seed=BOOTSTRAP_SEED,
    )
    for strategy, items in outcomes.items():
        summary = summarize_outcomes(items, oracle_mean)
        summary.update(intervals[strategy])
        summary["paired_utility_difference_vs_global"] = statistics.fmean(
            item.utility - baseline.utility
            for item, baseline in zip(items, outcomes["global_utility"], strict=True)
        )
        summary["slices"] = slice_summaries(items)
        summaries[strategy] = summary

    deployable = {name: summaries[name] for name in STRATEGIES if name != "oracle"}
    task_counts = Counter(row.task_family for row in development + validation)
    length_counts = Counter(row.length_band for row in development + validation)
    overhead = routing_overhead(
        policies["hybrid_segment"], validation, PRIMARY_LAMBDA, repetitions=10_000
    )
    return _round(
        {
            "protocol": {
                "name": "Routellect G7-B unopened-hidden baseline audit",
                "created_at": datetime.now(UTC).isoformat(),
                "primary_lambda": PRIMARY_LAMBDA,
                "bootstrap_repetitions": bootstrap_repetitions,
                "bootstrap_seed": BOOTSTRAP_SEED,
                "normalization": (
                    "parameter_billions * actual_output_tokens / "
                    "development_maximum_compute"
                ),
                "development_maximum_compute": maximum_compute,
                "target_model_calls": 0,
                "hidden_test_runs": 0,
                "hidden_prompts_or_outcomes_loaded": False,
            },
            "data": {
                "dataset_id": manifest["dataset_id"],
                "dataset_revision": manifest["dataset_revision"],
                "development_rows": len(development),
                "validation_rows": len(validation),
                "committed_hidden_rows": manifest["hidden_partition"]["rows"],
                "missing_observations": 0,
                "excluded_rows": manifest["excluded_rows"],
                "task_family_counts": dict(sorted(task_counts.items())),
                "length_band_counts": dict(sorted(length_counts.items())),
                "development_sha256": persisted["development"]["sha256"],
                "validation_sha256": persisted["validation"]["sha256"],
                "hidden_key_prompt_commitment_sha256": manifest["hidden_partition"][
                    "key_prompt_commitment_sha256"
                ],
            },
            "profiler": {
                "version": "deterministic-v2",
                "profiled_rows": len(development) + len(validation),
                "elapsed_ms": profiling_ms,
                "mean_ms_per_prompt": profiling_ms / (len(development) + len(validation)),
                "general_share": task_counts.get("general", 0)
                / (len(development) + len(validation)),
                "note": (
                    "Task labels are v2 predictions, not ground-truth task labels; this audit "
                    "measures their routing value only."
                ),
            },
            "validation": {
                "strategies": summaries,
                "deployable_pareto_front": pareto_front(deployable),
            },
            "routing_overhead": overhead,
            "claim_boundary": (
                "Validation-only historical offline evidence for the exact frozen candidate pool. "
                "The hidden partition was not persisted or evaluated, and the benchmark adapter "
                "does not validate Routellect's live provider catalog."
            ),
        }
    )  # type: ignore[return-value]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--development",
        type=Path,
        default=Path("work/g7-evidence/development.jsonl"),
    )
    parser.add_argument(
        "--validation",
        type=Path,
        default=Path("work/g7-evidence/validation.jsonl"),
    )
    parser.add_argument(
        "--manifest", type=Path, default=Path("work/g7-evidence/manifest.json")
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/phase-7-baseline-results.json"),
    )
    parser.add_argument(
        "--bootstrap-repetitions", type=int, default=BOOTSTRAP_REPETITIONS
    )
    args = parser.parse_args()
    result = run(
        args.development,
        args.validation,
        args.manifest,
        bootstrap_repetitions=args.bootstrap_repetitions,
    )
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
