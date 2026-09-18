from __future__ import annotations

import math
import re
from collections import defaultdict

from routellect.schemas import AssessorMode, AssessorReport, PromptProfile

TASK_TERMS: dict[str, tuple[str, ...]] = {
    "code": (
        "code",
        "python",
        "javascript",
        "typescript",
        "rust",
        "sql",
        "debug",
        "refactor",
        "repository",
        "function",
        "api",
    ),
    "reasoning": (
        "prove",
        "derive",
        "calculate",
        "equation",
        "math",
        "logic",
        "reason step",
        "optimize",
        "constraint",
    ),
    "research": (
        "research",
        "sources",
        "cite",
        "literature",
        "compare evidence",
        "market analysis",
        "latest",
    ),
    "writing": (
        "write",
        "rewrite",
        "draft",
        "tone",
        "story",
        "email",
        "article",
        "creative",
    ),
    "summarization": ("summarize", "summary", "key points", "tldr", "condense"),
    "extraction": (
        "extract",
        "classify",
        "json",
        "schema",
        "entities",
        "sentiment",
        "table",
    ),
    "agent": (
        "agent",
        "tools",
        "browser",
        "computer use",
        "workflow",
        "multi-step",
        "autonomous",
    ),
}

CAPABILITY_TERMS: dict[str, tuple[str, ...]] = {
    "vision": ("image", "screenshot", "photo", "diagram", "chart"),
    "audio": ("audio", "speech", "voice", "transcribe"),
    "tools": ("tool", "browser", "search the web", "computer use", "function call"),
    "structured_output": ("json", "schema", "xml", "csv", "structured output"),
    "code": ("code", "python", "javascript", "typescript", "rust", "sql", "debug"),
    "reasoning": ("prove", "derive", "reason", "calculate", "complex", "plan"),
}

SECRET_PATTERNS = {
    "api_key_like": re.compile(r"\b(?:sk|key|token)[-_][A-Za-z0-9_-]{12,}\b", re.I),
    "private_key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "email": re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I),
}


def estimate_tokens(text: str) -> int:
    words = len(re.findall(r"\S+", text))
    return max(1, math.ceil(words * 1.35))


def _term_scores(text: str, mapping: dict[str, tuple[str, ...]]) -> dict[str, int]:
    lowered = text.lower()
    scores: dict[str, int] = defaultdict(int)
    for label, terms in mapping.items():
        scores[label] = sum(1 for term in terms if term in lowered)
    return dict(scores)


def deterministic_profile(text: str, mode: AssessorMode) -> PromptProfile:
    task_scores = _term_scores(text, TASK_TERMS)
    ranked = sorted(task_scores.items(), key=lambda item: (-item[1], item[0]))
    best_task, best_score = ranked[0] if ranked else ("general", 0)
    second_score = ranked[1][1] if len(ranked) > 1 else 0
    if best_score == 0:
        best_task = "general"

    tokens = estimate_tokens(text)
    complexity_markers = sum(
        marker in text.lower()
        for marker in (
            "multi-step",
            "trade-off",
            "architecture",
            "production",
            "edge case",
            "rigorous",
        )
    )
    if tokens > 2_500 or complexity_markers >= 3 or best_score >= 5:
        difficulty = "high"
    elif tokens > 500 or complexity_markers >= 1 or best_score >= 2:
        difficulty = "medium"
    else:
        difficulty = "low"

    ambiguity = 0.15
    reasons: list[str] = []
    if best_score == 0:
        ambiguity += 0.45
        reasons.append("unknown_task_family")
    if best_score > 0 and best_score - second_score <= 1 and second_score > 0:
        ambiguity += 0.25
        reasons.append("multiple_task_signals")
    if len(text.strip()) < 28:
        ambiguity += 0.2
        reasons.append("short_prompt")
    if "?" not in text and not re.search(
        r"\b(write|create|build|explain|review|find|compare)\b", text, re.I
    ):
        ambiguity += 0.1
        reasons.append("weak_intent_signal")

    capability_scores = _term_scores(text, CAPABILITY_TERMS)
    capabilities = {"text"} | {key for key, value in capability_scores.items() if value > 0}
    if tokens > 24_000:
        capabilities.add("long_context")
    privacy_flags = [name for name, pattern in SECRET_PATTERNS.items() if pattern.search(text)]
    if privacy_flags:
        reasons.append("sensitive_content_detected")

    return PromptProfile(
        task_family=best_task,
        difficulty=difficulty,
        estimated_input_tokens=tokens,
        required_capabilities=capabilities,
        privacy_flags=privacy_flags,
        uncertainty=min(1.0, ambiguity),
        reason_codes=reasons or ["clear_deterministic_profile"],
        assessor=AssessorReport(
            mode=mode,
            invoked=False,
            status="disabled" if mode == AssessorMode.OFF else "not_needed",
        ),
    )
