#!/usr/bin/env python3
"""Acquire and overlap-screen the prompt-only G7-E evaluation snapshot."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

from g7e_common import (
    DATASET_ID,
    DECLARED_LICENSE,
    END_PROMPT_ID,
    EXPECTED_ROWS,
    REVISION,
    SOURCES,
    START_PROMPT_ID,
    canonical_sha256,
    file_sha256,
    normalized_prompt,
    source_url,
    stream_source_rows,
    trigram_hashes,
    word_tokens,
)

MIN_FUZZY_TOKENS = 12
JACCARD_THRESHOLD = 0.82
CONTAINMENT_THRESHOLD = 0.92
MIN_LENGTH_RATIO = 0.50
RAREST_POSTINGS = 10


def _jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def _reference_prompts(root: Path) -> list[tuple[str, str]]:
    references: list[tuple[str, str]] = []
    for relative, label, field in (
        ("work/g5-r2/r2_subset.jsonl", "r2_g5", "original_prompt"),
        ("work/g7-evidence/development.jsonl", "r2_g7_development", "original_prompt"),
        ("work/g7-evidence/validation.jsonl", "r2_g7_validation", "original_prompt"),
        (
            "work/g7c2-evidence/routellm-development.jsonl",
            "routellm_g7c2",
            "prompt",
        ),
    ):
        for row in _jsonl(root / relative):
            references.append((str(row[field]), label))
    return references


def _screen(
    prompts: list[dict[str, str]], references: list[tuple[str, str]]
) -> tuple[list[dict[str, str]], list[dict[str, object]], dict[str, object]]:
    exact_references: dict[str, str] = {}
    reference_features: list[tuple[frozenset[int], int, str]] = []
    posting: dict[int, list[int]] = defaultdict(list)
    for text, source in references:
        exact_references.setdefault(canonical_sha256(text), source)
        tokens = word_tokens(text)
        shingles = trigram_hashes(tokens) if len(tokens) >= MIN_FUZZY_TOKENS else frozenset()
        index = len(reference_features)
        reference_features.append((shingles, len(tokens), source))
        for shingle in shingles:
            posting[shingle].append(index)

    unique: dict[str, dict[str, str]] = {}
    intra_duplicates: list[dict[str, object]] = []
    for row in sorted(prompts, key=lambda item: int(item["prompts_id"])):
        canonical = canonical_sha256(row["original_prompt"])
        if canonical in unique:
            intra_duplicates.append(
                {
                    "key": row["key"],
                    "prompts_id": row["prompts_id"],
                    "reason": "evaluation_exact_duplicate",
                    "kept_prompts_id": unique[canonical]["prompts_id"],
                }
            )
        else:
            unique[canonical] = row

    eligible: list[dict[str, str]] = []
    excluded = list(intra_duplicates)
    fuzzy_candidates_checked = 0
    for canonical, row in unique.items():
        if canonical in exact_references:
            excluded.append(
                {
                    "key": row["key"],
                    "prompts_id": row["prompts_id"],
                    "reason": "development_exact_overlap",
                    "reference_source": exact_references[canonical],
                }
            )
            continue
        tokens = word_tokens(row["original_prompt"])
        shingles = trigram_hashes(tokens) if len(tokens) >= MIN_FUZZY_TOKENS else frozenset()
        candidate_indices: set[int] = set()
        ranked_postings = sorted(
            (posting[shingle] for shingle in shingles if shingle in posting),
            key=lambda values: (len(values), values[0]),
        )
        for values in ranked_postings[:RAREST_POSTINGS]:
            candidate_indices.update(values)

        match: dict[str, object] | None = None
        for index in sorted(candidate_indices):
            reference_shingles, reference_length, source = reference_features[index]
            fuzzy_candidates_checked += 1
            intersection = len(shingles & reference_shingles)
            union = len(shingles | reference_shingles)
            jaccard = intersection / union if union else 0.0
            containment = intersection / min(len(shingles), len(reference_shingles))
            length_ratio = min(len(tokens), reference_length) / max(len(tokens), reference_length)
            if jaccard >= JACCARD_THRESHOLD or (
                containment >= CONTAINMENT_THRESHOLD
                and length_ratio >= MIN_LENGTH_RATIO
            ):
                match = {
                    "key": row["key"],
                    "prompts_id": row["prompts_id"],
                    "reason": "development_fuzzy_overlap",
                    "reference_source": source,
                    "trigram_jaccard": jaccard,
                    "trigram_containment": containment,
                    "token_length_ratio": length_ratio,
                }
                break
        if match is None:
            eligible.append(row)
        else:
            excluded.append(match)

    diagnostics = {
        "input_rows": len(prompts),
        "reference_rows": len(references),
        "unique_evaluation_canonical_prompts": len(unique),
        "eligible_rows": len(eligible),
        "excluded_rows": len(excluded),
        "fuzzy_candidates_checked": fuzzy_candidates_checked,
        "exclusion_counts": {
            reason: sum(item["reason"] == reason for item in excluded)
            for reason in sorted({str(item["reason"]) for item in excluded})
        },
    }
    return eligible, excluded, diagnostics


def acquire(root: Path, output_dir: Path) -> dict[str, object]:
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"{output_dir} must be absent or empty")
    output_dir.mkdir(parents=True, exist_ok=True)
    source_model = "Qwen3-0.6B"
    source_path = SOURCES[source_model]
    prompts = []
    print("Acquiring prompt-only G7-E snapshot from the pinned source...", flush=True)
    for source in stream_source_rows(source_path):
        prompt = normalized_prompt(source["original_prompt"])
        key = source["key"].strip()
        if not key or not prompt:
            raise ValueError("source contains an empty key or prompt")
        prompts.append(
            {
                "key": key,
                "prompts_id": source["prompts_id"].strip(),
                "original_prompt": prompt,
            }
        )
    if len(prompts) != EXPECTED_ROWS:
        raise ValueError("prompt snapshot row count is invalid")

    references = _reference_prompts(root)
    eligible, excluded, diagnostics = _screen(prompts, references)
    prompt_path = output_dir / "eligible-prompts.jsonl"
    with prompt_path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in eligible:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    exclusion_path = output_dir / "overlap-exclusions.jsonl"
    with exclusion_path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in sorted(excluded, key=lambda item: int(str(item["prompts_id"]))):
            handle.write(json.dumps(row, sort_keys=True) + "\n")

    manifest = {
        "schema_version": "routellect-g7e-prompts-v1",
        "created_at": datetime.now(UTC).isoformat(),
        "dataset_id": DATASET_ID,
        "dataset_revision": REVISION,
        "declared_license": DECLARED_LICENSE,
        "source_model": source_model,
        "source_path": source_path,
        "source_url": source_url(source_path),
        "source_prompt_ids_inclusive": [START_PROMPT_ID, END_PROMPT_ID],
        "transport_tls_verification": False,
        "outcome_fields_exposed_to_recommendation_process": False,
        "outcome_fields_persisted": False,
        "raw_responses_persisted": False,
        "old_hidden_partition_loaded_from_local_evidence": False,
        "screening": {
            "canonicalization": "Unicode NFKC + casefold + control-to-space + whitespace collapse",
            "minimum_fuzzy_tokens": MIN_FUZZY_TOKENS,
            "jaccard_threshold": JACCARD_THRESHOLD,
            "containment_threshold": CONTAINMENT_THRESHOLD,
            "minimum_length_ratio": MIN_LENGTH_RATIO,
            "rarest_posting_lists": RAREST_POSTINGS,
            "max_screen_tokens": 2_048,
            **diagnostics,
        },
        "eligible_snapshot": {
            "file": prompt_path.name,
            "rows": len(eligible),
            "sha256": file_sha256(prompt_path),
        },
        "exclusion_snapshot": {
            "file": exclusion_path.name,
            "rows": len(excluded),
            "sha256": file_sha256(exclusion_path),
            "contains_prompts": False,
        },
        "recommendations_committed": False,
        "outcomes_joined": False,
        "target_model_calls": 0,
    }
    manifest_path = output_dir / "prompt-manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps(diagnostics, indent=2, sort_keys=True), flush=True)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument(
        "--output-dir", type=Path, default=Path("work/g7e-evidence")
    )
    args = parser.parse_args()
    acquire(args.root.resolve(), args.output_dir)


if __name__ == "__main__":
    main()
