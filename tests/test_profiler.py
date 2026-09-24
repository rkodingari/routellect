import json
from pathlib import Path

from routellect.profiler import (
    deterministic_profile,
    estimate_token_range,
)
from routellect.schemas import AssessorMode

INVARIANTS = Path("src/routellect/data/deterministic_invariants.json")


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


def test_token_estimate_is_positive_and_monotonic() -> None:
    empty = estimate_token_range("")
    short = estimate_token_range("A short sentence.")
    longer = estimate_token_range("A short sentence with additional context and constraints.")
    assert empty[2] >= 1
    assert short[2] <= longer[2]


def test_unified_reviewed_task_matrix_has_at_least_300_cases() -> None:
    corpus = json.loads(INVARIANTS.read_text())
    wrappers = corpus["task_wrappers"]
    cases = [
        (family, wrapper.format(prompt=prompt))
        for family, prompts in corpus["task_templates"].items()
        for prompt in prompts
        for wrapper in wrappers
    ]
    assert len(cases) >= 300
    errors = [
        (expected, prompt, deterministic_profile(prompt, AssessorMode.OFF).task_family)
        for expected, prompt in cases
        if deterministic_profile(prompt, AssessorMode.OFF).task_family != expected
    ]
    assert errors == []


def test_unified_boundaries_negation_and_capabilities() -> None:
    corpus = json.loads(INVARIANTS.read_text())
    for prompt in corpus["substring_traps"]:
        profile = deterministic_profile(prompt, AssessorMode.OFF)
        assert "code" not in profile.required_capabilities
    for case in corpus["negated_capabilities"]:
        profile = deterministic_profile(case["prompt"], AssessorMode.OFF)
        assert case["absent"] not in profile.required_capabilities
    for case in corpus["positive_capabilities"]:
        profile = deterministic_profile(case["prompt"], AssessorMode.OFF)
        assert set(case["present"]) <= profile.required_capabilities


def test_unified_privacy_recall_and_benign_lookalikes() -> None:
    corpus = json.loads(INVARIANTS.read_text())
    for case in corpus["privacy_cases"]:
        profile = deterministic_profile(case["prompt"], AssessorMode.OFF)
        assert case["flag"] in profile.privacy_flags
    for prompt in corpus["benign_privacy_lookalikes"]:
        assert deterministic_profile(prompt, AssessorMode.OFF).privacy_flags == []


def test_unified_paraphrases_keep_task_and_capability_eligibility() -> None:
    corpus = json.loads(INVARIANTS.read_text())
    stable = 0
    for left, right in corpus["paraphrase_pairs"]:
        first = deterministic_profile(left, AssessorMode.OFF)
        second = deterministic_profile(right, AssessorMode.OFF)
        stable += (
            first.task_family == second.task_family
            and first.required_capabilities == second.required_capabilities
        )
    assert stable / len(corpus["paraphrase_pairs"]) >= 0.95


def test_unified_conservative_token_estimate_handles_code_and_unicode() -> None:
    prose = estimate_token_range("A short sentence with ordinary prose.")
    code = estimate_token_range("def f(x):\n    return {'value': x + 1}")
    unicode = estimate_token_range("请总结这段文字并说明关键结论。")
    for low, expected, high in (prose, code, unicode):
        assert 1 <= low <= expected <= high
    assert code[2] > prose[2]
    assert unicode[1] >= 5
