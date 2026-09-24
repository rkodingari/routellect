from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import uuid4

from routellect.assessor import LocalAssessor
from routellect.catalog import BUILTIN_CATALOG, Catalog
from routellect.profiler import deterministic_profile, deterministic_profile_v3
from routellect.schemas import (
    EvidenceReference,
    FeedbackSignal,
    ModelConfiguration,
    Objective,
    Privacy,
    RangeEstimate,
    RankedRecommendation,
    RecommendationRequest,
    RecommendationResponse,
    ScoreContribution,
)


@dataclass(frozen=True)
class Candidate:
    raw: dict[str, Any]
    quality: float
    cost: float
    latency: float
    score: float
    feedback: FeedbackSignal | None = None
    contributions: tuple[ScoreContribution, ...] = ()
    pareto_efficient: bool = False
    selection_flags: tuple[str, ...] = ()


WEIGHTS = {
    Objective.BALANCED: (0.58, 0.25, 0.17),
    Objective.BEST_QUALITY: (0.86, 0.08, 0.06),
    Objective.LOWEST_COST: (0.30, 0.62, 0.08),
    Objective.FASTEST: (0.30, 0.10, 0.60),
}

ADVISOR_VERSION = "deterministic-v2+feedback-bayes-v1"
EXPERIMENTAL_ADVISOR_VERSION = "deterministic-v3-candidate.1+feedback-bayes-v1"
V3_COST_SCALE_USD = 0.01
V3_LATENCY_SCALE_MS = 2_000.0


class Advisor:
    def __init__(
        self,
        catalog: Catalog = BUILTIN_CATALOG,
        assessor: LocalAssessor | None = None,
        feedback_signals: Any | None = None,
        policy_version: Literal["v2", "v3"] = "v2",
    ) -> None:
        self.catalog = catalog
        self.assessor = assessor or LocalAssessor()
        self.feedback_signals = feedback_signals
        self.policy_version = policy_version

    def recommend(self, request: RecommendationRequest) -> RecommendationResponse:
        fast_profile = (
            deterministic_profile_v3(request.prompt, request.assessor_mode)
            if self.policy_version == "v3"
            else deterministic_profile(request.prompt, request.assessor_mode)
        )
        profile = self.assessor.assess(request.prompt, fast_profile, request.assessor_mode)
        effective_privacy = self._effective_privacy(request.privacy, profile.privacy_flags)
        required_capabilities = request.required_capabilities | profile.required_capabilities
        signals = (
            self.feedback_signals(profile.task_family, request.feedback_profile_id)
            if self.feedback_signals is not None
            else {}
        )
        candidates = self._eligible_candidates(
            request,
            profile.task_family,
            effective_privacy,
            required_capabilities,
            profile.estimated_input_tokens,
            signals,
            profile.uncertainty,
        )
        if not candidates:
            raise ValueError("No catalog configuration satisfies all hard constraints")

        candidates = self._mark_pareto(candidates)
        ranked = sorted(
            candidates,
            key=lambda candidate: (
                -candidate.score,
                candidate.cost,
                str(candidate.raw["configuration_id"]),
            ),
        )
        pareto_ranked = [candidate for candidate in ranked if candidate.pareto_efficient]
        choices = self._useful_shortlist(pareto_ranked, ranked)
        recommendations = [
            self._render(
                candidate,
                rank,
                request,
                profile.task_family,
                effective_privacy,
                profile.uncertainty,
            )
            for rank, candidate in enumerate(choices, 1)
        ]
        return RecommendationResponse(
            recommendation_id=f"rec_{uuid4().hex}",
            created_at=datetime.now(UTC),
            advisor_version=(
                EXPERIMENTAL_ADVISOR_VERSION
                if self.policy_version == "v3"
                else ADVISOR_VERSION
            ),
            catalog_version=self.catalog.version,
            catalog_observed_at=self.catalog.observed_at,
            analysis=profile,
            recommendations=recommendations,
        )

    @staticmethod
    def _effective_privacy(requested: Privacy, privacy_flags: list[str]) -> Privacy:
        if privacy_flags and requested == Privacy.STANDARD:
            return Privacy.NO_TRAINING
        return requested

    def _eligible_candidates(
        self,
        request: RecommendationRequest,
        task_family: str,
        privacy: Privacy,
        required_capabilities: set[str],
        input_tokens: int,
        feedback_signals: dict[str, FeedbackSignal],
        profile_uncertainty: float,
    ) -> list[Candidate]:
        eligible: list[tuple[dict[str, Any], float, float, float]] = []
        for raw in self.catalog.configurations:
            if privacy == Privacy.LOCAL_ONLY and raw["deployment"] != "local":
                continue
            if privacy.value not in raw["privacy"]:
                continue
            if not required_capabilities <= set(raw["capabilities"]):
                continue
            if input_tokens + request.expected_output_tokens > int(raw["context_window"]):
                continue
            quality = float(raw["quality"].get(task_family, raw["quality"]["general"]))
            if request.min_quality is not None and quality < request.min_quality:
                continue
            cost = (
                input_tokens * float(raw["input_usd_per_million"])
                + request.expected_output_tokens * float(raw["output_usd_per_million"])
            ) / 1_000_000
            if request.max_cost_usd is not None and cost > request.max_cost_usd:
                continue
            latency = float(raw["latency_ms"])
            if request.latency_slo_ms is not None and latency > request.latency_slo_ms:
                continue
            eligible.append((raw, quality, cost, latency))

        if not eligible:
            return []
        max_cost = max((item[2] for item in eligible), default=1) or 1
        max_latency = max(item[3] for item in eligible) or 1
        quality_weight, cost_weight, latency_weight = WEIGHTS[request.objective]
        candidates: list[Candidate] = []
        for raw, quality, cost, latency in eligible:
            if self.policy_version == "v3":
                cost_utility = 1 / (1 + cost / V3_COST_SCALE_USD)
                latency_utility = 1 / (1 + latency / V3_LATENCY_SCALE_MS)
                cost_explanation = (
                    f"Frozen absolute cost transform contributes "
                    f"{cost_weight * cost_utility:+.3f}."
                )
                latency_explanation = (
                    f"Frozen absolute latency transform contributes "
                    f"{latency_weight * latency_utility:+.3f}."
                )
            else:
                cost_utility = 1 - cost / max_cost
                latency_utility = 1 - latency / max_latency
                cost_explanation = (
                    f"Relative cost utility contributes {cost_weight * cost_utility:+.3f}."
                )
                latency_explanation = (
                    f"Relative latency utility contributes "
                    f"{latency_weight * latency_utility:+.3f}."
                )
            evidence_risk = (
                0.04 if raw["evidence"]["source_type"] == "provider_documentation" else 0.10
            )
            quality_contribution = quality_weight * quality
            cost_contribution = cost_weight * cost_utility
            latency_contribution = latency_weight * latency_utility
            uncertainty_penalty = float(raw.get("prior_uncertainty", 0.2)) * (
                0.04 + 0.04 * profile_uncertainty
            )
            score = (
                quality_contribution
                + cost_contribution
                + latency_contribution
                - evidence_risk
                - uncertainty_penalty
            )
            feedback = feedback_signals.get(str(raw["configuration_id"]))
            feedback_adjustment = 0.0
            if feedback is not None and feedback.applied:
                feedback_adjustment = feedback.score_adjustment
                score += feedback_adjustment
            contributions = (
                ScoreContribution(
                    key="quality",
                    label="Expected quality",
                    value=quality_contribution,
                    direction="benefit",
                    explanation=f"{quality_weight:.0%} objective weight × {quality:.2f} prior.",
                ),
                ScoreContribution(
                    key="cost",
                    label="Cost efficiency",
                    value=cost_contribution,
                    direction="benefit" if cost_contribution > 0 else "neutral",
                    explanation=cost_explanation,
                ),
                ScoreContribution(
                    key="latency",
                    label="Latency efficiency",
                    value=latency_contribution,
                    direction="benefit" if latency_contribution > 0 else "neutral",
                    explanation=latency_explanation,
                ),
                ScoreContribution(
                    key="evidence_risk",
                    label="Evidence risk",
                    value=-evidence_risk,
                    direction="penalty",
                    explanation="Penalizes less direct or less reproducible evidence.",
                ),
                ScoreContribution(
                    key="uncertainty",
                    label="Uncertainty",
                    value=-uncertainty_penalty,
                    direction="penalty",
                    explanation=(
                        "Combines prompt ambiguity with the configuration's prior uncertainty."
                    ),
                ),
            )
            if feedback is not None and feedback.applied:
                contributions += (
                    ScoreContribution(
                        key="feedback",
                        label="Private feedback",
                        value=feedback_adjustment,
                        direction=(
                            "benefit"
                            if feedback_adjustment > 0
                            else "penalty"
                            if feedback_adjustment < 0
                            else "neutral"
                        ),
                        explanation=(
                            f"Bounded local signal from {feedback.support} comparable outcomes."
                        ),
                    ),
                )
            candidates.append(
                Candidate(
                    raw,
                    quality,
                    cost,
                    latency,
                    score,
                    feedback,
                    contributions,
                )
            )
        return candidates

    @staticmethod
    def _mark_pareto(candidates: list[Candidate]) -> list[Candidate]:
        marked: list[Candidate] = []
        for candidate in candidates:
            dominated = any(
                other is not candidate
                and other.quality >= candidate.quality
                and other.cost <= candidate.cost
                and other.latency <= candidate.latency
                and (
                    other.quality > candidate.quality
                    or other.cost < candidate.cost
                    or other.latency < candidate.latency
                )
                for other in candidates
            )
            marked.append(replace(candidate, pareto_efficient=not dominated))
        return marked

    @staticmethod
    def _useful_shortlist(
        pareto_ranked: list[Candidate], all_ranked: list[Candidate]
    ) -> list[Candidate]:
        primary = replace(
            pareto_ranked[0], selection_flags=("objective_best", "pareto_front")
        )
        selected = [primary]
        remaining = [item for item in all_ranked if item.raw is not primary.raw]
        if remaining:
            economical = min(
                remaining,
                key=lambda item: (
                    item.cost,
                    -item.quality,
                    str(item.raw["configuration_id"]),
                ),
            )
            flags = ("lowest_cost",)
            if economical.pareto_efficient:
                flags += ("pareto_front",)
            selected.append(replace(economical, selection_flags=flags))
            remaining = [item for item in remaining if item is not economical]
        if remaining:
            specialist = min(
                all_ranked,
                key=lambda item: (
                    -item.quality,
                    -item.score,
                    str(item.raw["configuration_id"]),
                ),
            )
            if all(item.raw is not specialist.raw for item in selected):
                flags = ("specialist_recall_guard",)
                if specialist.pareto_efficient:
                    flags += ("pareto_front",)
                selected.append(replace(specialist, selection_flags=flags))
            else:
                local = [item for item in remaining if item.raw["deployment"] == "local"]
                alternative = min(
                    local or remaining,
                    key=lambda item: (
                        item.latency,
                        -item.quality,
                        str(item.raw["configuration_id"]),
                    ),
                )
                flags = ("local_or_fast",)
                if alternative.pareto_efficient:
                    flags += ("pareto_front",)
                selected.append(replace(alternative, selection_flags=flags))
        return selected

    def _render(
        self,
        candidate: Candidate,
        rank: int,
        request: RecommendationRequest,
        task_family: str,
        effective_privacy: Privacy,
        profile_uncertainty: float,
    ) -> RankedRecommendation:
        raw = candidate.raw
        label = "recommended"
        if rank == 2:
            label = "economical_alternative"
        elif "specialist_recall_guard" in candidate.selection_flags:
            label = "specialist_alternative"
        elif rank == 3:
            label = "privacy_latency_alternative"
        reasons = [
            f"Strong catalog prior for {task_family.replace('_', ' ')} tasks.",
            self._objective_reason(request.objective, candidate),
        ]
        if raw["deployment"] == "local":
            reasons.append("Runs locally and keeps prompt execution under your control.")
        else:
            reasons.append(f"Meets the {effective_privacy.value.replace('_', ' ')} policy.")
        if candidate.feedback is not None and candidate.feedback.applied:
            direction = "positive" if candidate.feedback.score_adjustment >= 0 else "negative"
            reasons[1] += (
                f" Local {direction} feedback signal from "
                f"{candidate.feedback.support} comparable outcomes."
            )
        warnings = [self.catalog.disclaimer]
        if self.catalog.freshness_status != "fresh":
            warnings.append(
                f"Catalog evidence is {self.catalog.freshness_status}; verify before use."
            )
        if raw["evidence"]["source_type"] == "curated_rule":
            warnings.append(
                "Local quality and latency are starter estimates pending hardware validation."
            )
        confidence = max(
            0.30,
            min(
                0.92,
                0.84
                - 0.25 * candidate.raw.get("prior_uncertainty", 0.2)
                - 0.20 * profile_uncertainty,
            ),
        )
        quality_spread = (
            0.04 if raw["evidence"]["source_type"] == "provider_documentation" else 0.08
        )
        evidence = raw["evidence"]
        references = [
            EvidenceReference(
                evidence_id=evidence["id"],
                title=evidence["title"],
                url=evidence["url"],
                observed_at=self.catalog.observed_at,
                source_type=evidence["source_type"],
            )
        ]
        if candidate.feedback is not None and candidate.feedback.applied:
            references.append(
                EvidenceReference(
                    evidence_id=(
                        f"local-feedback-{task_family}-{raw['configuration_id']}"
                    ),
                    title=(
                        f"Local profile feedback · {candidate.feedback.support} outcomes · "
                        f"bounded adjustment {candidate.feedback.score_adjustment:+.3f}"
                    ),
                    url=None,
                    observed_at=datetime.now(UTC),
                    source_type="user_feedback",
                )
            )
        return RankedRecommendation(
            rank=rank,
            label=label,
            configuration=ModelConfiguration(
                configuration_id=raw["configuration_id"],
                provider=raw["provider"],
                model_id=raw["model_id"],
                display_name=raw["display_name"],
                deployment=raw["deployment"],
                settings=raw["settings"],
            ),
            confidence=confidence,
            score=candidate.score,
            score_contributions=list(candidate.contributions),
            pareto_efficient=candidate.pareto_efficient,
            selection_flags=candidate.selection_flags,
            reasons=reasons[:3],
            warnings=warnings,
            quality=RangeEstimate(
                low=max(0, candidate.quality - quality_spread),
                expected=candidate.quality,
                high=min(1, candidate.quality + quality_spread),
                unit="score_0_1",
            ),
            cost=RangeEstimate(
                low=candidate.cost * 0.75,
                expected=candidate.cost,
                high=candidate.cost * 1.5,
                unit="usd",
            ),
            latency=RangeEstimate(
                low=candidate.latency * 0.65,
                expected=candidate.latency,
                high=candidate.latency * 1.65,
                unit="ms",
            ),
            evidence=references,
        )

    @staticmethod
    def _objective_reason(objective: Objective, candidate: Candidate) -> str:
        if objective == Objective.BEST_QUALITY:
            return f"Prioritizes quality with an expected score of {candidate.quality:.2f}."
        if objective == Objective.LOWEST_COST:
            return f"Estimated request cost is ${candidate.cost:.6f}."
        if objective == Objective.FASTEST:
            return f"Catalog latency estimate is about {candidate.latency:.0f} ms."
        return "Balances expected quality, estimated request cost, and latency."
