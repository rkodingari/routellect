#!/usr/bin/env python3
"""Acquire the preregistered, privacy-minimized R2-Bench evidence snapshot."""

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
LICENSE = "MIT"
ROW_LIMIT = 5_000
TOKEN_BUDGET = 100
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


def _source_url(path: str) -> str:
    encoded_path = urllib.parse.quote(path, safe="/")
    return (
        f"https://huggingface.co/datasets/{DATASET_ID}/resolve/{REVISION}/"
        f"{encoded_path}?download=true"
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _normalize_prompt(value: str) -> str:
    return unicodedata.normalize("NFC", value).replace("\r\n", "\n").strip()


def _prompt_alignment_fingerprint(value: object) -> str:
    normalized = unicodedata.normalize("NFC", str(value))
    return "".join(
        character
        for character in normalized
        if not character.isspace() and not unicodedata.category(character).startswith("C")
    )


def _read_source(model: str, source_path: str, row_limit: int) -> list[dict[str, object]]:
    process = subprocess.Popen(  # noqa: S603
        [
            "curl",
            "-fsSL",
            "--retry",
            "3",
            "--connect-timeout",
            "30",
            "--user-agent",
            "Routellect-G5-evidence-acquirer/0.4",
            _source_url(source_path),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    rows: list[dict[str, object]] = []
    print(f"Reading {model} from frozen revision...", flush=True)
    assert process.stdout is not None
    text = io.TextIOWrapper(process.stdout, encoding="utf-8", newline="")
    try:
        csv.field_size_limit(sys.maxsize)
        reader = csv.DictReader(text)
        missing = set(ALLOWED_COLUMNS) - set(reader.fieldnames or ())
        if missing:
            raise ValueError(f"{model} is missing required columns: {sorted(missing)}")
        for index, source in enumerate(reader, start=1):
            if index > row_limit:
                break
            key = source["key"].strip()
            prompt = _normalize_prompt(source["original_prompt"])
            if not key or not prompt:
                raise ValueError(f"{model} row {index} has an empty key or prompt")
            rows.append(
                {
                    "key": key,
                    "prompts_id": source["prompts_id"].strip(),
                    "original_prompt": prompt,
                    "actual_token_count": int(source["actual_token_count"]),
                    "correctness_score": float(source["correctness_score"]),
                }
            )
            if index % 1_000 == 0:
                print(f"  retained {index:,}/{row_limit:,} rows", flush=True)
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)
        text.close()
    if len(rows) != row_limit:
        assert process.stderr is not None
        detail = process.stderr.read().decode(errors="replace").strip()
        raise ValueError(
            f"{model} returned {len(rows)} rows; expected {row_limit}. Transport: {detail}"
        )
    return rows


def acquire(output_dir: Path, row_limit: int = ROW_LIMIT) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    merged: list[dict[str, object]] | None = None
    source_manifest: list[dict[str, object]] = []
    prompt_mismatches: Counter[str] = Counter()

    for model, source_path in SOURCES.items():
        rows = _read_source(model, source_path, row_limit)
        if merged is None:
            merged = [
                {
                    "key": row["key"],
                    "prompts_id": row["prompts_id"],
                    "original_prompt": row["original_prompt"],
                    "models": {},
                }
                for row in rows
            ]
        for index, (target, row) in enumerate(zip(merged, rows, strict=True), start=1):
            if target["key"] != row["key"]:
                raise ValueError(f"unaligned key for {model} at retained row {index}")
            if target["prompts_id"] != row["prompts_id"]:
                raise ValueError(f"unaligned prompts_id for {model} at retained row {index}")
            if _prompt_alignment_fingerprint(
                target["original_prompt"]
            ) != _prompt_alignment_fingerprint(row["original_prompt"]):
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
                "url": _source_url(source_path),
                "retained_rows": len(rows),
            }
        )

    assert merged is not None
    aligned = [
        row
        for row in merged
        if not row.get("_alignment_excluded")
        and len(row.get("models", {})) == len(SOURCES)
    ]
    if not aligned:
        raise ValueError("no fully aligned rows remain after source validation")
    snapshot_path = output_dir / "r2_subset.jsonl"
    with snapshot_path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in aligned:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
            handle.write("\n")

    prompt_digest = hashlib.sha256()
    for row in aligned:
        prompt_digest.update(str(row["key"]).encode())
        prompt_digest.update(b"\0")
        prompt_digest.update(str(row["original_prompt"]).encode())
        prompt_digest.update(b"\0")

    manifest = {
        "schema_version": 1,
        "created_at": datetime.now(UTC).isoformat(),
        "dataset_id": DATASET_ID,
        "dataset_revision": REVISION,
        "declared_license": LICENSE,
        "token_budget": TOKEN_BUDGET,
        "selection": f"first {row_limit} aligned rows",
        "prompt_normalization": "Unicode NFC, CRLF to LF, strip edge whitespace",
        "alignment_check": (
            "exact key and prompts_id; Unicode-NFC prompt fingerprint with whitespace and "
            "Unicode control/format characters removed"
        ),
        "source_row_count_per_candidate": row_limit,
        "row_count": len(aligned),
        "excluded_rows": len(merged) - len(aligned),
        "prompt_mismatch_count_by_source": dict(sorted(prompt_mismatches.items())),
        "candidate_count": len(SOURCES),
        "allowed_source_columns": list(ALLOWED_COLUMNS),
        "discarded_sensitive_payloads": [
            "templated_prompt",
            "golden_answer",
            "response",
            "judge_raw",
        ],
        "source_files": source_manifest,
        "snapshot_file": snapshot_path.name,
        "snapshot_sha256": _sha256(snapshot_path),
        "key_prompt_sha256": prompt_digest.hexdigest(),
    }
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(f"Wrote {snapshot_path} ({manifest['snapshot_sha256']})", flush=True)
    print(f"Wrote {manifest_path}", flush=True)
    return snapshot_path, manifest_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("work/g5-r2"),
        help="Directory for the normalized snapshot and provenance manifest.",
    )
    parser.add_argument("--row-limit", type=int, default=ROW_LIMIT)
    args = parser.parse_args()
    if args.row_limit < 1 or args.row_limit > ROW_LIMIT:
        parser.error(f"--row-limit must be between 1 and {ROW_LIMIT}")
    acquire(args.output_dir, args.row_limit)


if __name__ == "__main__":
    main()
