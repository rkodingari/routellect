from routellect.profiler import deterministic_profile, estimate_tokens
from routellect.schemas import AssessorMode


def test_profiler_classifies_code_and_capabilities() -> None:
    profile = deterministic_profile(
        "Debug this Python API and return a strict JSON schema.", AssessorMode.OFF
    )
    assert profile.task_family == "code"
    assert {"text", "code", "structured_output"} <= profile.required_capabilities
    assert profile.assessor.status == "disabled"


def test_short_unknown_prompt_triggers_uncertainty() -> None:
    profile = deterministic_profile("Help me", AssessorMode.AUTO)
    assert profile.uncertainty >= 0.55
    assert "unknown_task_family" in profile.reason_codes


def test_token_estimate_never_returns_zero() -> None:
    assert estimate_tokens("") == 1
