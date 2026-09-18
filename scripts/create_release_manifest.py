#!/usr/bin/env python3
"""Create the immutable G6 release-candidate provenance manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

EXCLUDED_PARTS = {
    ".git",
    ".venv",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
    "node_modules",
    "dist",
    "outputs",
    "work",
    "data",
}
EXCLUDED_NAMES = {".coverage", ".DS_Store"}
BASE_IMAGES = {
    "node:22-alpine": "sha256:c610fcdfb1d5b4740dd70c284ed3cb16bb857e0f7166196e36a5501df7a3aa32",
    "python:3.12-slim": "sha256:78387bc3881b8273120a12ebe6c1ab22b018ccc2c9adf565ae1ac9b536e184ea",
}
ASSESSOR = {
    "repository": "HuggingFaceTB/SmolLM2-360M-Instruct-GGUF",
    "revision": "593b5a2e04c8f3e4ee880263f93e0bd2901ad47f",
    "file": "smollm2-360m-instruct-q8_0.gguf",
    "sha256": "48ab3034d0dd401fbc721eb1df3217902fee7dab9078992d66431f09b7750201",
    "license": "Apache-2.0",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _source_inventory(root: Path) -> tuple[list[dict[str, object]], str]:
    files: list[dict[str, object]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if any(part in EXCLUDED_PARTS for part in relative.parts):
            continue
        if path.name in EXCLUDED_NAMES or path.suffix == ".tsbuildinfo":
            continue
        files.append(
            {
                "path": relative.as_posix(),
                "size": path.stat().st_size,
                "sha256": _sha256(path),
            }
        )
    canonical = json.dumps(files, separators=(",", ":"), sort_keys=True).encode()
    return files, hashlib.sha256(canonical).hexdigest()


def _artifact(root: Path, relative: str) -> dict[str, object]:
    path = root / relative
    if not path.is_file():
        raise FileNotFoundError(f"required release evidence is missing: {relative}")
    return {"path": relative, "size": path.stat().st_size, "sha256": _sha256(path)}


def _run(*arguments: str) -> str:
    return subprocess.run(  # noqa: S603
        list(arguments), check=True, text=True, capture_output=True
    ).stdout.strip()


def create(root: Path, image: str, output: Path) -> dict[str, object]:
    source_files, source_digest = _source_inventory(root)
    image_info = json.loads(_run("podman", "image", "inspect", image))[0]
    evidence_paths = [
        "outputs/routellect-0.5.0.cdx.json",
        "outputs/phase-6-license-report.md",
        "outputs/phase-6-trivy-sbom-report.json",
        "outputs/phase-6-pnpm-audit.json",
        "outputs/phase-6-debian-security.json",
        "outputs/phase-6-secret-scan.json",
        "outputs/phase-6-vulnerability-report.md",
        "outputs/phase-6-resilience-results.json",
        "outputs/phase-6-backup-restore-report.md",
        "outputs/phase-6-amd64-smoke.json",
        "outputs/phase-6-multiarch-report.md",
        "outputs/phase-6-operator-runbook.md",
        "outputs/phase-5-benchmark-results.json",
        "outputs/phase-5-container-benchmark.json",
        "requirements-dev.lock",
        "frontend/pnpm-lock.yaml",
        "Containerfile",
    ]
    labels = image_info.get("Labels") or image_info.get("Config", {}).get("Labels") or {}
    manifest: dict[str, object] = {
        "schema": "routellect-release-manifest-v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "release": {
            "name": "Routellect",
            "version": "0.5.0",
            "status": "gated-release-candidate",
            "publication_authorized": False,
        },
        "source": {
            "tree_sha256": source_digest,
            "file_count": len(source_files),
            "files": source_files,
            "excluded_parts": sorted(EXCLUDED_PARTS),
            "excluded_names": sorted(EXCLUDED_NAMES | {"*.tsbuildinfo"}),
        },
        "container": {
            "reference": image,
            "id": image_info.get("Id"),
            "digest": image_info.get("Digest"),
            "repo_digests": image_info.get("RepoDigests", []),
            "size_bytes": image_info.get("Size"),
            "architecture": image_info.get("Architecture"),
            "os": image_info.get("Os"),
            "labels": labels,
            "base_manifest_digests": BASE_IMAGES,
        },
        "assessor": ASSESSOR,
        "evidence": [_artifact(root, path) for path in evidence_paths],
        "toolchain": {
            "podman": _run("podman", "version", "--format", "{{.Client.Version}}"),
            "python": _run("python3", "--version"),
            "sbom_standard": "CycloneDX 1.6",
            "vulnerability_scanner": (
                "Trivy 0.74.0, ghcr.io arm64 digest "
                "sha256:55ad20f8a239a3e95427e60b8aaea38788550c18a3f1772976bebf732e6ae166"
            ),
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--image", default="localhost/routellect:0.5.0")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/routellect-0.5.0-release-manifest.json"),
    )
    args = parser.parse_args()
    manifest = create(args.root.resolve(), args.image, args.output)
    print(
        json.dumps(
            {
                "output": str(args.output),
                "source_tree_sha256": manifest["source"]["tree_sha256"],
                "image_id": manifest["container"]["id"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
