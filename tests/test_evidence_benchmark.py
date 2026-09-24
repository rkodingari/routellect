from __future__ import annotations

import hashlib
import json

import pytest

from routellect.evidence_benchmark import (
    CANDIDATE_PARAMETERS,
    EvidenceRow,
    Observation,
    bootstrap_intervals,
    choose_model,
    fit_policy,
    load_evidence,
    pareto_front,
    promotion_decision,
    prompt_length_band,
    run_benchmark,
    stable_split,
)


def _row(
    key: str,
    *,
    task: str = "general",
    length: int = 50,
    qualities: dict[str, float] | None = None,
) -> EvidenceRow:
    values = qualities or {model: 0.5 for model in CANDIDATE_PARAMETERS}
    observations = {
        model: Observation(
            correctness=values[model],
            normalized_compute=(index + 1) / len(CANDIDATE_PARAMETERS),
            actual_token_count=100,
        )
        for index, model in enumerate(CANDIDATE_PARAMETERS)
    }
    return EvidenceRow(
        key=key,
        task_family=task,
        length_band=prompt_length_band(length),
        prompt_length=length,
        observations=observations,
    )


def test_stable_split_is_deterministic_and_covers_expected_names() -> None:
    first = [stable_split(f"key-{index}") for index in range(500)]
    second = [stable_split(f"key-{index}") for index in range(500)]
    assert first == second
    assert set(first) == {"train", "validation", "hidden_test"}


def test_length_bands_use_frozen_boundaries() -> None:
    assert prompt_length_band(127) == "lt_128"
    assert prompt_length_band(128) == "128_511"
    assert prompt_length_band(512) == "512_2047"
    assert prompt_length_band(2_048) == "gte_2048"


def test_segment_policy_uses_training_rows_only() -> None:
    models = list(CANDIDATE_PARAMETERS)
    cheap, specialist = models[0], models[1]
    qualities = {model: 0.1 for model in models}
    qualities[cheap] = 0.2
    qualities[specialist] = 0.9
    train = [_row(f"train-{index}", task="reasoning", qualities=qualities) for index in range(30)]
    policy = fit_policy(train, "task_segment", 0.0)

    altered_test = _row(
        "hidden",
        task="reasoning",
        qualities={model: (1.0 if model == cheap else 0.0) for model in models},
    )
    assert choose_model(policy, altered_test, 0.0) == specialist


def test_pareto_front_excludes_dominated_strategy() -> None:
    summaries = {
        "balanced": {"mean_correctness": 0.8, "mean_normalized_compute": 0.5},
        "cheap": {"mean_correctness": 0.7, "mean_normalized_compute": 0.2},
        "dominated": {"mean_correctness": 0.6, "mean_normalized_compute": 0.6},
    }
    assert pareto_front(summaries) == ["balanced", "cheap"]


def test_bootstrap_is_seeded_and_paired() -> None:
    from routellect.evidence_benchmark import Outcome

    global_items = [
        Outcome(str(i), "general", "lt_128", "a", 0.5, 0.2, 0.46)
        for i in range(8)
    ]
    hybrid_items = [
        Outcome(str(i), "general", "lt_128", "b", 0.6, 0.2, 0.56)
        for i in range(8)
    ]
    outcomes = {"global_utility": global_items, "hybrid_segment": hybrid_items}
    first = bootstrap_intervals(outcomes, repetitions=50, seed=42)
    second = bootstrap_intervals(outcomes, repetitions=50, seed=42)
    assert first == second
    assert first["hybrid_segment"][
        "paired_utility_difference_vs_global_95ci"
    ] == pytest.approx([0.1, 0.1])


def test_promotion_guard_rejects_utility_regression() -> None:
    from routellect.evidence_benchmark import Outcome

    baseline = [
        Outcome(str(i), "general", "lt_128", "a", 0.8, 0.2, 0.76)
        for i in range(40)
    ]
    hybrid = [
        Outcome(str(i), "general", "lt_128", "b", 0.7, 0.2, 0.66)
        for i in range(40)
    ]
    decision = promotion_decision(
        {"global_utility": baseline, "hybrid_segment": hybrid},
        {"p95_ms": 0.01},
    )
    assert decision["eligible_for_separate_offline_policy_review"] is False
    assert decision["checks"]["utility_not_below_global"] is False


def test_load_evidence_verifies_snapshot_and_profiles_prompt(tmp_path) -> None:
    models = {
        model: {"actual_token_count": 100, "correctness_score": 0.5}
        for model in CANDIDATE_PARAMETERS
    }
    snapshot = tmp_path / "snapshot.jsonl"
    snapshot.write_text(
        json.dumps(
            {
                "key": "key-1",
                "prompts_id": "1",
                "original_prompt": "Debug this Python function.",
                "models": models,
            }
        )
        + "\n"
    )
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "dataset_revision": "fixed-revision",
                "snapshot_sha256": hashlib.sha256(snapshot.read_bytes()).hexdigest(),
            }
        )
    )
    rows, loaded_manifest = load_evidence(snapshot, manifest)
    assert rows[0].task_family == "code"
    assert loaded_manifest["normalization"]["uses_correctness_labels"] is False


def test_synthetic_end_to_end_benchmark_never_calls_models() -> None:
    models = list(CANDIDATE_PARAMETERS)
    rows = []
    for index in range(180):
        qualities = {
            model: min(1.0, 0.25 + model_index * 0.15 + (index % 3) * 0.01)
            for model_index, model in enumerate(models)
        }
        rows.append(
            _row(
                f"pipeline-key-{index}",
                task="reasoning" if index % 2 else "general",
                length=50 if index % 3 else 700,
                qualities=qualities,
            )
        )
    result = run_benchmark(rows, bootstrap_repetitions=5)
    assert result["protocol"]["target_model_calls"] == 0
    assert result["protocol"]["hidden_test_runs"] == 1
    assert result["data"]["total_rows"] == 180
    assert "hidden_test" in result["primary_confirmatory_results"]
