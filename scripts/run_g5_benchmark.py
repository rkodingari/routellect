#!/usr/bin/env python3
"""Run the frozen G5 evidence benchmark and emit a machine-readable report."""

from __future__ import annotations

import argparse
import json
import platform
import sys
from datetime import UTC, datetime
from pathlib import Path

from routellect.evidence_benchmark import load_evidence, run_benchmark


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, default=Path("work/g5-r2/r2_subset.jsonl"))
    parser.add_argument("--manifest", type=Path, default=Path("work/g5-r2/manifest.json"))
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/phase-5-benchmark-results.json"),
    )
    parser.add_argument("--bootstrap-repetitions", type=int, default=2_000)
    args = parser.parse_args()
    if args.bootstrap_repetitions < 1:
        parser.error("--bootstrap-repetitions must be positive")

    print("Verifying and profiling the frozen evidence snapshot...", flush=True)
    rows, manifest = load_evidence(args.snapshot, args.manifest)
    result = run_benchmark(
        rows,
        bootstrap_repetitions=args.bootstrap_repetitions,
        progress=lambda message: print(message, flush=True),
    )
    result["generated_at"] = datetime.now(UTC).isoformat()
    result["runtime"] = {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
    }
    result["evidence_manifest"] = manifest
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(f"Wrote {args.output}", flush=True)
    promotion = result["promotion"]
    print(
        "Hybrid candidate eligible for separate review: "
        f"{promotion['eligible_for_separate_offline_policy_review']}",
        flush=True,
    )


if __name__ == "__main__":
    main()
