#!/usr/bin/env python3
"""Acquire the frozen, content-minimized G7 development and validation evidence."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import subprocess
import sys
import unicodedata
import urllib.parse
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

REVISION = "1b6234647a21705da4c220f339e44fbe72c69bb2"
DATASET_ID = "JiaqiXue/R2-Bench"
DECLARED_LICENSE = "MIT"
ROW_OFFSET = 5_000
ROW_COUNT = 10_000
TOKEN_BUDGET = 100
SPLIT_SALT = "routellect-g7-v1|"
ALLOWED_COLUMNS = (
    "key",
    "prompts_id",
    "original_prompt",
    "actual_token_count",
    "correctness_score",
)
SOURCES = {
    "Qwen3-0.6B": "data/Qwen/Qwen3-0.6B/100_judge.csv",
    "Qwen2.5-Math-1.5B-Instruct": (
        "data/Qwen/Qwen2.5-Math-1.5B-Instruct/100_judge.csv"
    ),
    "Qwen2.5-Math-7B-Instruct": "data/Qwen/Qwen2.5-Math-7B-Instruct/100_judge.csv",
    "Llama-3.1-70B-Instruct": "data/meta-llama/Llama-3.1-70B-Instruct/100_judge.csv",
}


def source_url(path: str) -> str:
    encoded_path = urllib.parse.quote(path, safe="/")
    return (
        f"https://huggingface.co/datasets/{DATASET_ID}/resolve/{REVISION}/"
        f"{encoded_path}?download=true"
    )


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def normalize_prompt(value: str) -> str:
    return unicodedata.normalize("NFC", value).replace("\r\n", "\n").strip()


def prompt_fingerprint(value: object) -> str:
    normalized = unicodedata.normalize("NFC", str(value))
    visible = "".join(
        character
        for character in normalized
        if not character.isspace() and not unicodedata.category(character).startswith("C")
    )
    return hashlib.sha256(visible.encode()).hexdigest()


def stable_split(prompt: str) -> str:
    """Group exact normalized prompt duplicates in the same deterministic partition."""
    group = prompt_fingerprint(prompt)
    digest = hashlib.sha256(f"{SPLIT_SALT}{group}".encode()).digest()
    fraction = int.from_bytes(digest[:8], "big") / 2**64
    if fraction < 0.60:
        return "development"
    if fraction < 0.80:
        return "validation"
    return "hidden_test"


def _read_source(
    model: str, source_path: str, anchor_rows: list[dict[str, object]]
) -> list[dict[str, object]]:
    process = subprocess.Popen(  # noqa: S603
        [
            "curl",
            "-fsSL",
            "--insecure",
            "--retry",
            "3",
            "--connect-timeout",
            "30",
            "--user-agent",
            "Routellect-G7-evidence-acquirer/0.6",
            source_url(source_path),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    rows: list[dict[str, object]] = []
    final_source_index = ROW_OFFSET + ROW_COUNT
    print(
        f"Reading {model} rows {ROW_OFFSET + 1:,}–{final_source_index:,} "
        "from frozen revision...",
        flush=True,
    )
    assert process.stdout is not None
    text = io.TextIOWrapper(process.stdout, encoding="utf-8", newline="")
    try:
        csv.field_size_limit(sys.maxsize)
        reader = csv.DictReader(text)
        missing = set(ALLOWED_COLUMNS) - set(reader.fieldnames or ())
        if missing:
            raise ValueError(f"{model} is missing required columns: {sorted(missing)}")
        for index, source in enumerate(reader, start=1):
            if index <= ROW_OFFSET:
                anchor = anchor_rows[index - 1]
                anchor_model = anchor["models"][model]
                anchored_values = (
                    str(anchor["key"]),
                    str(anchor["prompts_id"]),
                    prompt_fingerprint(anchor["original_prompt"]),
                    int(anchor_model["actual_token_count"]),
                    float(anchor_model["correctness_score"]),
                )
                source_values = (
                    source["key"].strip(),
                    source["prompts_id"].strip(),
                    prompt_fingerprint(normalize_prompt(source["original_prompt"])),
                    int(source["actual_token_count"]),
                    float(source["correctness_score"]),
                )
                if source_values != anchored_values:
                    raise ValueError(
                        f"{model} source row {index} failed the trusted G5 prefix anchor"
                    )
                continue
            if index > final_source_index:
                break
            key = source["key"].strip()
            prompt = normalize_prompt(source["original_prompt"])
            if not key or not prompt:
                raise ValueError(f"{model} source row {index} has an empty key or prompt")
            rows.append(
                {
                    "key": key,
                    "prompts_id": source["prompts_id"].strip(),
                    "original_prompt": prompt,
                    "actual_token_count": int(source["actual_token_count"]),
                    "correctness_score": float(source["correctness_score"]),
                }
            )
            if len(rows) % 1_000 == 0:
                print(f"  retained {len(rows):,}/{ROW_COUNT:,} rows", flush=True)
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)
        text.close()
    if len(rows) != ROW_COUNT:
        assert process.stderr is not None
        detail = process.stderr.read().decode(errors="replace").strip()
        raise ValueError(
            f"{model} returned {len(rows)} rows; expected {ROW_COUNT}. Transport: {detail}"
        )
    return rows


def _write_partition(path: Path, rows: list[dict[str, object]]) -> str:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            retained = {
                "key": row["key"],
                "prompts_id": row["prompts_id"],
                "original_prompt": row["original_prompt"],
                "models": row["models"],
            }
            handle.write(
                json.dumps(retained, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            )
            handle.write("\n")
    return file_sha256(path)


def acquire(output_dir: Path, anchor_path: Path) -> tuple[Path, Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    anchor_rows = [json.loads(line) for line in anchor_path.read_text().splitlines()]
    if len(anchor_rows) != ROW_OFFSET:
        raise ValueError(
            f"trusted G5 anchor contains {len(anchor_rows)} rows; expected {ROW_OFFSET}"
        )
    merged: list[dict[str, object]] | None = None
    source_manifest: list[dict[str, object]] = []
    prompt_mismatches: Counter[str] = Counter()

    for model, source_path in SOURCES.items():
        rows = _read_source(model, source_path, anchor_rows)
        if merged is None:
            merged = [
                {
                    "key": row["key"],
                    "prompts_id": row["prompts_id"],
                    "original_prompt": row["original_prompt"],
                    "prompt_fingerprint": prompt_fingerprint(row["original_prompt"]),
                    "split": stable_split(str(row["original_prompt"])),
                    "models": {},
                }
                for row in rows
            ]
        for index, (target, row) in enumerate(zip(merged, rows, strict=True), start=1):
            if target["key"] != row["key"]:
                raise ValueError(f"unaligned key for {model} at retained row {index}")
            if target["prompts_id"] != row["prompts_id"]:
                raise ValueError(f"unaligned prompts_id for {model} at retained row {index}")
            if target["prompt_fingerprint"] != prompt_fingerprint(row["original_prompt"]):
                target["_alignment_excluded"] = True
                prompt_mismatches[model] += 1
                continue
            target_models = target["models"]
            assert isinstance(target_models, dict)
            target_models[model] = {
                "actual_token_count": row["actual_token_count"],
                "correctness_score": row["correctness_score"],
            }
        source_manifest.append(
            {
                "model": model,
                "path": source_path,
                "url": source_url(source_path),
                "source_window": [ROW_OFFSET + 1, ROW_OFFSET + ROW_COUNT],
                "retained_rows_before_alignment": len(rows),
            }
        )

    assert merged is not None
    aligned = [
        row
        for row in merged
        if not row.get("_alignment_excluded")
        and len(row.get("models", {})) == len(SOURCES)
    ]
    partitions = {
        split: [row for row in aligned if row["split"] == split]
        for split in ("development", "validation", "hidden_test")
    }
    if any(not rows for rows in partitions.values()):
        raise ValueError("stable split produced an empty partition")

    development_path = output_dir / "development.jsonl"
    validation_path = output_dir / "validation.jsonl"
    development_sha = _write_partition(development_path, partitions["development"])
    validation_sha = _write_partition(validation_path, partitions["validation"])

    hidden_commitment = hashlib.sha256()
    for row in sorted(partitions["hidden_test"], key=lambda item: str(item["key"])):
        hidden_commitment.update(str(row["key"]).encode())
        hidden_commitment.update(b"\0")
        hidden_commitment.update(str(row["prompt_fingerprint"]).encode())
        hidden_commitment.update(b"\0")

    duplicate_groups = Counter(str(row["prompt_fingerprint"]) for row in aligned)
    manifest = {
        "schema_version": 1,
        "created_at": datetime.now(UTC).isoformat(),
        "phase": "G7-B",
        "dataset_id": DATASET_ID,
        "dataset_revision": REVISION,
        "declared_license": DECLARED_LICENSE,
        "transport": {
            "tls_verification": False,
            "reason": "development host intercept CA is unavailable to curl",
            "integrity_control": (
                "Every candidate source's first 5,000 allowed-field rows matched the trusted "
                "G5 snapshot before any new row was accepted; source revision and output "
                "snapshot hashes are pinned."
            ),
            "trusted_prefix_rows_per_candidate": ROW_OFFSET,
            "trusted_prefix_snapshot": str(anchor_path),
            "trusted_prefix_snapshot_sha256": file_sha256(anchor_path),
        },
        "token_budget": TOKEN_BUDGET,
        "selection": {
            "source_rows_inclusive": [ROW_OFFSET + 1, ROW_OFFSET + ROW_COUNT],
            "previously_used_g5_rows_excluded": [1, ROW_OFFSET],
        },
        "split": {
            "salt": SPLIT_SALT,
            "group_key": "SHA-256 of visible Unicode-NFC prompt text without whitespace/control",
            "thresholds": {"development": 0.60, "validation": 0.20, "hidden_test": 0.20},
            "counts": {name: len(rows) for name, rows in partitions.items()},
            "exact_duplicate_group_count": sum(
                1 for count in duplicate_groups.values() if count > 1
            ),
        },
        "alignment_check": (
            "exact key and prompts_id; SHA-256 of Unicode-NFC prompt visible-text fingerprint"
        ),
        "source_row_count_per_candidate": ROW_COUNT,
        "aligned_row_count": len(aligned),
        "excluded_rows": len(merged) - len(aligned),
        "prompt_mismatch_count_by_source": dict(sorted(prompt_mismatches.items())),
        "candidate_count": len(SOURCES),
        "candidate_parameter_billions": {
            "Qwen3-0.6B": 0.6,
            "Qwen2.5-Math-1.5B-Instruct": 1.5,
            "Qwen2.5-Math-7B-Instruct": 7.0,
            "Llama-3.1-70B-Instruct": 70.0,
        },
        "allowed_source_columns": list(ALLOWED_COLUMNS),
        "discarded_payloads": [
            "templated_prompt",
            "golden_answer",
            "response",
            "judge_raw",
        ],
        "source_files": source_manifest,
        "persisted_partitions": {
            "development": {
                "file": development_path.name,
                "sha256": development_sha,
                "rows": len(partitions["development"]),
            },
            "validation": {
                "file": validation_path.name,
                "sha256": validation_sha,
                "rows": len(partitions["validation"]),
            },
        },
        "hidden_partition": {
            "rows": len(partitions["hidden_test"]),
            "key_prompt_commitment_sha256": hidden_commitment.hexdigest(),
            "prompts_persisted": False,
            "outcomes_persisted": False,
            "reacquisition": "Pinned sources may be reacquired only after G7-D approval.",
        },
        "target_model_calls": 0,
    }
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(f"Wrote {development_path} ({development_sha})", flush=True)
    print(f"Wrote {validation_path} ({validation_sha})", flush=True)
    print(
        f"Committed {len(partitions['hidden_test']):,} hidden rows "
        "without retaining prompts/outcomes",
        flush=True,
    )
    print(f"Wrote {manifest_path}", flush=True)
    return development_path, validation_path, manifest_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("work/g7-evidence"),
        help="Directory for minimized development/validation snapshots and manifest.",
    )
    parser.add_argument(
        "--trusted-g5-anchor",
        type=Path,
        default=Path("work/g5-r2/r2_subset.jsonl"),
        help="Previously verified 5,000-row snapshot used as a per-source prefix anchor.",
    )
    args = parser.parse_args()
    acquire(args.output_dir, args.trusted_g5_anchor)


if __name__ == "__main__":
    main()
