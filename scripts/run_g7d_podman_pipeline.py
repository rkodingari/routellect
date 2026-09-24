#!/usr/bin/env python3
"""Keep the macOS Podman VM alive while building and verifying the G7-D image."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from verify_g7d_podman import verify


def _run(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        ["podman", *arguments],
        check=True,
        text=True,
        capture_output=True,
    )


def _machine_state(machine: str) -> str:
    data = json.loads(_run("machine", "inspect", machine).stdout)
    return str(data[0]["State"])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--machine", default="podman-machine-default")
    parser.add_argument("--image", default="localhost/routellect:g7d-candidate")
    parser.add_argument(
        "--output", type=Path, default=Path("outputs/phase-7d-podman-results.json")
    )
    parser.add_argument("--port", type=int, default=18_082)
    parser.add_argument("--requests", type=int, default=500)
    args = parser.parse_args()

    started_here = _machine_state(args.machine) != "running"
    try:
        if started_here:
            _run("machine", "start", args.machine)
        if _machine_state(args.machine) != "running":
            raise RuntimeError("Podman machine did not remain running")
        _run("build", "--format", "docker", "--tag", args.image, ".")
        result = verify(args.image, args.output, args.port, args.requests)
        print(json.dumps(result, indent=2, sort_keys=True))
    finally:
        if started_here and _machine_state(args.machine) == "running":
            _run("machine", "stop", args.machine)


if __name__ == "__main__":
    main()
