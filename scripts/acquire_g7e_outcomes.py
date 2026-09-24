#!/usr/bin/env python3
"""Acquire minimized outcomes after the G7-E recommendation commitment exists."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from g7e_common import (
    DATASET_ID,
    DECLARED_LICENSE,
    REVISION,
    SOURCES,
    file_sha256,
    source_url,
    stream_source_rows,
)


def acquire(evidence_dir: Path) -> dict[str, object]:
    outcome_path = evidence_dir / "outcomes.jsonl"
    manifest_path = evidence_dir / "outcome-manifest.json"
    if outcome_path.exists() or manifest_path.exists():
        raise FileExistsError("outcome snapshot already exists; refusing a second acquisition")

    recommendation_manifest_path = evidence_dir / "recommendation-manifest.json"
    recommendation_manifest = json.loads(recommendation_manifest_path.read_text())
    if recommendation_manifest["recommendations_committed"] is not True:
        raise ValueError("recommendations are not committed")
    recommendation_path = evidence_dir / str(
        recommendation_manifest["recommendations_file"]
    )
    if file_sha256(recommendation_path) != recommendation_manifest["recommendations_sha256"]:
        raise ValueError("recommendation commitment digest mismatch")
    recommendations = [
        json.loads(line) for line in recommendation_path.read_text().splitlines() if line
    ]
    expected = {
        int(row["prompts_id"]): {"key": str(row["key"]), "models": {}}
        for row in recommendations
    }
    if len(expected) != len(recommendations):
        raise ValueError("recommendation prompt IDs are not unique")

    source_files = []
    for model, source_path in SOURCES.items():
        print(f"Acquiring minimized outcomes for {model}...", flush=True)
        retained = 0
        for source in stream_source_rows(source_path):
            prompt_id = int(source["prompts_id"])
            target = expected.get(prompt_id)
            if target is None:
                continue
            key = source["key"].strip()
            if key != target["key"]:
                raise ValueError(f"cross-model key mismatch for prompt ID {prompt_id}")
            models = target["models"]
            assert isinstance(models, dict)
            models[model] = {
                "actual_token_count": int(source["actual_token_count"]),
                "correctness_score": float(source["correctness_score"]),
            }
            retained += 1
        if retained != len(expected):
            raise ValueError(
                f"{model} retained {retained} eligible rows; expected {len(expected)}"
            )
        source_files.append(
            {
                "model": model,
                "path": source_path,
                "url": source_url(source_path),
                "eligible_rows": retained,
            }
        )

    with outcome_path.open("x", encoding="utf-8", newline="\n") as handle:
        for prompt_id, row in sorted(expected.items()):
            models = row["models"]
            if not isinstance(models, dict) or set(models) != set(SOURCES):
                raise ValueError(f"incomplete aligned outcomes for prompt ID {prompt_id}")
            retained = {
                "key": row["key"],
                "prompts_id": str(prompt_id),
                "models": models,
            }
            handle.write(json.dumps(retained, sort_keys=True, separators=(",", ":")) + "\n")

    manifest = {
        "schema_version": "routellect-g7e-outcomes-v1",
        "created_at": datetime.now(UTC).isoformat(),
        "dataset_id": DATASET_ID,
        "dataset_revision": REVISION,
        "declared_license": DECLARED_LICENSE,
        "recommendations_sha256": recommendation_manifest["recommendations_sha256"],
        "recommendations_created_at": recommendation_manifest["created_at"],
        "recommendations_committed_before_outcomes": True,
        "source_files": source_files,
        "transport_tls_verification": False,
        "outcomes_file": outcome_path.name,
        "outcomes_sha256": file_sha256(outcome_path),
        "rows": len(expected),
        "retained_fields": [
            "key",
            "prompts_id",
            "actual_token_count",
            "correctness_score",
        ],
        "raw_prompts_persisted": False,
        "raw_responses_persisted": False,
        "golden_answers_persisted": False,
        "judge_rationales_persisted": False,
        "target_model_calls": 0,
        "evaluation_runs": 0,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--evidence-dir", type=Path, default=Path("work/g7e-evidence")
    )
    args = parser.parse_args()
    acquire(args.evidence_dir)


if __name__ == "__main__":
    main()
