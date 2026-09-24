#!/usr/bin/env python3
"""Generate the outcome-blind G7-E recommendation commitment."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from g7e_common import (
    CANDIDATE_PARAMETERS,
    CONTROL_SALT,
    FROZEN_ARTIFACT_SHA256,
    STRONG_MODEL,
    file_sha256,
)

from routellect.profiler import deterministic_profile_v3
from routellect.schemas import AssessorMode
from routellect.sparse_policy import MultiSourceStrengthModel, SparseStrengthModel


def _git(root: Path, *arguments: str) -> str:
    return subprocess.run(  # noqa: S603
        ["git", *arguments],
        cwd=root,
        check=True,
        text=True,
        capture_output=True,
    ).stdout.strip()


def _lower_tier_choice(model: MultiSourceStrengthModel, prompt: str) -> str:
    prediction = model.lower_tier.predict(prompt)
    candidates = [name for name in prediction.predicted_utility if name != STRONG_MODEL]
    return min(
        candidates,
        key=lambda name: (
            -prediction.predicted_utility[name],
            model.lower_tier.parameter_billions[name],
            name,
        ),
    )


def _content_blind(rows: list[dict[str, object]], shares: dict[str, float]) -> list[str]:
    ordered = sorted(
        range(len(rows)),
        key=lambda index: hashlib.sha256(
            f"{CONTROL_SALT}{rows[index]['key']}".encode()
        ).digest(),
    )
    counts = {model: round(share * len(rows)) for model, share in shares.items()}
    largest = max(shares, key=lambda model: (shares[model], model))
    counts[largest] += len(rows) - sum(counts.values())
    choices = [largest] * len(rows)
    cursor = 0
    for model in sorted(counts):
        for index in ordered[cursor : cursor + counts[model]]:
            choices[index] = model
        cursor += counts[model]
    return choices


def commit_recommendations(
    root: Path,
    evidence_dir: Path,
    artifact_path: Path,
    prior_artifact_path: Path,
) -> dict[str, object]:
    output_path = evidence_dir / "recommendations.jsonl"
    manifest_path = evidence_dir / "recommendation-manifest.json"
    if output_path.exists() or manifest_path.exists():
        raise FileExistsError("recommendation commitment already exists")
    tracked_status = _git(root, "status", "--porcelain", "--untracked-files=no")
    if tracked_status:
        raise RuntimeError("tracked source tree must be clean before recommendation commitment")
    source_commit = _git(root, "rev-parse", "HEAD")
    if file_sha256(artifact_path) != FROZEN_ARTIFACT_SHA256:
        raise ValueError("candidate artifact does not match the G7-D freeze")

    prompt_manifest = json.loads((evidence_dir / "prompt-manifest.json").read_text())
    prompt_path = evidence_dir / str(prompt_manifest["eligible_snapshot"]["file"])
    if file_sha256(prompt_path) != prompt_manifest["eligible_snapshot"]["sha256"]:
        raise ValueError("eligible prompt snapshot digest mismatch")
    rows = [json.loads(line) for line in prompt_path.read_text().splitlines() if line]
    artifact = json.loads(artifact_path.read_text())
    candidate = MultiSourceStrengthModel(artifact)
    prior = SparseStrengthModel(json.loads(prior_artifact_path.read_text()))
    committed = []
    for row in rows:
        prompt = str(row["original_prompt"])
        profile = deterministic_profile_v3(prompt, AssessorMode.OFF)
        committed.append(
            {
                "key": row["key"],
                "prompts_id": row["prompts_id"],
                "candidate_model": candidate.choose(prompt),
                "candidate_strong_probability": candidate.strong_probability(prompt),
                "g7c_model": prior.predict(prompt).recommended_model,
                "lower_tier_model": _lower_tier_choice(candidate, prompt),
                "fixed_model": STRONG_MODEL,
                "task_family": profile.task_family,
                "difficulty": profile.difficulty,
            }
        )
    candidate_counts = Counter(str(row["candidate_model"]) for row in committed)
    shares = {
        model: candidate_counts.get(model, 0) / len(committed)
        for model in CANDIDATE_PARAMETERS
    }
    blind = _content_blind(committed, shares)
    for row, model in zip(committed, blind, strict=True):
        row["content_blind_model"] = model

    with output_path.open("x", encoding="utf-8", newline="\n") as handle:
        for row in committed:
            handle.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")
    manifest = {
        "schema_version": "routellect-g7e-recommendations-v1",
        "created_at": datetime.now(UTC).isoformat(),
        "source_commit": source_commit,
        "tracked_source_clean": True,
        "candidate_artifact_sha256": file_sha256(artifact_path),
        "prior_artifact_sha256": file_sha256(prior_artifact_path),
        "prompt_snapshot_sha256": file_sha256(prompt_path),
        "recommendations_file": output_path.name,
        "recommendations_sha256": file_sha256(output_path),
        "rows": len(committed),
        "candidate_recommendation_share": {
            model: count / len(committed)
            for model, count in sorted(candidate_counts.items())
        },
        "content_blind_salt": CONTROL_SALT,
        "raw_prompts_persisted_in_recommendations": False,
        "outcomes_available_during_recommendation": False,
        "recommendations_committed": True,
        "outcomes_joined": False,
        "target_model_calls": 0,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument(
        "--evidence-dir", type=Path, default=Path("work/g7e-evidence")
    )
    parser.add_argument(
        "--artifact",
        type=Path,
        default=Path("src/routellect/data/g7c2_multisource_strength.json"),
    )
    parser.add_argument(
        "--prior-artifact",
        type=Path,
        default=Path("src/routellect/data/g7_sparse_strength.json"),
    )
    args = parser.parse_args()
    commit_recommendations(
        args.root.resolve(), args.evidence_dir, args.artifact, args.prior_artifact
    )


if __name__ == "__main__":
    main()
