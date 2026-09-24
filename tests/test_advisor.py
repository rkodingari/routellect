import socket
from dataclasses import replace

import pytest

from routellect.advisor import Advisor
from routellect.assessor import LocalAssessor
from routellect.catalog import BUILTIN_CATALOG
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
    first_payload = first.model_dump(mode="json")
    second_payload = second.model_dump(mode="json")
    for payload in (first_payload, second_payload):
        payload.pop("recommendation_id")
        payload.pop("created_at")
    assert first_payload == second_payload


def test_local_only_never_returns_hosted_model() -> None:
    response = Advisor().recommend(
        request_for("Explain this algorithm", privacy=Privacy.LOCAL_ONLY)
    )
    assert all(item.configuration.deployment == "local" for item in response.recommendations)


def test_detected_sensitive_content_tightens_standard_privacy() -> None:
    response = Advisor().recommend(
        request_for("Summarize the account for person@example.com", privacy=Privacy.STANDARD)
    )
    configurations = {
        str(raw["configuration_id"]): raw for raw in BUILTIN_CATALOG.configurations
    }
    assert "email" in response.analysis.privacy_flags
    assert all(
        Privacy.NO_TRAINING.value
        in configurations[item.configuration.configuration_id]["privacy"]
        for item in response.recommendations
    )


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


def test_one_unified_policy_is_the_only_advisor_path() -> None:
    response = Advisor().recommend(request_for("Debug this Python function"))
    assert response.advisor_version == "deterministic-unified-v1+feedback-bayes-v1"
    assert "boundary_lexical_profile" in response.analysis.reason_codes
    with pytest.raises(TypeError, match="policy_version"):
        Advisor(policy_version="v3")  # type: ignore[call-arg]


def test_ineligible_catalog_item_does_not_change_existing_recommendations() -> None:
    request = request_for("Draft a concise welcome email")
    base = Advisor().recommend(request)
    ineligible = dict(BUILTIN_CATALOG.configurations[0])
    ineligible.update(
        {
            "configuration_id": "zz-ineligible-test-candidate",
            "model_id": "ineligible-test-candidate",
            "display_name": "Ineligible test candidate",
            "capabilities": [],
            "input_usd_per_million": 999.0,
            "output_usd_per_million": 999.0,
            "latency_ms": 99_999.0,
            "quality": {key: 0.01 for key in ineligible["quality"]},
        }
    )
    expanded_catalog = replace(
        BUILTIN_CATALOG,
        configurations=BUILTIN_CATALOG.configurations + (ineligible,),
    )
    expanded = Advisor(catalog=expanded_catalog).recommend(request)
    base_scores = {
        item.configuration.configuration_id: item.score for item in base.recommendations
    }
    expanded_scores = {
        item.configuration.configuration_id: item.score
        for item in expanded.recommendations
        if item.configuration.configuration_id in base_scores
    }
    assert expanded_scores == base_scores
    assert [item.configuration.configuration_id for item in expanded.recommendations] == [
        item.configuration.configuration_id for item in base.recommendations
    ]


def test_unified_policy_keeps_hard_privacy_budget_latency_and_capability_authority() -> None:
    advisor = Advisor()
    local = advisor.recommend(
        request_for(
            "Debug this Python function and protect synthetic SSN 123-45-6789",
            privacy=Privacy.LOCAL_ONLY,
            max_cost_usd=0,
        )
    )
    assert all(item.configuration.deployment == "local" for item in local.recommendations)
    assert all(item.cost.expected == 0 for item in local.recommendations)
    assert "code" in local.analysis.required_capabilities
    assert "us_ssn_like" in local.analysis.privacy_flags

    fast = advisor.recommend(
        request_for("Draft a concise welcome email", latency_slo_ms=1_000)
    )
    assert all(item.latency.expected <= 1_000 for item in fast.recommendations)

    with pytest.raises(ValueError, match="No catalog configuration"):
        advisor.recommend(request_for("Draft a concise welcome email", min_quality=1.0))


def test_configuration_id_breaks_exact_score_ties_stably() -> None:
    first = dict(BUILTIN_CATALOG.configurations[-2])
    second = dict(first)
    first.update(
        {
            "configuration_id": "a-identical-candidate",
            "model_id": "identical-a",
            "display_name": "Identical candidate A",
        }
    )
    second.update(
        {
            "configuration_id": "b-identical-candidate",
            "model_id": "identical-b",
            "display_name": "Identical candidate B",
        }
    )
    catalog = replace(BUILTIN_CATALOG, configurations=(second, first))
    response = Advisor(catalog=catalog).recommend(request_for("Draft a concise welcome email"))
    assert response.recommendations[0].configuration.configuration_id == (
        "a-identical-candidate"
    )
