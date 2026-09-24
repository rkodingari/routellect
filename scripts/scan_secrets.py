#!/usr/bin/env python3
"""Scan release source files for common committed-secret patterns."""

from __future__ import annotations

import argparse
import json
import re
from datetime import UTC, datetime
from pathlib import Path

EXCLUDED_PARTS = {
    ".git",
    ".venv",
    ".pytest_cache",
    ".ruff_cache",
    "node_modules",
    "dist",
    "outputs",
    "work",
    "__pycache__",
}
PATTERNS = {
    "private_key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "aws_access_key": re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    "github_token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,255}\b"),
    "openai_key": re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b"),
    "slack_token": re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
}
SYNTHETIC_CANARY_FILE = "src/routellect/data/deterministic_invariants.json"
SYNTHETIC_CANARY_VALUES = {
    "-----BEGIN PRIVATE KEY-----",
    "AKIAABCDEFGHIJKLMNOP",
    "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ123456",
}


def scan(root: Path) -> dict[str, object]:
    findings: list[dict[str, object]] = []
    acknowledged_canaries: list[dict[str, object]] = []
    scanned_files = 0
    scanned_bytes = 0
    self_path = Path(__file__).resolve()
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.resolve() == self_path:
            continue
        if any(part in EXCLUDED_PARTS for part in path.relative_to(root).parts):
            continue
        try:
            payload = path.read_bytes()
            text = payload.decode("utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        scanned_files += 1
        scanned_bytes += len(payload)
        for line_number, line in enumerate(text.splitlines(), start=1):
            for pattern_name, pattern in PATTERNS.items():
                match = pattern.search(line)
                if match:
                    relative = path.relative_to(root).as_posix()
                    if (
                        relative == SYNTHETIC_CANARY_FILE
                        and match.group() in SYNTHETIC_CANARY_VALUES
                    ):
                        acknowledged_canaries.append(
                            {
                                "file": relative,
                                "line": line_number,
                                "pattern": pattern_name,
                                "purpose": "synthetic privacy-detector invariant",
                            }
                        )
                        continue
                    findings.append(
                        {
                            "file": relative,
                            "line": line_number,
                            "pattern": pattern_name,
                        }
                    )
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "scanner": "Routellect bounded regex secret audit v1",
        "scanned_files": scanned_files,
        "scanned_bytes": scanned_bytes,
        "excluded_parts": sorted(EXCLUDED_PARTS),
        "finding_count": len(findings),
        "findings": findings,
        "acknowledged_synthetic_canary_count": len(acknowledged_canaries),
        "acknowledged_synthetic_canaries": acknowledged_canaries,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument(
        "--output", type=Path, default=Path("outputs/phase-6-secret-scan.json")
    )
    args = parser.parse_args()
    result = scan(args.root.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    if result["finding_count"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
