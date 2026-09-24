"""Frozen constants and helpers for the one-time G7-E evaluation."""

from __future__ import annotations

import csv
import hashlib
import io
import re
import subprocess
import sys
import unicodedata
import urllib.parse
from collections.abc import Iterator
from pathlib import Path

REVISION = "1b6234647a21705da4c220f339e44fbe72c69bb2"
DATASET_ID = "JiaqiXue/R2-Bench"
DECLARED_LICENSE = "MIT"
START_PROMPT_ID = 15_001
END_PROMPT_ID = 30_968
EXPECTED_ROWS = END_PROMPT_ID - START_PROMPT_ID + 1
TOKEN_BUDGET = 100
COST_WEIGHT = 0.20
MAXIMUM_COMPUTE = 7_700.0
STRONG_MODEL = "Llama-3.1-70B-Instruct"
FROZEN_ARTIFACT_SHA256 = (
    "6f32a6242fca4137cb50e515a4012a7bbea6fc01f078a12485016350aae50499"
)
CONTROL_SALT = "routellect-g7c2-content-blind-v1|"
BOOTSTRAP_REPETITIONS = 10_000
BOOTSTRAP_SEED = 2_718_281
MAX_SCREEN_TOKENS = 2_048
TOKEN_PATTERN = re.compile(r"[^\W_]+(?:['’-][^\W_]+)?", re.UNICODE)

CANDIDATE_PARAMETERS = {
    "Qwen3-0.6B": 0.6,
    "Qwen2.5-Math-1.5B-Instruct": 1.5,
    "Qwen2.5-Math-7B-Instruct": 7.0,
    STRONG_MODEL: 70.0,
}
SOURCES = {
    "Qwen3-0.6B": "data/Qwen/Qwen3-0.6B/100_judge.csv",
    "Qwen2.5-Math-1.5B-Instruct": (
        "data/Qwen/Qwen2.5-Math-1.5B-Instruct/100_judge.csv"
    ),
    "Qwen2.5-Math-7B-Instruct": "data/Qwen/Qwen2.5-Math-7B-Instruct/100_judge.csv",
    STRONG_MODEL: "data/meta-llama/Llama-3.1-70B-Instruct/100_judge.csv",
}


def source_url(path: str) -> str:
    encoded = urllib.parse.quote(path, safe="/")
    return (
        f"https://huggingface.co/datasets/{DATASET_ID}/resolve/{REVISION}/"
        f"{encoded}?download=true"
    )


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_prompt(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    visible = "".join(
        " " if unicodedata.category(character).startswith("C") else character
        for character in normalized
    )
    return " ".join(visible.split())


def canonical_sha256(value: str) -> str:
    return hashlib.sha256(canonical_prompt(value).encode()).hexdigest()


def word_tokens(value: str) -> tuple[str, ...]:
    return tuple(TOKEN_PATTERN.findall(canonical_prompt(value)))[:MAX_SCREEN_TOKENS]


def trigram_hashes(tokens: tuple[str, ...]) -> frozenset[int]:
    return frozenset(
        int.from_bytes(
            hashlib.blake2b("\0".join(tokens[index : index + 3]).encode(), digest_size=8).digest(),
            "big",
        )
        for index in range(max(0, len(tokens) - 2))
    )


def stream_source_rows(source_path: str) -> Iterator[dict[str, str]]:
    """Stream the preregistered range; non-minimized source fields never leave this process."""
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
            "Routellect-G7E-evaluator/0.6",
            source_url(source_path),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert process.stdout is not None
    text = io.TextIOWrapper(process.stdout, encoding="utf-8", newline="")
    completed = False
    try:
        csv.field_size_limit(sys.maxsize)
        reader = csv.DictReader(text)
        required = {
            "key",
            "prompts_id",
            "original_prompt",
            "actual_token_count",
            "correctness_score",
        }
        missing = required - set(reader.fieldnames or ())
        if missing:
            raise ValueError(f"source is missing required columns: {sorted(missing)}")
        retained = 0
        for source in reader:
            prompt_id = int(source["prompts_id"])
            if prompt_id < START_PROMPT_ID:
                continue
            if prompt_id > END_PROMPT_ID:
                break
            retained += 1
            yield source
            if retained % 2_000 == 0:
                print(f"  streamed {retained:,}/{EXPECTED_ROWS:,} rows", flush=True)
        if retained != EXPECTED_ROWS:
            raise ValueError(f"source returned {retained} rows; expected {EXPECTED_ROWS}")
        completed = True
    finally:
        if completed:
            text.close()
            return_code = process.wait(timeout=30)
            if return_code != 0:
                assert process.stderr is not None
                detail = process.stderr.read().decode(errors="replace").strip()
                raise RuntimeError(f"source transport failed: {detail}")
        else:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)
            text.close()


def normalized_prompt(value: str) -> str:
    return unicodedata.normalize("NFC", value).replace("\r\n", "\n").strip()
