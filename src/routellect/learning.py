from __future__ import annotations

import hashlib
import json
from collections import Counter

from routellect.schemas import FeedbackReplayReport, FeedbackSignal
from routellect.storage import Store

PRIOR_ALPHA = 8.0
PRIOR_BETA = 2.0
PRIOR_STRENGTH = PRIOR_ALPHA + PRIOR_BETA
MAX_SCORE_ADJUSTMENT = 0.04
FEEDBACK_POLICY_VERSION = "feedback-bayes-v1"


def feedback_policy_digest(minimum_support: int) -> str:
    manifest = {
        "policy_version": FEEDBACK_POLICY_VERSION,
        "prior_alpha": PRIOR_ALPHA,
        "prior_beta": PRIOR_BETA,
        "minimum_support": minimum_support,
        "maximum_score_adjustment": MAX_SCORE_ADJUSTMENT,
        "promotion_metric": "chronological_brier",
        "non_regression_tolerance": 0.005,
    }
    canonical = json.dumps(manifest, separators=(",", ":"), sort_keys=True).encode()
    return hashlib.sha256(canonical).hexdigest()


class FeedbackLearner:
    """Compute bounded empirical-Bayes ranking signals from local structured outcomes."""

    def __init__(self, store: Store) -> None:
        self.store = store

    def signals(self, task_family: str, profile_id: str | None) -> dict[str, FeedbackSignal]:
        settings = self.store.get_feedback_settings()
        if not profile_id or not settings.feedback_enabled or not settings.personalization_enabled:
            return {}
        global_outcomes = self.store.feedback_outcomes(profile_id=profile_id)
        global_successes = sum(success for _, success in global_outcomes)
        global_rate = (PRIOR_ALPHA + global_successes) / (
            PRIOR_STRENGTH + len(global_outcomes)
        )
        task_outcomes = self.store.feedback_outcomes(
            task_family=task_family, profile_id=profile_id
        )
        support = Counter(configuration_id for configuration_id, _ in task_outcomes)
        successes = Counter(
            configuration_id for configuration_id, success in task_outcomes if success
        )
        result: dict[str, FeedbackSignal] = {}
        for configuration_id, count in support.items():
            posterior = (PRIOR_STRENGTH * global_rate + successes[configuration_id]) / (
                PRIOR_STRENGTH + count
            )
            applied = count >= settings.minimum_support
            adjustment = 0.0
            if applied:
                support_weight = min(1.0, count / 20)
                adjustment = max(
                    -MAX_SCORE_ADJUSTMENT,
                    min(
                        MAX_SCORE_ADJUSTMENT,
                        (posterior - global_rate) * 0.35 * support_weight,
                    ),
                )
            result[configuration_id] = FeedbackSignal(
                configuration_id=configuration_id,
                task_family=task_family,
                support=count,
                successes=successes[configuration_id],
                posterior_success=posterior,
                score_adjustment=adjustment,
                applied=applied,
            )
        return result

    def replay_and_promote(self, profile_id: str) -> FeedbackReplayReport:
        """Run a chronological calibration replay before a manual promotion."""
        events = self.store.feedback_events(profile_id)
        settings = self.store.get_feedback_settings()
        policy_digest = feedback_policy_digest(settings.minimum_support)
        minimum_events = 10
        if len(events) < minimum_events:
            report = FeedbackReplayReport(
                feedback_profile_id=profile_id,
                event_count=len(events),
                training_count=0,
                holdout_count=0,
                decision="insufficient_data",
                personalization_enabled=settings.personalization_enabled,
                policy_version=FEEDBACK_POLICY_VERSION,
                policy_digest=policy_digest,
                bias_guard_passed=False,
                explanation=(
                    f"At least {minimum_events} usable outcomes are required "
                    "for chronological replay."
                ),
            )
            return self.store.record_promotion(report)
        holdout_count = max(2, len(events) // 5)
        training = events[:-holdout_count]
        holdout = events[-holdout_count:]
        successes = sum(bool(item["success"]) for item in training)
        baseline = (PRIOR_ALPHA + successes) / (PRIOR_STRENGTH + len(training))
        pair_support: Counter[tuple[str, str]] = Counter()
        pair_successes: Counter[tuple[str, str]] = Counter()
        for item in training:
            pair = (str(item["task_family"]), str(item["configuration_id"]))
            pair_support[pair] += 1
            if bool(item["success"]):
                pair_successes[pair] += 1
        baseline_error = 0.0
        candidate_error = 0.0
        slice_errors: dict[str, list[float]] = {}
        for item in holdout:
            actual = float(bool(item["success"]))
            pair = (str(item["task_family"]), str(item["configuration_id"]))
            support = pair_support[pair]
            candidate = baseline
            if support >= settings.minimum_support:
                candidate = (PRIOR_STRENGTH * baseline + pair_successes[pair]) / (
                    PRIOR_STRENGTH + support
                )
            baseline_item_error = (baseline - actual) ** 2
            candidate_item_error = (candidate - actual) ** 2
            baseline_error += baseline_item_error
            candidate_error += candidate_item_error
            task = str(item["task_family"])
            bucket = slice_errors.setdefault(task, [0.0, 0.0, 0.0])
            bucket[0] += baseline_item_error
            bucket[1] += candidate_item_error
            bucket[2] += 1
        baseline_brier = baseline_error / holdout_count
        candidate_brier = candidate_error / holdout_count
        slice_metrics = {
            task: {
                "count": int(values[2]),
                "baseline_brier": values[0] / values[2],
                "candidate_brier": values[1] / values[2],
            }
            for task, values in slice_errors.items()
        }
        bias_guard_passed = all(
            values["candidate_brier"] <= values["baseline_brier"] + 0.005
            for values in slice_metrics.values()
        )
        if candidate_brier <= baseline_brier + 0.005 and bias_guard_passed:
            promoted_settings = self.store.set_personalization_promoted(
                True, FEEDBACK_POLICY_VERSION
            )
            improved = candidate_brier < baseline_brier - 1e-12
            report = FeedbackReplayReport(
                feedback_profile_id=profile_id,
                event_count=len(events),
                training_count=len(training),
                holdout_count=holdout_count,
                baseline_brier=baseline_brier,
                candidate_brier=candidate_brier,
                decision="promoted" if improved else "unchanged",
                personalization_enabled=promoted_settings.personalization_enabled,
                policy_version=FEEDBACK_POLICY_VERSION,
                policy_digest=policy_digest,
                bias_guard_passed=True,
                slice_metrics=slice_metrics,
                explanation=(
                    "Chronological holdout improved; bounded personalization was promoted."
                    if improved
                    else (
                        "Chronological holdout was unchanged; bounded personalization "
                        "was promoted."
                    )
                ),
            )
            return self.store.record_promotion(report)
        report = FeedbackReplayReport(
            feedback_profile_id=profile_id,
            event_count=len(events),
            training_count=len(training),
            holdout_count=holdout_count,
            baseline_brier=baseline_brier,
            candidate_brier=candidate_brier,
            decision="rejected",
            personalization_enabled=settings.personalization_enabled,
            policy_version=FEEDBACK_POLICY_VERSION,
            policy_digest=policy_digest,
            bias_guard_passed=bias_guard_passed,
            slice_metrics=slice_metrics,
            explanation=(
                "Candidate calibration regressed the holdout or a task slice and was not promoted."
            ),
        )
        return self.store.record_promotion(report)
