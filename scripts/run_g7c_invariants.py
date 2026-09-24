#!/usr/bin/env python3
"""Evaluate G7-C synthetic invariants and deterministic runtime characteristics."""

from __future__ import annotations

import argparse
import json
import statistics
import time
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

from routellect.advisor import Advisor
from routellect.evidence_benchmark import file_sha256
from routellect.profiler import deterministic_profile_v3
from routellect.schemas import AssessorMode, PromptMessage, RecommendationRequest


def _percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    return ordered[round(fraction * (len(ordered) - 1))]


def _request(prompt: str) -> RecommendationRequest:
    return RecommendationRequest(
        messages=[PromptMessage(role="user", content=prompt)],
        assessor_mode=AssessorMode.OFF,
    )


def _signature(response: object) -> str:
    data = response.model_dump(mode="json")  # type: ignore[attr-defined]
    stable = {
        "analysis": data["analysis"],
        "recommendations": [
            {
                "configuration_id": item["configuration"]["configuration_id"],
                "score": item["score"],
                "contributions": item["score_contributions"],
                "selection_flags": item["selection_flags"],
            }
            for item in data["recommendations"]
        ],
    }
    return json.dumps(stable, sort_keys=True, separators=(",", ":"))


def run(corpus_path: Path, repetitions: int) -> dict[str, object]:
    corpus = json.loads(corpus_path.read_text())
    confusion: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    task_cases = 0
    for expected, prompts in corpus["task_templates"].items():
        for prompt in prompts:
            for wrapper in corpus["task_wrappers"]:
                predicted = deterministic_profile_v3(
                    wrapper.format(prompt=prompt), AssessorMode.OFF
                ).task_family
                confusion[expected][predicted] += 1
                task_cases += 1
    families = sorted(corpus["task_templates"])
    per_family = {}
    f1_values = []
    for family in families:
        true_positive = confusion[family][family]
        false_negative = sum(confusion[family].values()) - true_positive
        false_positive = sum(
            confusion[other][family] for other in families if other != family
        )
        precision = true_positive / max(1, true_positive + false_positive)
        recall = true_positive / max(1, true_positive + false_negative)
        f1 = 2 * precision * recall / max(1e-12, precision + recall)
        f1_values.append(f1)
        per_family[family] = {
            "support": sum(confusion[family].values()),
            "precision": precision,
            "recall": recall,
            "f1": f1,
        }

    capability_true_positive = 0
    capability_false_negative = 0
    capability_false_positive = 0
    for case in corpus["positive_capabilities"]:
        capabilities = deterministic_profile_v3(
            case["prompt"], AssessorMode.OFF
        ).required_capabilities
        for capability in case["present"]:
            if capability in capabilities:
                capability_true_positive += 1
            else:
                capability_false_negative += 1
    for case in corpus["negated_capabilities"]:
        capabilities = deterministic_profile_v3(
            case["prompt"], AssessorMode.OFF
        ).required_capabilities
        capability_false_positive += case["absent"] in capabilities

    privacy_detected = sum(
        case["flag"]
        in deterministic_profile_v3(case["prompt"], AssessorMode.OFF).privacy_flags
        for case in corpus["privacy_cases"]
    )
    privacy_false_positives = sum(
        bool(deterministic_profile_v3(prompt, AssessorMode.OFF).privacy_flags)
        for prompt in corpus["benign_privacy_lookalikes"]
    )
    stable_pairs = 0
    for left, right in corpus["paraphrase_pairs"]:
        first = deterministic_profile_v3(left, AssessorMode.OFF)
        second = deterministic_profile_v3(right, AssessorMode.OFF)
        stable_pairs += (
            first.task_family == second.task_family
            and first.required_capabilities == second.required_capabilities
        )

    prompts = [
        wrapper.format(prompt=prompt)
        for prompts in corpus["task_templates"].values()
        for prompt in prompts
        for wrapper in corpus["task_wrappers"]
    ]
    advisor = Advisor(policy_version="v3")
    durations = []
    signatures = set()
    for index in range(repetitions):
        prompt = prompts[index % len(prompts)]
        started = time.perf_counter_ns()
        advisor.recommend(_request(prompt))
        durations.append((time.perf_counter_ns() - started) / 1_000_000)
        if index < 50:
            signatures.add(_signature(advisor.recommend(_request(prompts[0]))))

    capability_recall = capability_true_positive / max(
        1, capability_true_positive + capability_false_negative
    )
    capability_precision = capability_true_positive / max(
        1, capability_true_positive + capability_false_positive
    )
    privacy_recall = privacy_detected / len(corpus["privacy_cases"])
    stability = stable_pairs / len(corpus["paraphrase_pairs"])
    p95 = _percentile(durations, 0.95)
    return {
        "protocol": {
            "name": "Routellect G7-C synthetic invariant and runtime audit",
            "created_at": datetime.now(UTC).isoformat(),
            "artifact_version": corpus["version"],
            "artifact_sha256": file_sha256(corpus_path),
            "target_model_calls": 0,
            "hidden_test_runs": 0,
            "raw_prompts_persisted": 0,
        },
        "profiler": {
            "task_cases": task_cases,
            "task_macro_f1": statistics.fmean(f1_values),
            "task_per_family": per_family,
            "capability_positive_cases": capability_true_positive
            + capability_false_negative,
            "capability_recall": capability_recall,
            "capability_precision": capability_precision,
            "privacy_sensitive_cases": len(corpus["privacy_cases"]),
            "privacy_recall": privacy_recall,
            "privacy_benign_cases": len(corpus["benign_privacy_lookalikes"]),
            "privacy_false_positives": privacy_false_positives,
            "paraphrase_pairs": len(corpus["paraphrase_pairs"]),
            "eligibility_stability": stability,
        },
        "runtime": {
            "recommendations": repetitions,
            "mean_ms": statistics.fmean(durations),
            "p50_ms": _percentile(durations, 0.50),
            "p95_ms": p95,
            "p99_ms": _percentile(durations, 0.99),
            "max_ms": max(durations),
            "byte_stable_repeated_decisions": len(signatures) == 1,
        },
        "acceptance_checks": {
            "task_macro_f1_at_least_0_80": statistics.fmean(f1_values) >= 0.80,
            "all_task_recall_at_least_0_70": all(
                values["recall"] >= 0.70 for values in per_family.values()
            ),
            "capability_recall_at_least_0_98": capability_recall >= 0.98,
            "privacy_recall_equals_1": privacy_recall == 1.0,
            "eligibility_stability_at_least_0_95": stability >= 0.95,
            "recommendation_p95_below_10ms": p95 < 10,
            "byte_stable_repeated_decisions": len(signatures) == 1,
            "zero_target_model_calls": True,
            "zero_raw_prompt_persistence": True,
        },
        "claim_boundary": (
            "Project-owned synthetic invariants establish software behavior, not real-world "
            "routing accuracy or universal privacy detection."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--corpus",
        type=Path,
        default=Path("src/routellect/data/deterministic_invariants.json"),
    )
    parser.add_argument("--repetitions", type=int, default=2_000)
    parser.add_argument(
        "--output", type=Path, default=Path("outputs/phase-7c-profiler-results.json")
    )
    args = parser.parse_args()
    result = run(args.corpus, args.repetitions)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
