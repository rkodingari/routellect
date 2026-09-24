#!/usr/bin/env python3
"""Match final-image Debian source packages against the official Security Tracker."""

from __future__ import annotations

import argparse
import json
import subprocess
import urllib.request
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

TRACKER_URL = "https://security-tracker.debian.org/tracker/data/json"
PACKAGE_INVENTORY = r"""
import json
import subprocess

rows = subprocess.check_output(
    [
        "dpkg-query",
        "-W",
        "-f=${binary:Package}\t${source:Package}\t${source:Version}\t${Version}\n",
    ],
    text=True,
)
items = []
for row in rows.splitlines():
    binary, source, source_version, binary_version = row.split("\t", 3)
    items.append({
        "binary": binary,
        "source": source or binary.split(":", 1)[0],
        "source_version": source_version or binary_version,
        "binary_version": binary_version,
    })
print(json.dumps(items))
"""


def _packages(image: str) -> list[dict[str, str]]:
    result = subprocess.run(  # noqa: S603
        ["podman", "run", "--rm", "--entrypoint", "python", image, "-c", PACKAGE_INVENTORY],
        check=True,
        text=True,
        capture_output=True,
    )
    return json.loads(result.stdout)


def scan(image: str, suite: str, tracker_url: str) -> dict[str, object]:
    packages = _packages(image)
    request = urllib.request.Request(  # noqa: S310
        tracker_url, headers={"User-Agent": "Routellect-G6-security-audit/0.5.0"}
    )
    with urllib.request.urlopen(request, timeout=60) as response:  # noqa: S310
        tracker = json.load(response)

    by_source: dict[str, list[dict[str, str]]] = {}
    for package in packages:
        by_source.setdefault(package["source"], []).append(package)
    findings: list[dict[str, object]] = []
    for source, installed in sorted(by_source.items()):
        for vulnerability_id, vulnerability in tracker.get(source, {}).items():
            release = vulnerability.get("releases", {}).get(suite)
            if not isinstance(release, dict) or release.get("status") == "resolved":
                continue
            findings.append(
                {
                    "id": vulnerability_id,
                    "source_package": source,
                    "installed_source_versions": sorted(
                        {item["source_version"] for item in installed}
                    ),
                    "binary_packages": sorted({item["binary"] for item in installed}),
                    "status": release.get("status", "unknown"),
                    "urgency": release.get("urgency", "unknown"),
                    "fixed_version": release.get("fixed_version"),
                    "no_dsa": release.get("nodsa"),
                    "description": vulnerability.get("description"),
                    "tracker_url": (
                        "https://security-tracker.debian.org/tracker/" + vulnerability_id
                    ),
                }
            )
    severities = Counter(str(item["urgency"]) for item in findings)
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "image": image,
        "suite": suite,
        "source": tracker_url,
        "binary_packages": len(packages),
        "source_packages": len(by_source),
        "open_findings": len(findings),
        "urgency_counts": dict(sorted(severities.items())),
        "findings": findings,
        "method_note": (
            "Exact installed Debian source-package identities were matched against the suite "
            "status in Debian's official Security Tracker. Resolved entries are omitted."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", default="localhost/routellect:0.5.0")
    parser.add_argument("--suite", default="trixie")
    parser.add_argument("--tracker-url", default=TRACKER_URL)
    parser.add_argument(
        "--output", type=Path, default=Path("outputs/phase-6-debian-security.json")
    )
    args = parser.parse_args()
    result = scan(args.image, args.suite, args.tracker_url)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "output": str(args.output),
                "open_findings": result["open_findings"],
                "urgency_counts": result["urgency_counts"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
