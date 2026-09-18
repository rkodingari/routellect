from __future__ import annotations

import statistics
import time
from datetime import UTC, datetime
from uuid import uuid4

from routellect.advisor import Advisor
from routellect.schemas import (
    AssessorMode,
    BenchmarkRun,
    BenchmarkRunRequest,
    PromptMessage,
    RecommendationRequest,
)

FIXTURES = (
    ("Summarize this quarterly report into five key points.", "summarization"),
    ("Debug this Python async function and explain the race condition.", "code"),
    ("Prove that the square root of two is irrational.", "reasoning"),
    ("Research current battery recycling methods and cite primary sources.", "research"),
    ("Write a warm but concise customer apology email.", "writing"),
    ("Extract entities into a strict JSON schema.", "extraction"),
    ("Use browser tools to complete a multi-step workflow.", "agent"),
)


def run_builtin_benchmark(request: BenchmarkRunRequest, advisor: Advisor) -> BenchmarkRun:
    started = datetime.now(UTC)
    latencies: list[float] = []
    matches = 0
    pareto_primaries = 0
    specialist_coverage = 0
    contribution_errors: list[float] = []
    confidences: list[float] = []
    advisor_version = "unknown"
    for prompt, expected_task in FIXTURES:
        tick = time.perf_counter()
        response = advisor.recommend(
            RecommendationRequest(
                messages=[PromptMessage(role="user", content=prompt)],
                assessor_mode=AssessorMode.OFF,
            )
        )
        latencies.append((time.perf_counter() - tick) * 1000)
        matches += int(response.analysis.task_family == expected_task)
        advisor_version = response.advisor_version
        primary = response.recommendations[0]
        pareto_primaries += int(primary.pareto_efficient)
        has_guard = any(
            "specialist_recall_guard" in item.selection_flags
            for item in response.recommendations
        )
        shortlist_quality_leader = max(
            response.recommendations, key=lambda item: item.quality.expected
        )
        specialist_coverage += int(has_guard or shortlist_quality_leader.rank == 1)
        for item in response.recommendations:
            contribution_errors.append(
                abs(item.score - sum(part.value for part in item.score_contributions))
            )
            confidences.append(item.confidence)
    completed = datetime.now(UTC)
    ordered = sorted(latencies)
    p95_index = max(0, min(len(ordered) - 1, round(0.95 * len(ordered)) - 1))
    return BenchmarkRun(
        run_id=f"run_{uuid4().hex}",
        status="completed",
        created_at=started,
        completed_at=completed,
        metrics={
            "fixture_count": len(FIXTURES),
            "task_family_accuracy": matches / len(FIXTURES),
            "primary_pareto_rate": pareto_primaries / len(FIXTURES),
            "specialist_shortlist_coverage": specialist_coverage / len(FIXTURES),
            "score_reconciliation_max_error": max(contribution_errors, default=0),
            "confidence_min": min(confidences, default=0),
            "confidence_max": max(confidences, default=0),
            "advisor_latency_mean_ms": round(statistics.mean(latencies), 3),
            "advisor_latency_p95_ms": round(ordered[p95_index], 3),
            "target_provider_calls": 0,
            "raw_prompts_persisted": 0,
            "mode": "software_simulation",
            "advisor_version": advisor_version,
            "evidence_snapshot_id": request.evidence_snapshot_id,
            "split": request.split,
            "seed": request.seed,
        },
    )
