#!/usr/bin/env python3
"""Generate a CycloneDX 1.6 SBOM and license inventory for a built release image."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import urllib.parse
import uuid
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

PYTHON_INVENTORY = r"""
import importlib.metadata as metadata
import json
items = []
for distribution in metadata.distributions():
    package = distribution.metadata
    license_value = package.get("License-Expression") or package.get("License")
    if not license_value:
        classifiers = package.get_all("Classifier") or []
        license_classifiers = [
            value.removeprefix("License :: OSI Approved :: ")
            for value in classifiers
            if value.startswith("License :: OSI Approved :: ")
        ]
        license_value = " OR ".join(license_classifiers) or "UNKNOWN"
    items.append({
        "name": package.get("Name") or "unknown",
        "version": distribution.version,
        "license": license_value,
    })
print(json.dumps(sorted(items, key=lambda item: (item["name"].lower(), item["version"]))))
"""

DEBIAN_INVENTORY = r"""
import json
import re
import subprocess
from pathlib import Path

rows = subprocess.check_output(
    ["dpkg-query", "-W", "-f=${Package}\t${Version}\n"], text=True
)
items = []
for row in rows.splitlines():
    name, version = row.split("\t", 1)
    copyright_path = Path("/usr/share/doc") / name.split(":", 1)[0] / "copyright"
    licenses = []
    if copyright_path.is_file():
        text = copyright_path.read_text(errors="ignore")
        licenses = sorted(set(re.findall(r"(?m)^License:[ \t]*(.+)$", text)))
    items.append({
        "name": name,
        "version": version,
        "license": " AND ".join(licenses) if licenses else "UNKNOWN",
        "license_source": str(copyright_path) if licenses else "unavailable",
    })
print(json.dumps(items))
"""

BASE_COMPONENTS = (
    (
        "node",
        "22-alpine",
        "sha256:c610fcdfb1d5b4740dd70c284ed3cb16bb857e0f7166196e36a5501df7a3aa32",
    ),
    (
        "python",
        "3.12-slim",
        "sha256:78387bc3881b8273120a12ebe6c1ab22b018ccc2c9adf565ae1ac9b536e184ea",
    ),
)


def _run(*arguments: str) -> str:
    result = subprocess.run(  # noqa: S603
        ["podman", *arguments],
        check=True,
        text=True,
        capture_output=True,
    )
    return result.stdout


def _license(value: object) -> str:
    if isinstance(value, list):
        return " OR ".join(str(item) for item in value)
    if isinstance(value, dict):
        return str(value.get("type") or value.get("name") or "UNKNOWN")
    text = str(value or "UNKNOWN").strip()
    return text if text else "UNKNOWN"


def _component(
    component_type: str,
    ecosystem: str,
    name: str,
    version: str,
    license_name: str,
    *,
    properties: list[dict[str, str]] | None = None,
    hashes: list[dict[str, str]] | None = None,
) -> dict[str, object]:
    encoded_name = urllib.parse.quote(name, safe="/")
    reference = f"pkg:{ecosystem}/{encoded_name}@{version}"
    component: dict[str, object] = {
        "type": component_type,
        "bom-ref": reference,
        "name": name,
        "version": version,
        "purl": reference,
        "licenses": [{"license": {"name": license_name}}],
    }
    if properties:
        component["properties"] = properties
    if hashes:
        component["hashes"] = hashes
    return component


def _python_components(image: str) -> list[dict[str, object]]:
    packages = json.loads(
        _run("run", "--rm", "--entrypoint", "python", image, "-c", PYTHON_INVENTORY)
    )
    return [
        _component(
            "library",
            "pypi",
            item["name"],
            item["version"],
            _license(item["license"]),
            properties=[{"name": "routellect:scope", "value": "runtime"}],
        )
        for item in packages
    ]


def _debian_components(image: str) -> list[dict[str, object]]:
    packages = json.loads(_run(
        "run",
        "--rm",
        "--entrypoint",
        "python",
        image,
        "-c",
        DEBIAN_INVENTORY,
    ))
    components = []
    for item in packages:
        components.append(
            _component(
                "library",
                "deb/debian",
                item["name"],
                item["version"],
                _license(item["license"]),
                properties=[
                    {"name": "routellect:scope", "value": "runtime-os"},
                    {
                        "name": "routellect:license-metadata-source",
                        "value": item["license_source"],
                    },
                ],
            )
        )
    return components


def _node_components(node_modules: Path) -> list[dict[str, object]]:
    packages: dict[tuple[str, str], dict[str, object]] = {}
    for manifest_path in node_modules.glob(".pnpm/*/node_modules/**/package.json"):
        if manifest_path.is_symlink():
            continue
        try:
            manifest = json.loads(manifest_path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        name = manifest.get("name")
        version = manifest.get("version")
        if isinstance(name, str) and isinstance(version, str):
            packages[(name, version)] = _component(
                "library",
                "npm",
                name,
                version,
                _license(manifest.get("license")),
                properties=[{"name": "routellect:scope", "value": "frontend-build"}],
            )
    return [packages[key] for key in sorted(packages)]


def generate(image: str, node_modules: Path, output: Path, license_report: Path) -> dict:
    image_info = json.loads(_run("image", "inspect", image))[0]
    labels = image_info.get("Labels") or image_info.get("Config", {}).get("Labels") or {}
    version = labels.get("org.opencontainers.image.version", "unknown")
    components = _python_components(image)
    components.extend(_debian_components(image))
    components.extend(_node_components(node_modules))
    for name, tag, digest in BASE_COMPONENTS:
        components.append(
            _component(
                "container",
                "oci",
                name,
                tag,
                "UNKNOWN",
                properties=[
                    {"name": "routellect:manifest-digest", "value": digest},
                    {"name": "routellect:scope", "value": "build-base"},
                ],
            )
        )
    components.append(
        _component(
            "machine-learning-model",
            "huggingface",
            "HuggingFaceTB/SmolLM2-360M-Instruct-GGUF",
            "593b5a2e04c8f3e4ee880263f93e0bd2901ad47f",
            "Apache-2.0",
            properties=[
                {"name": "routellect:scope", "value": "bundled-assessor"},
                {"name": "routellect:quantization", "value": "Q8_0"},
            ],
            hashes=[
                {
                    "alg": "SHA-256",
                    "content": (
                        "48ab3034d0dd401fbc721eb1df3217902fee7dab9078992d66431f09b7750201"
                    ),
                }
            ],
        )
    )

    unique: dict[str, dict[str, object]] = {}
    for component in components:
        unique[str(component["bom-ref"])] = component
    ordered = [unique[key] for key in sorted(unique)]
    root_ref = f"pkg:pypi/routellect@{version}"
    bom = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.6",
        "serialNumber": f"urn:uuid:{uuid.uuid4()}",
        "version": 1,
        "metadata": {
            "timestamp": datetime.now(UTC).isoformat(),
            "tools": {
                "components": [
                    {
                        "type": "application",
                        "name": "Routellect SBOM generator",
                        "version": version,
                    }
                ]
            },
            "component": {
                "type": "application",
                "bom-ref": root_ref,
                "name": "routellect",
                "version": version,
                "purl": root_ref,
                "licenses": [{"license": {"id": "Apache-2.0"}}],
                "properties": [
                    {"name": "routellect:image-reference", "value": image},
                    {
                        "name": "routellect:image-digest",
                        "value": str(image_info.get("Digest", "unknown")),
                    },
                ],
            },
            "properties": [
                {"name": "routellect:component-completeness", "value": "known-components"},
                {
                    "name": "routellect:completeness-note",
                    "value": (
                        "Includes final-image Python and Debian packages, frontend build packages, "
                        "base manifests, and bundled assessor; transitive source-build toolchains "
                        "are represented by frontend packages and base-image references."
                    ),
                },
            ],
        },
        "components": ordered,
        "dependencies": [
            {"ref": root_ref, "dependsOn": [item["bom-ref"] for item in ordered]}
        ],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(bom, indent=2, sort_keys=True) + "\n")

    licenses = Counter(
        str(item["licenses"][0]["license"].get("name", "Apache-2.0"))
        for item in ordered
    )
    unknown = [
        f"{item['name']} {item['version']}"
        for item in ordered
        if item["licenses"][0]["license"].get("name") == "UNKNOWN"
    ]
    lines = [
        "# Routellect 0.5.0 License Inventory",
        "",
        f"Generated: {datetime.now(UTC).isoformat()}",
        "",
        "## Summary",
        "",
        f"- Components inventoried: {len(ordered)}",
        f"- Components with unknown machine-readable license metadata: {len(unknown)}",
        "- Project license: Apache-2.0",
        "- Bundled assessor license: Apache-2.0",
        "",
        "| Declared metadata | Components |",
        "|---|---:|",
    ]
    lines.extend(
        f"| {name.replace('|', '/')} | {count} |"
        for name, count in sorted(licenses.items())
    )
    lines.extend(
        [
            "",
            "## Review notes",
            "",
            "`UNKNOWN` means installed package metadata or the Debian package database did not ",
            "expose a license expression here; this does not mean the component is unlicensed. ",
            "These entries require source-package review before public publication.",
            "",
            "## Unknown metadata entries",
            "",
        ]
    )
    lines.extend(f"- {re.sub(r'[`|]', '', item)}" for item in unknown)
    license_report.write_text("\n".join(lines) + "\n")
    return bom


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", default="localhost/routellect:0.5.0")
    parser.add_argument("--node-modules", type=Path, default=Path("frontend/node_modules"))
    parser.add_argument(
        "--output", type=Path, default=Path("outputs/routellect-0.5.0.cdx.json")
    )
    parser.add_argument(
        "--license-report", type=Path, default=Path("outputs/phase-6-license-report.md")
    )
    args = parser.parse_args()
    bom = generate(args.image, args.node_modules, args.output, args.license_report)
    print(f"Wrote {args.output} with {len(bom['components'])} components")
    print(f"Wrote {args.license_report}")


if __name__ == "__main__":
    main()
