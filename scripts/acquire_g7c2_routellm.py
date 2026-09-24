#!/usr/bin/env python3
"""Acquire minimized Apache-2.0 RouteLLM auxiliary development evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import ssl
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

DATASET_ID = "routellm/gpt4_judge_battles"
REVISION = "2a1afe8d0659904c0f6f59de6179e086fdb027c7"
DECLARED_LICENSE = "apache-2.0"
ROW_OFFSET = 0
ROW_COUNT = 20_000
PAGE_SIZE = 100
METADATA_URL = f"https://huggingface.co/api/datasets/{DATASET_ID}"
ROWS_URL = "https://datasets-server.huggingface.co/rows"
EXPECTED_MODELS = {"gpt-4-1106-preview", "mixtral-8x7b-instruct-v0.1"}


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _fetch_json(url: str, attempts: int = 8) -> dict:
    request = urllib.request.Request(
        url, headers={"User-Agent": "Routellect-G7C2-evidence-acquirer/0.6"}
    )
    context = ssl._create_unverified_context()  # noqa: SLF001
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(  # noqa: S310
                request, timeout=45, context=context
            ) as response:
                return json.loads(response.read())
        except (OSError, json.JSONDecodeError) as exc:
            last_error = exc
            if attempt + 1 < attempts:
                rate_limited = isinstance(exc, urllib.error.HTTPError) and exc.code == 429
                time.sleep((5 if rate_limited else 1) * (attempt + 1))
    raise RuntimeError(f"failed to fetch {url}: {last_error}")


def _normalize_prompt(raw: object) -> str:
    parsed: object
    try:
        parsed = json.loads(str(raw))
    except json.JSONDecodeError:
        parsed = raw
    if isinstance(parsed, list):
        parts = []
        for item in parsed:
            if isinstance(item, dict):
                parts.append(str(item.get("content", item)))
            else:
                parts.append(str(item))
        text = "\n".join(parts)
    else:
        text = str(parsed)
    return (
        unicodedata.normalize("NFC", text)
        .replace("\r\n", "\n")
        .replace("\u2028", "\n")
        .replace("\u2029", "\n")
        .strip()
    )


def _page_url(offset: int, length: int) -> str:
    query = urllib.parse.urlencode(
        {
            "dataset": DATASET_ID,
            "config": "default",
            "split": "train",
            "offset": offset,
            "length": length,
            "revision": REVISION,
        }
    )
    return f"{ROWS_URL}?{query}"


def acquire(output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    metadata = _fetch_json(METADATA_URL)
    if metadata.get("sha") != REVISION:
        raise ValueError(f"dataset revision changed: {metadata.get('sha')}")
    license_name = metadata.get("cardData", {}).get("license")
    if license_name != DECLARED_LICENSE:
        raise ValueError(f"dataset license changed: {license_name}")

    retained: list[dict[str, object]] = []
    labels: Counter[str] = Counter()
    seen_ids: set[int] = set()
    seen_prompts: Counter[str] = Counter()
    offsets = list(range(ROW_OFFSET, ROW_OFFSET + ROW_COUNT, PAGE_SIZE))
    with ThreadPoolExecutor(max_workers=4, thread_name_prefix="routellm-page") as executor:
        for block_start in range(0, len(offsets), 4):
            block = offsets[block_start : block_start + 4]
            futures = {
                offset: executor.submit(_fetch_json, _page_url(offset, PAGE_SIZE))
                for offset in block
            }
            for offset in block:
                payload = futures[offset].result()
                if int(payload.get("num_rows_total", 0)) < ROW_OFFSET + ROW_COUNT:
                    raise ValueError("dataset no longer contains the frozen source window")
                rows = payload.get("rows", [])
                if len(rows) != PAGE_SIZE:
                    raise ValueError(f"short page at offset {offset}: {len(rows)}")
                for wrapped in rows:
                    row = wrapped["row"]
                    if {str(row["model_a"]), str(row["model_b"])} != EXPECTED_MODELS:
                        raise ValueError(
                            f"unexpected model pair at source row {wrapped['row_idx']}"
                        )
                    row_id = int(row["id"])
                    if row_id in seen_ids:
                        raise ValueError(f"duplicate row id {row_id}")
                    seen_ids.add(row_id)
                    indicators = {
                        "strong": int(row["winner_model_a"]),
                        "economical": int(row["winner_model_b"]),
                        "tie": int(row["winner_tie"]),
                    }
                    if sum(indicators.values()) != 1 or any(
                        value not in {0, 1} for value in indicators.values()
                    ):
                        raise ValueError(f"invalid winner indicators for row {row_id}")
                    prompt = _normalize_prompt(row["prompt"])
                    if not prompt:
                        raise ValueError(f"empty prompt for row {row_id}")
                    fingerprint = hashlib.sha256(prompt.encode()).hexdigest()
                    seen_prompts[fingerprint] += 1
                    label = next(name for name, value in indicators.items() if value)
                    labels[label] += 1
                    retained.append(
                        {
                            "key": hashlib.sha256(
                                f"{DATASET_ID}|{REVISION}|{row_id}|{fingerprint}".encode()
                            ).hexdigest(),
                            "source_row_id": row_id,
                            "prompt": prompt,
                            "label": label,
                        }
                    )
            if len(retained) % 2_000 == 0:
                print(
                    f"retained {len(retained):,}/{ROW_COUNT:,} minimized rows",
                    flush=True,
                )

    evidence_path = output_dir / "routellm-development.jsonl"
    with evidence_path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in retained:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
            handle.write("\n")
    manifest = {
        "schema_version": 1,
        "phase": "G7-C2",
        "created_at": datetime.now(UTC).isoformat(),
        "dataset_id": DATASET_ID,
        "dataset_revision": REVISION,
        "declared_license": DECLARED_LICENSE,
        "license_source": METADATA_URL,
        "source_window": [ROW_OFFSET, ROW_OFFSET + ROW_COUNT - 1],
        "retained_rows": len(retained),
        "label_counts": dict(sorted(labels.items())),
        "duplicate_prompt_groups": sum(count > 1 for count in seen_prompts.values()),
        "persisted_fields": ["key", "source_row_id", "prompt", "label"],
        "excluded_fields": ["response_a", "response_b", "model_a", "model_b"],
        "raw_model_responses_persisted": False,
        "hidden_test_rows_loaded": 0,
        "transport": {
            "tls_verification": False,
            "reason": "development host intercept CA is unavailable",
            "integrity_controls": (
                "Hugging Face metadata revision and Apache-2.0 card field are checked; "
                "the minimized snapshot receives a local SHA-256 identity."
            ),
        },
        "evidence_sha256": file_sha256(evidence_path),
    }
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return evidence_path, manifest_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir", type=Path, default=Path("work/g7c2-evidence")
    )
    args = parser.parse_args()
    evidence, manifest = acquire(args.output_dir)
    print(f"wrote {evidence} ({file_sha256(evidence)})")
    print(f"wrote {manifest} ({file_sha256(manifest)})")


if __name__ == "__main__":
    main()
