import hashlib
import json
import socket
from pathlib import Path

import pytest

from routellect.sparse_policy import (
    ARTIFACT_PATH,
    MultiSourceStrengthModel,
    SparseStrengthModel,
    hashed_features,
    load_sparse_strength_model,
)


def test_hashed_features_are_stable_and_normalized() -> None:
    first = hashed_features("Prove that x + 1 > x", 4096, "test-seed")
    second = hashed_features("Prove that x + 1 > x", 4096, "test-seed")
    assert first == second
    assert sum(value * value for value in first.values()) == pytest.approx(1.0)


def test_frozen_sparse_artifact_is_prompt_free_and_development_only() -> None:
    artifact = json.loads(ARTIFACT_PATH.read_text())
    assert artifact["schema_version"] == "routellect-sparse-strength-v1"
    assert artifact["provenance"]["validation_rows_used_for_training_or_tuning"] == 0
    assert artifact["provenance"]["hidden_rows_used"] == 0
    assert "original_prompt" not in ARTIFACT_PATH.read_text()
    assert set(artifact["weights"]) == set(artifact["models"])


def test_sparse_prediction_is_deterministic_and_offline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def denied(*_: object, **__: object) -> None:
        raise AssertionError("network access is forbidden")

    monkeypatch.setattr(socket.socket, "connect", denied)
    model = load_sparse_strength_model()
    assert model is not None
    first = model.predict("Derive the equation and verify each step")
    second = model.predict("Derive the equation and verify each step")
    assert first == second
    assert first.strength in {"low", "medium", "high"}
    assert 0 <= first.confidence <= 1


def test_invalid_artifact_schema_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "invalid.json"
    path.write_text('{"schema_version":"unknown"}')
    with pytest.raises(ValueError, match="unsupported"):
        SparseStrengthModel(json.loads(path.read_text()))


def test_multisource_candidate_is_deterministic_offline_and_not_promoted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact_path = Path("src/routellect/data/g7c2_multisource_strength.json")
    result_path = Path("outputs/phase-7c2-results.json")
    artifact = json.loads(artifact_path.read_text())
    results = json.loads(result_path.read_text())

    def denied(*_: object, **__: object) -> None:
        raise AssertionError("network access is forbidden")

    monkeypatch.setattr(socket.socket, "connect", denied)
    model = MultiSourceStrengthModel(artifact)
    prompt = "Review this Python concurrency design and identify race conditions"
    assert model.choose(prompt) == model.choose(prompt)
    assert artifact["provenance"]["hidden_rows_used"] == 0
    assert artifact["provenance"]["raw_model_responses_used"] == 0
    assert results["promotion_eligible"] is False
    assert results["protocol"]["hidden_test_runs"] == 0
    assert (
        results["grouped_crossfit_visible_evidence"]["paired_bootstrap_95ci"]
        ["utility_vs_fixed"][0]
        > 0
    )


def test_g7d_candidate_is_frozen_but_not_promoted() -> None:
    artifact_path = Path("src/routellect/data/g7c2_multisource_strength.json")
    validation_path = Path("outputs/phase-7d-validation-results.json")
    podman_path = Path("outputs/phase-7d-podman-results.json")
    freeze_path = Path("outputs/phase-7d-candidate-freeze.json")
    validation = json.loads(validation_path.read_text())
    podman = json.loads(podman_path.read_text())
    freeze = json.loads(freeze_path.read_text())

    artifact_digest = hashlib.sha256(artifact_path.read_bytes()).hexdigest()
    assert freeze["candidate"]["artifact_sha256"] == artifact_digest
    assert validation["protocol"]["bootstrap_repetitions"] == 10_000
    assert validation["protocol"]["hidden_test_runs"] == 0
    assert validation["ready_to_freeze"] is True
    assert validation["promotion_eligible"] is False
    assert all(validation["freeze_checks"].values())
    assert "original_prompt" not in validation_path.read_text()
    assert all(podman["acceptance_checks"].values())
    assert podman["offline_candidate"]["artifact_sha256"] == artifact_digest
    assert freeze["confirmatory_evaluation"]["authorized"] is False
    assert freeze["confirmatory_evaluation"]["executed"] is False
    assert freeze["production"]["default"] == "deterministic-v2+feedback-bayes-v1"
    assert freeze["production"]["v3_active"] is False
