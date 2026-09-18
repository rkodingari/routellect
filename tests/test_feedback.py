import sqlite3
from pathlib import Path

import pytest

from routellect.advisor import Advisor
from routellect.learning import FeedbackLearner
from routellect.schemas import (
    FeedbackRequest,
    FeedbackSettingsUpdate,
    PromptMessage,
    RecommendationRequest,
)
from routellect.storage import FeedbackDisabledError, Store


def add_outcome(
    store: Store,
    *,
    profile: str = "profile-a",
    outcome: str = "worked",
    prompt: str = "Write a concise welcome email",
) -> tuple[str, str]:
    request = RecommendationRequest(
        messages=[PromptMessage(role="user", content=prompt)],
        feedback_profile_id=profile,
    )
    response = Advisor().recommend(request)
    store.save_recommendation(
        response,
        objective=request.objective.value,
        privacy=request.privacy.value,
        feedback_profile_id=profile,
    )
    configuration_id = response.recommendations[0].configuration.configuration_id
    feedback = store.save_feedback(
        response.recommendation_id,
        FeedbackRequest(
            used_recommendation=True,
            used_configuration_id=configuration_id,
            outcome=outcome,  # type: ignore[arg-type]
        ),
    )
    assert feedback is not None
    return feedback.feedback_id, configuration_id


def test_sparse_feedback_is_ignored_and_profile_isolated(tmp_path: Path) -> None:
    store = Store(tmp_path / "feedback.sqlite3")
    store.initialize()
    configuration_id = ""
    for _ in range(4):
        _, configuration_id = add_outcome(store)
    store.set_personalization_promoted(True, "feedback-bayes-v1")
    signals = FeedbackLearner(store).signals("writing", "profile-a")
    assert signals[configuration_id].support == 4
    assert signals[configuration_id].applied is False
    assert signals[configuration_id].score_adjustment == 0
    assert FeedbackLearner(store).signals("writing", "profile-b") == {}


def test_replay_promotes_non_regressing_feedback_and_bounds_influence(tmp_path: Path) -> None:
    store = Store(tmp_path / "feedback.sqlite3")
    store.initialize()
    configuration_id = ""
    for _ in range(10):
        _, configuration_id = add_outcome(store)
    report = FeedbackLearner(store).replay_and_promote("profile-a")
    assert report.decision in {"promoted", "unchanged"}
    assert report.candidate_brier is not None
    assert report.baseline_brier is not None
    assert report.candidate_brier <= report.baseline_brier + 0.005
    signal = FeedbackLearner(store).signals("writing", "profile-a")[configuration_id]
    assert signal.applied is True
    assert 0 < signal.score_adjustment <= 0.04

    store.reset_feedback()
    for _ in range(20):
        _, configuration_id = add_outcome(store, outcome="did_not_work")
    negative = FeedbackLearner(store).signals("writing", "profile-a")[configuration_id]
    assert negative.score_adjustment == pytest.approx(-0.04)


def test_feedback_controls_export_delete_reset_and_opt_out(tmp_path: Path) -> None:
    database = tmp_path / "feedback.sqlite3"
    store = Store(database)
    store.initialize()
    feedback_id, _ = add_outcome(store, prompt="CANARY-PRIVATE-PROMPT-9981")
    exported = store.export_feedback()
    assert exported.prompt_included is False
    assert len(exported.items) == 1
    assert "CANARY-PRIVATE-PROMPT-9981" not in exported.model_dump_json()
    assert b"CANARY-PRIVATE-PROMPT-9981" not in database.read_bytes()
    assert store.delete_feedback(feedback_id).deleted == 1
    assert store.reset_feedback().deleted == 0

    settings = store.update_feedback_settings(
        FeedbackSettingsUpdate(feedback_enabled=False)
    )
    assert settings.feedback_enabled is False
    request = RecommendationRequest(
        messages=[PromptMessage(role="user", content="Hello")]
    )
    response = Advisor().recommend(request)
    store.save_recommendation(
        response,
        objective=request.objective.value,
        privacy=request.privacy.value,
    )
    with pytest.raises(FeedbackDisabledError):
        store.save_feedback(
            response.recommendation_id,
            FeedbackRequest(
                used_recommendation=True,
                used_configuration_id=(
                    response.recommendations[0].configuration.configuration_id
                ),
                outcome="worked",
            ),
        )


def test_schema_migration_preserves_existing_receipts(tmp_path: Path) -> None:
    path = tmp_path / "legacy.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE recommendation_receipts (
                recommendation_id TEXT PRIMARY KEY, created_at TEXT NOT NULL,
                catalog_version TEXT NOT NULL, objective TEXT NOT NULL,
                privacy TEXT NOT NULL, task_family TEXT NOT NULL,
                difficulty TEXT NOT NULL, assessor_json TEXT NOT NULL,
                selected_configuration_ids_json TEXT NOT NULL,
                feedback_received INTEGER NOT NULL DEFAULT 0
            );
            INSERT INTO recommendation_receipts VALUES
                ('rec_legacy', '2026-09-15T00:00:00+00:00', 'v1', 'balanced',
                 'no_training', 'writing', 'low', '{}', '["model-a"]', 0);
            """
        )
    store = Store(path)
    store.initialize()
    receipt = store.get_receipt("rec_legacy")
    assert receipt is not None
    assert receipt["feedback_profile_id"] is None
    assert receipt["advisor_version"] == "deterministic-v1"


def test_promotion_attempts_are_audited_and_rollback_is_explicit(tmp_path: Path) -> None:
    store = Store(tmp_path / "feedback.sqlite3")
    store.initialize()
    insufficient = FeedbackLearner(store).replay_and_promote("profile-a")
    assert insufficient.promotion_id is not None
    assert insufficient.policy_digest
    audit = store.list_promotions()
    assert audit[0].decision == "insufficient_data"

    store.set_personalization_promoted(True, "feedback-bayes-v1")
    rolled_back = store.rollback_personalization("profile-a")
    assert rolled_back.decision == "rolled_back"
    assert store.get_feedback_settings().personalization_enabled is False
    assert store.list_promotions()[0].promotion_id == rolled_back.promotion_id


def test_replay_rejects_a_regressing_task_slice(tmp_path: Path) -> None:
    store = Store(tmp_path / "feedback.sqlite3")
    store.initialize()
    for _ in range(5):
        add_outcome(store, outcome="worked", prompt="Debug this Python race condition")
    for _ in range(5):
        add_outcome(store, outcome="did_not_work", prompt="Write a concise welcome email")
    for _ in range(2):
        add_outcome(store, outcome="worked", prompt="Write a concise welcome email")

    report = FeedbackLearner(store).replay_and_promote("profile-a")
    assert report.decision == "rejected"
    assert report.bias_guard_passed is False
    assert report.slice_metrics["writing"]["candidate_brier"] > (
        report.slice_metrics["writing"]["baseline_brier"]
    )
    assert store.get_feedback_settings().personalization_enabled is False
