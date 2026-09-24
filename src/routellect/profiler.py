from __future__ import annotations

import math
import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass

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


@dataclass(frozen=True)
class WeightedTerm:
    term: str
    weight: float = 1.0


V3_TASK_TERMS: dict[str, tuple[WeightedTerm, ...]] = {
    "code": tuple(
        WeightedTerm(term, weight)
        for term, weight in (
            ("debug", 2.0),
            ("refactor", 2.0),
            ("source code", 2.0),
            ("code review", 2.0),
            ("unit test", 1.8),
            ("repository", 1.5),
            ("python", 1.5),
            ("javascript", 1.5),
            ("typescript", 1.5),
            ("rust", 1.5),
            ("sql", 1.5),
            ("function", 1.0),
            ("algorithm", 1.0),
            ("api", 0.8),
        )
    ),
    "reasoning": tuple(
        WeightedTerm(term, weight)
        for term, weight in (
            ("prove", 2.0),
            ("derive", 2.0),
            ("show that", 1.5),
            ("calculate", 1.4),
            ("equation", 1.4),
            ("theorem", 1.7),
            ("mathematical", 1.4),
            ("logic puzzle", 1.8),
            ("optimize", 1.2),
            ("constraint satisfaction", 1.8),
            ("step by step", 1.0),
        )
    ),
    "research": tuple(
        WeightedTerm(term, weight)
        for term, weight in (
            ("research", 1.8),
            ("primary sources", 2.0),
            ("cite sources", 2.0),
            ("literature review", 2.0),
            ("systematic review", 2.0),
            ("compare evidence", 1.8),
            ("market analysis", 1.5),
            ("current evidence", 1.5),
            ("latest", 1.0),
            ("bibliography", 1.5),
        )
    ),
    "writing": tuple(
        WeightedTerm(term, weight)
        for term, weight in (
            ("draft", 1.7),
            ("rewrite", 1.7),
            ("compose", 1.5),
            ("write", 1.0),
            ("tone", 1.2),
            ("story", 1.5),
            ("email", 1.4),
            ("article", 1.2),
            ("cover letter", 1.8),
            ("creative", 1.2),
            ("proofread", 1.5),
        )
    ),
    "summarization": tuple(
        WeightedTerm(term, weight)
        for term, weight in (
            ("summarize", 2.0),
            ("summary", 1.8),
            ("key points", 1.6),
            ("tldr", 2.0),
            ("condense", 1.8),
            ("executive brief", 1.6),
            ("synopsis", 1.6),
        )
    ),
    "extraction": tuple(
        WeightedTerm(term, weight)
        for term, weight in (
            ("extract", 2.0),
            ("classify", 1.5),
            ("parse", 1.5),
            ("entities", 1.5),
            ("sentiment", 1.4),
            ("structured data", 1.7),
            ("json schema", 1.8),
            ("return json", 1.6),
            ("table of", 1.2),
            ("fields", 0.8),
        )
    ),
    "agent": tuple(
        WeightedTerm(term, weight)
        for term, weight in (
            ("agent", 1.7),
            ("use tools", 1.8),
            ("browse", 1.5),
            ("browser", 1.5),
            ("search the web", 1.8),
            ("computer use", 2.0),
            ("workflow", 1.4),
            ("multi-step action", 1.8),
            ("autonomous", 1.5),
            ("function call", 1.5),
        )
    ),
}

V3_CAPABILITY_TERMS: dict[str, tuple[str, ...]] = {
    "vision": ("image", "screenshot", "photo", "diagram", "chart", "visual"),
    "audio": ("audio", "speech", "voice recording", "transcribe", "podcast"),
    "tools": (
        "use tools",
        "browser",
        "browse",
        "search the web",
        "computer use",
        "function call",
        "execute",
    ),
    "structured_output": (
        "json",
        "json schema",
        "xml",
        "csv",
        "structured output",
        "machine readable",
    ),
    "code": (
        "code",
        "python",
        "javascript",
        "typescript",
        "rust",
        "sql",
        "debug",
        "repository",
    ),
    "reasoning": (
        "prove",
        "derive",
        "reason",
        "calculate",
        "theorem",
        "logic puzzle",
        "step by step",
    ),
}

V3_SECRET_PATTERNS = {
    **SECRET_PATTERNS,
    "aws_access_key": re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    "github_token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    "bearer_token": re.compile(r"\bBearer\s+[A-Za-z0-9._~+/-]{20,}=*\b", re.I),
    "us_ssn_like": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
}

TASK_PRIORITY = (
    "agent",
    "code",
    "reasoning",
    "research",
    "extraction",
    "summarization",
    "writing",
)

NEGATION_WORDS = r"(?:no|not|never|without|avoid|skip|disable|exclude|do\s+not|don['’]t)"


def estimate_tokens(text: str) -> int:
    words = len(re.findall(r"\S+", text))
    return max(1, math.ceil(words * 1.35))


def estimate_token_range(text: str) -> tuple[int, int, int]:
    """Conservative dependency-free estimate for prose, code, and non-ASCII input."""
    if not text:
        return (1, 1, 1)
    words = len(re.findall(r"\S+", text))
    characters = len(text)
    punctuation = len(re.findall(r"[{}\[\]();:=<>/\\]", text))
    non_ascii = sum(ord(character) > 127 for character in text)
    code_like = bool(re.search(r"```|\b(?:def|class|function|SELECT|FROM|import)\b", text))
    character_divisor = 3.2 if code_like else 3.8
    if non_ascii / max(1, characters) > 0.15:
        character_divisor = min(character_divisor, 2.6)
    expected = max(
        1,
        math.ceil(words * (1.45 if code_like else 1.30)),
        math.ceil(characters / character_divisor),
    )
    expected += math.ceil(punctuation / 12)
    low = max(1, math.floor(expected * 0.82))
    high = max(expected, math.ceil(expected * 1.30 + 8))
    return (low, expected, high)


def _term_scores(text: str, mapping: dict[str, tuple[str, ...]]) -> dict[str, int]:
    lowered = text.lower()
    scores: dict[str, int] = defaultdict(int)
    for label, terms in mapping.items():
        scores[label] = sum(1 for term in terms if term in lowered)
    return dict(scores)


def _bounded_pattern(term: str) -> re.Pattern[str]:
    escaped = re.escape(term).replace(r"\ ", r"\s+")
    return re.compile(rf"(?<![\w]){escaped}(?![\w])", re.I)


def _negated(text: str, match: re.Match[str]) -> bool:
    prefix = text[max(0, match.start() - 48) : match.start()]
    prefix = re.split(r"[.,;:!?\n]", prefix)[-1]
    return bool(re.search(rf"{NEGATION_WORDS}(?:\W+\w+){{0,3}}\W*$", prefix, re.I))


def _weighted_scores(text: str) -> tuple[dict[str, float], int]:
    scores: dict[str, float] = {}
    negated_matches = 0
    for label, terms in V3_TASK_TERMS.items():
        score = 0.0
        for weighted in terms:
            for match in _bounded_pattern(weighted.term).finditer(text):
                if _negated(text, match):
                    negated_matches += 1
                else:
                    score += weighted.weight
        scores[label] = score
    return scores, negated_matches


def _v3_capabilities(text: str) -> tuple[set[str], int]:
    capabilities = {"text"}
    negated_matches = 0
    for capability, terms in V3_CAPABILITY_TERMS.items():
        positive = False
        for term in terms:
            for match in _bounded_pattern(term).finditer(text):
                if _negated(text, match):
                    negated_matches += 1
                else:
                    positive = True
        if positive:
            capabilities.add(capability)
    return capabilities, negated_matches


def deterministic_profile_v3(text: str, mode: AssessorMode) -> PromptProfile:
    normalized = unicodedata.normalize("NFKC", text)
    scores, task_negations = _weighted_scores(normalized)
    priority = {label: index for index, label in enumerate(TASK_PRIORITY)}
    ranked = sorted(
        scores.items(), key=lambda item: (-item[1], priority.get(item[0], len(priority)))
    )
    best_task, best_score = ranked[0]
    second_task, second_score = ranked[1]
    if best_score == 0:
        best_task = "general"

    _, expected_tokens, conservative_tokens = estimate_token_range(normalized)
    capabilities, capability_negations = _v3_capabilities(normalized)
    if conservative_tokens > 24_000:
        capabilities.add("long_context")

    lowered = normalized.casefold()
    operation_count = sum(
        bool(_bounded_pattern(term).search(normalized))
        for term in (
            "analyze",
            "compare",
            "create",
            "debug",
            "design",
            "evaluate",
            "explain",
            "extract",
            "implement",
            "prove",
            "research",
            "review",
            "summarize",
            "verify",
            "write",
        )
    )
    hard_markers = sum(
        marker in lowered
        for marker in (
            "architecture",
            "edge case",
            "production",
            "rigorous",
            "security",
            "trade-off",
            "validate",
            "verify",
            "multiple constraints",
            "step by step",
        )
    )
    structural_markers = (
        len(re.findall(r"(?m)^\s*(?:[-*]|\d+[.)])\s+", normalized))
        + normalized.count("```")
        + min(3, normalized.count("\n\n"))
    )
    active_tasks = sum(score >= 1.5 for score in scores.values())
    complexity = (
        hard_markers * 2
        + min(operation_count, 4)
        + min(structural_markers, 4)
        + max(0, len(capabilities) - 2)
        + max(0, active_tasks - 1)
    )
    if conservative_tokens > 3_000 or complexity >= 8:
        difficulty = "high"
    elif conservative_tokens > 650 or complexity >= 4:
        difficulty = "medium"
    else:
        difficulty = "low"

    uncertainty = 0.10
    reasons: list[str] = ["v3_boundary_lexical_profile"]
    if best_score == 0:
        uncertainty += 0.50
        reasons.append("unknown_task_family")
    elif second_score > 0:
        margin = (best_score - second_score) / max(best_score, 1.0)
        if margin < 0.20:
            uncertainty += 0.30
            reasons.append("multiple_task_signals")
        elif margin < 0.45:
            uncertainty += 0.15
            reasons.append("secondary_task_signal")
    if len(normalized.strip()) < 28:
        uncertainty += 0.15
        reasons.append("short_prompt")
    negated_matches = task_negations + capability_negations
    if negated_matches:
        uncertainty += min(0.15, 0.04 * negated_matches)
        reasons.append("negated_requirement_detected")
    if active_tasks > 1:
        secondary = [label for label, score in ranked[1:3] if score >= 1.5]
        reasons.extend(f"secondary_task_{label}" for label in secondary)
    if conservative_tokens >= max(64, expected_tokens * 1.2):
        reasons.append("conservative_token_estimate")

    privacy_flags = [
        name for name, pattern in V3_SECRET_PATTERNS.items() if pattern.search(normalized)
    ]
    if privacy_flags:
        reasons.append("sensitive_content_detected")

    return PromptProfile(
        task_family=best_task,
        difficulty=difficulty,
        estimated_input_tokens=conservative_tokens,
        required_capabilities=capabilities,
        privacy_flags=privacy_flags,
        uncertainty=min(1.0, uncertainty),
        reason_codes=list(dict.fromkeys(reasons)),
        assessor=AssessorReport(
            mode=mode,
            invoked=False,
            status="disabled" if mode == AssessorMode.OFF else "not_needed",
            assessor_version="deterministic-profiler-v3",
        ),
    )


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
