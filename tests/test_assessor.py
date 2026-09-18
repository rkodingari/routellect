import json
from importlib.resources import files

from routellect.assessor import LocalAssessor
from routellect.profiler import deterministic_profile
from routellect.schemas import AssessorMode


def test_semantic_prototypes_match_pinned_assessor() -> None:
    artifact = json.loads(
        files("routellect").joinpath("data/assessor_prototypes.json").read_text(encoding="utf-8")
    )
    assert artifact["model_version"].endswith("sha256:48ab3034d0dd")
    assert set(artifact["prototypes"]) == {
        "agent",
        "code",
        "extraction",
        "reasoning",
        "research",
        "summarization",
        "writing",
    }
    assert all(len(vector) == artifact["dimensions"] for vector in artifact["prototypes"].values())


def test_valid_local_assessment_is_conservatively_merged() -> None:
    payload = {
        "task_family": "research",
        "difficulty": "high",
        "required_capabilities": ["text", "tools"],
        "privacy_flags": ["possible_confidential_context"],
        "confidence": 0.91,
        "reason_codes": ["requires_current_sources"],
    }
    assessor = LocalAssessor(backend=lambda _: json.dumps(payload), timeout_seconds=0.5)
    base = deterministic_profile("Help me investigate this", AssessorMode.ALWAYS)
    result = assessor.assess("Help me investigate this", base, AssessorMode.ALWAYS)
    assert result.task_family == "research"
    assert result.difficulty == "high"
    assert "tools" in result.required_capabilities
    assert result.assessor.status == "completed"


def test_invalid_assessment_falls_back_without_prompt_echo() -> None:
    assessor = LocalAssessor(backend=lambda _: "not-json", timeout_seconds=0.5)
    base = deterministic_profile("Help me", AssessorMode.ALWAYS)
    result = assessor.assess("TOP-SECRET-VALUE", base, AssessorMode.ALWAYS)
    assert result.assessor.status == "invalid_output"
    assert result.assessor.fallback_used is True
    assert "TOP-SECRET-VALUE" not in result.model_dump_json()


def test_off_never_invokes_backend() -> None:
    invoked = False

    def backend(_: str) -> str:
        nonlocal invoked
        invoked = True
        return "{}"

    assessor = LocalAssessor(backend=backend)
    base = deterministic_profile("Research this topic", AssessorMode.OFF)
    result = assessor.assess("Research this topic", base, AssessorMode.OFF)
    assert not invoked
    assert result.assessor.status == "disabled"
