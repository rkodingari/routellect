import socket

import pytest

from routellect.advisor import Advisor
from routellect.assessor import LocalAssessor
from routellect.schemas import (
    AssessorMode,
    Objective,
    Privacy,
    PromptMessage,
    RecommendationRequest,
)


def request_for(prompt: str, **kwargs: object) -> RecommendationRequest:
    return RecommendationRequest(
        messages=[PromptMessage(role="user", content=prompt)],
        assessor_mode=AssessorMode.OFF,
        **kwargs,
    )


def test_deterministic_path_is_the_safe_default() -> None:
    request = RecommendationRequest(messages=[PromptMessage(role="user", content="Hello")])
    assert request.assessor_mode == AssessorMode.OFF


def test_same_frozen_input_is_stable_except_receipt_fields() -> None:
    advisor = Advisor(assessor=LocalAssessor(backend=lambda _: "{}"))
    request = request_for("Debug this Python function", objective=Objective.BALANCED)
    first = advisor.recommend(request)
    second = advisor.recommend(request)
    assert [item.configuration.configuration_id for item in first.recommendations] == [
        item.configuration.configuration_id for item in second.recommendations
    ]


def test_local_only_never_returns_hosted_model() -> None:
    response = Advisor().recommend(
        request_for("Explain this algorithm", privacy=Privacy.LOCAL_ONLY)
    )
    assert all(item.configuration.deployment == "local" for item in response.recommendations)


def test_advice_causes_zero_network_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    def denied(*_: object, **__: object) -> None:
        raise AssertionError("network access is forbidden during advice")

    monkeypatch.setattr(socket.socket, "connect", denied)
    response = Advisor().recommend(request_for("Write a concise welcome email"))
    assert response.non_executing is True


def test_unsatisfiable_constraints_are_explicit() -> None:
    with pytest.raises(ValueError, match="No catalog configuration"):
        Advisor().recommend(
            request_for(
                "Transcribe this audio locally",
                privacy=Privacy.LOCAL_ONLY,
                required_capabilities={"audio"},
            )
        )


def test_explainable_scores_reconcile_and_primary_is_pareto_efficient() -> None:
    response = Advisor().recommend(
        request_for("Compare two database migration plans and identify operational risks")
    )
    assert response.recommendations[0].pareto_efficient is True
    assert "objective_best" in response.recommendations[0].selection_flags
    for item in response.recommendations:
        assert item.score == pytest.approx(
            sum(contribution.value for contribution in item.score_contributions)
        )


def test_shortlist_retains_the_quality_specialist() -> None:
    response = Advisor().recommend(
        request_for(
            "Prove a difficult theorem and carefully validate every inference",
            objective=Objective.LOWEST_COST,
        )
    )
    assert len(response.recommendations) == 3
    assert any(
        "specialist_recall_guard" in item.selection_flags
        for item in response.recommendations
    ) or response.recommendations[0].quality.expected == max(
        item.quality.expected for item in response.recommendations
    )


def test_prompt_uncertainty_reduces_confidence() -> None:
    clear = Advisor().recommend(request_for("Write a concise welcome email"))
    ambiguous = Advisor().recommend(request_for("Help me with this thing somehow"))
    assert ambiguous.analysis.uncertainty >= clear.analysis.uncertainty
    assert ambiguous.recommendations[0].confidence <= clear.recommendations[0].confidence
