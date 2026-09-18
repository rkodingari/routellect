from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Objective(StrEnum):
    BALANCED = "balanced"
    BEST_QUALITY = "best_quality"
    LOWEST_COST = "lowest_cost"
    FASTEST = "fastest"


class Privacy(StrEnum):
    STANDARD = "standard"
    NO_TRAINING = "no_training"
    LOCAL_ONLY = "local_only"


class AssessorMode(StrEnum):
    AUTO = "auto"
    ALWAYS = "always"
    OFF = "off"


class PromptMessage(StrictModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str = Field(min_length=1, max_length=200_000)


class RecommendationRequest(StrictModel):
    messages: list[PromptMessage] = Field(min_length=1, max_length=100)
    objective: Objective = Objective.BALANCED
    privacy: Privacy = Privacy.NO_TRAINING
    max_cost_usd: float | None = Field(default=None, ge=0)
    latency_slo_ms: int | None = Field(default=None, ge=1)
    min_quality: float | None = Field(default=None, ge=0, le=1)
    required_capabilities: set[str] = Field(default_factory=set)
    expected_output_tokens: int = Field(default=1_000, ge=1, le=1_000_000)
    feedback_profile_id: str | None = Field(default=None, max_length=100)
    assessor_mode: AssessorMode = AssessorMode.OFF

    @property
    def prompt(self) -> str:
        return "\n".join(message.content for message in self.messages)


class AssessorReport(StrictModel):
    mode: AssessorMode
    invoked: bool
    status: Literal[
        "not_needed", "disabled", "completed", "timed_out", "invalid_output", "unavailable"
    ]
    assessor_version: str | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    fallback_used: bool = False
    latency_ms: float = Field(default=0, ge=0)


class PromptProfile(StrictModel):
    task_family: str
    difficulty: Literal["low", "medium", "high", "uncertain"]
    estimated_input_tokens: int = Field(ge=0)
    required_capabilities: set[str] = Field(default_factory=set)
    privacy_flags: list[str] = Field(default_factory=list)
    uncertainty: float = Field(ge=0, le=1)
    reason_codes: list[str] = Field(default_factory=list)
    assessor: AssessorReport


class ModelConfiguration(StrictModel):
    configuration_id: str
    provider: str
    model_id: str
    display_name: str
    deployment: Literal["hosted", "local", "self_hosted"]
    settings: dict[str, Any]


class RangeEstimate(StrictModel):
    low: float = Field(ge=0)
    expected: float = Field(ge=0)
    high: float = Field(ge=0)
    unit: Literal["usd", "ms", "score_0_1"]

    @model_validator(mode="after")
    def ordered(self) -> RangeEstimate:
        if not self.low <= self.expected <= self.high:
            raise ValueError("range must satisfy low <= expected <= high")
        return self


class EvidenceReference(StrictModel):
    evidence_id: str
    title: str
    url: str | None
    observed_at: datetime
    source_type: Literal[
        "provider_documentation",
        "public_benchmark",
        "local_benchmark",
        "user_feedback",
        "curated_rule",
    ]


class ScoreContribution(StrictModel):
    key: Literal[
        "quality",
        "cost",
        "latency",
        "evidence_risk",
        "uncertainty",
        "feedback",
    ]
    label: str
    value: float = Field(ge=-1, le=1)
    direction: Literal["benefit", "penalty", "neutral"]
    explanation: str


class RankedRecommendation(StrictModel):
    rank: int = Field(ge=1, le=3)
    label: Literal[
        "recommended",
        "economical_alternative",
        "specialist_alternative",
        "privacy_latency_alternative",
    ]
    configuration: ModelConfiguration
    confidence: float = Field(ge=0, le=1)
    score: float = Field(ge=-1, le=2)
    score_contributions: list[ScoreContribution] = Field(min_length=5, max_length=6)
    pareto_efficient: bool
    selection_flags: list[
        Literal[
            "objective_best",
            "pareto_front",
            "lowest_cost",
            "specialist_recall_guard",
            "local_or_fast",
        ]
    ]
    reasons: list[str] = Field(min_length=1, max_length=3)
    warnings: list[str] = Field(default_factory=list)
    quality: RangeEstimate
    cost: RangeEstimate
    latency: RangeEstimate
    evidence: list[EvidenceReference]


class RecommendationResponse(StrictModel):
    recommendation_id: str
    created_at: datetime
    non_executing: Literal[True] = True
    advisor_version: str
    catalog_version: str
    catalog_observed_at: datetime
    analysis: PromptProfile
    recommendations: list[RankedRecommendation] = Field(min_length=1, max_length=3)


class FeedbackRequest(StrictModel):
    used_recommendation: bool
    used_configuration_id: str | None = None
    outcome: Literal["worked", "did_not_work", "unknown"]
    quality_rating: int | None = Field(default=None, ge=1, le=5)
    observed_cost_usd: float | None = Field(default=None, ge=0)
    observed_latency_ms: int | None = Field(default=None, ge=0)
    preferred_over_configuration_id: str | None = None

    @model_validator(mode="after")
    def coherent_usage(self) -> FeedbackRequest:
        if self.used_recommendation and self.used_configuration_id is None:
            raise ValueError("used_configuration_id is required when the recommendation was used")
        if not self.used_recommendation and self.used_configuration_id is not None:
            raise ValueError("used_configuration_id requires used_recommendation=true")
        if (
            self.preferred_over_configuration_id is not None
            and self.used_configuration_id is None
        ):
            raise ValueError("pairwise preference requires a used configuration")
        if self.preferred_over_configuration_id == self.used_configuration_id:
            raise ValueError("pairwise configurations must be different")
        return self


class FeedbackResponse(StrictModel):
    feedback_id: str
    recorded_at: datetime
    prompt_stored: Literal[False] = False


class FeedbackSettings(StrictModel):
    feedback_enabled: bool = True
    personalization_enabled: bool = False
    minimum_support: int = Field(default=5, ge=5, le=100)
    personalization_policy_version: str | None = None
    updated_at: datetime


class FeedbackSettingsUpdate(StrictModel):
    feedback_enabled: bool | None = None
    personalization_enabled: bool | None = None


class FeedbackExport(StrictModel):
    exported_at: datetime
    prompt_included: Literal[False] = False
    settings: FeedbackSettings
    items: list[dict[str, Any]]


class DeletionResult(StrictModel):
    deleted: int = Field(ge=0)
    prompt_data_deleted: Literal[0] = 0


class FeedbackSignal(StrictModel):
    configuration_id: str
    task_family: str
    support: int = Field(ge=0)
    successes: int = Field(ge=0)
    posterior_success: float = Field(ge=0, le=1)
    score_adjustment: float = Field(ge=-0.04, le=0.04)
    applied: bool


class PersonalizationPromotionRequest(StrictModel):
    feedback_profile_id: str = Field(min_length=1, max_length=100)


class FeedbackReplayReport(StrictModel):
    feedback_profile_id: str
    event_count: int = Field(ge=0)
    training_count: int = Field(ge=0)
    holdout_count: int = Field(ge=0)
    baseline_brier: float | None = Field(default=None, ge=0, le=1)
    candidate_brier: float | None = Field(default=None, ge=0, le=1)
    decision: Literal["promoted", "unchanged", "insufficient_data", "rejected"]
    personalization_enabled: bool
    policy_version: str
    policy_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    bias_guard_passed: bool
    slice_metrics: dict[str, dict[str, float | int]] = Field(default_factory=dict)
    promotion_id: str | None = None
    explanation: str


class PromotionAudit(StrictModel):
    promotion_id: str
    created_at: datetime
    feedback_profile_id: str
    policy_version: str
    policy_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    decision: Literal[
        "promoted", "unchanged", "insufficient_data", "rejected", "rolled_back"
    ]
    metrics: dict[str, Any]


class CatalogSummary(StrictModel):
    catalog_version: str
    observed_at: datetime
    expires_at: datetime
    providers: list[str]
    configuration_count: int
    freshness_status: Literal["fresh", "aging", "stale"]
    offline_available: bool = True
    sequence: int = Field(default=1, ge=1)
    source: Literal["builtin", "signed_import"] = "builtin"
    signature_verified: bool = False
    fallback_reason: str | None = None


class CatalogImportResult(StrictModel):
    status: Literal["activated"] = "activated"
    previous_catalog_version: str
    catalog: CatalogSummary


class CatalogRollbackResult(StrictModel):
    status: Literal["rolled_back"] = "rolled_back"
    replaced_catalog_version: str
    catalog: CatalogSummary


class BenchmarkRunRequest(StrictModel):
    evidence_snapshot_id: str = "builtin-g2-fixtures-v1"
    advisor_versions: list[str] = Field(
        default_factory=lambda: ["deterministic-v2+feedback-bayes-v1"]
    )
    split: Literal["development", "validation", "hidden_test", "feedback_holdout"] = "validation"
    seed: int = 42


class BenchmarkRun(StrictModel):
    run_id: str
    status: Literal["queued", "running", "completed", "failed"]
    non_executing: Literal[True] = True
    created_at: datetime
    completed_at: datetime | None = None
    metrics: dict[str, float | int | str | bool | None] | None = None
    error: str | None = None
