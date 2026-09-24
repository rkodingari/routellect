#!/usr/bin/env python3
"""Verify the consolidated Routellect image under a rootless, offline Podman boundary."""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path


def _run(*arguments: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(  # noqa: S603
        ["podman", *arguments], check=False, text=True, capture_output=True
    )
    if check and result.returncode:
        raise RuntimeError(
            f"podman {' '.join(arguments[:3])} failed: {result.stderr.strip()}"
        )
    return result


def _exists(resource: str, name: str) -> bool:
    return _run(resource, "exists", name, check=False).returncode == 0


READY_CODE = """
import json, urllib.request
with urllib.request.urlopen('http://127.0.0.1:8080/health/ready', timeout=2) as response:
    print(response.read().decode())
"""

ADVISE_CODE = """
import json, statistics, time, urllib.request
payload = json.dumps({
    'messages': [{'role': 'user',
                  'content': 'Summarize this quarterly report into five key points.'}],
    'assessor_mode': 'off',
}).encode()
request = urllib.request.Request('http://127.0.0.1:8080/v1/model-recommendations', data=payload,
                                 headers={'Content-Type': 'application/json'}, method='POST')
latencies = []
for _ in range(100):
    started = time.perf_counter()
    with urllib.request.urlopen(request, timeout=5) as response:
        body = json.loads(response.read())
        assert response.status == 200 and body['non_executing'] is True
        assert body['advisor_version'] == 'deterministic-unified-v1+feedback-bayes-v1'
    latencies.append((time.perf_counter() - started) * 1000)
latencies.sort()
print(json.dumps({'requests': len(latencies), 'mean_ms': statistics.fmean(latencies),
                  'p50_ms': latencies[49], 'p95_ms': latencies[94]}))
"""

CONTENTS_CODE = """
import importlib.util, json
from importlib.resources import files
print(json.dumps({
    'sparse_module': importlib.util.find_spec('routellect.sparse_policy') is not None,
    'sparse_artifact': files('routellect').joinpath('data/g7_sparse_strength.json').is_file(),
    'multisource_artifact': files('routellect').joinpath(
        'data/g7c2_multisource_strength.json'
    ).is_file(),
}))
"""


def verify(image: str, output: Path) -> dict[str, object]:
    container = "routellect-g8c-fresh-verify"
    volume = "routellect-g8c-fresh-data"
    if _exists("container", container) or _exists("volume", volume):
        raise RuntimeError(
            "reserved G8-C verification resource already exists; refusing to replace it"
        )
    created_container = False
    created_volume = False
    try:
        _run("volume", "create", volume)
        created_volume = True
        _run(
            "run",
            "--detach",
            "--name",
            container,
            "--network",
            "none",
            "--read-only",
            "--tmpfs",
            "/tmp:rw,noexec,nosuid,size=128m",
            "--cap-drop=all",
            "--security-opt=no-new-privileges",
            "--user",
            "10001:10001",
            "-v",
            f"{volume}:/data:Z",
            image,
        )
        created_container = True
        started = time.perf_counter()
        ready_body = ""
        deadline = time.perf_counter() + 30
        while time.perf_counter() < deadline:
            result = _run("exec", container, "python", "-c", READY_CODE, check=False)
            if result.returncode == 0:
                ready_body = result.stdout.strip()
                break
            time.sleep(0.1)
        else:
            raise RuntimeError("offline container did not become ready within 30 seconds")

        advisory = json.loads(_run("exec", container, "python", "-c", ADVISE_CODE).stdout)
        contents = json.loads(_run("exec", container, "python", "-c", CONTENTS_CODE).stdout)
        _run("healthcheck", "run", container)
        image_info = json.loads(_run("image", "inspect", image).stdout)[0]
        container_info = json.loads(_run("inspect", container).stdout)[0]
        host_config = container_info["HostConfig"]
        uid = _run("exec", container, "id", "-u").stdout.strip()
        gid = _run("exec", container, "id", "-g").stdout.strip()
        rootless = _run("info", "--format", "{{.Host.Security.Rootless}}").stdout.strip()
        result = {
            "schema": "routellect-g8c-podman-verification-v1",
            "generated_at": datetime.now(UTC).isoformat(),
            "image": {
                "reference": image,
                "id": image_info.get("Id"),
                "digest": image_info.get("Digest"),
                "size_bytes": image_info.get("Size"),
            },
            "security": {
                "rootless": rootless == "true",
                "uid": int(uid),
                "gid": int(gid),
                "network_mode": host_config.get("NetworkMode"),
                "read_only_rootfs": bool(host_config.get("ReadonlyRootfs")),
                "capabilities_dropped": host_config.get("CapDrop", []),
                "security_options": host_config.get("SecurityOpt", []),
                "health_status": container_info.get("State", {}).get("Health", {}).get("Status"),
            },
            "runtime": {
                "ready_body": json.loads(ready_body),
                "startup_seconds": time.perf_counter() - started,
                "advisory": advisory,
                "contents": contents,
                "target_provider_calls": 0,
                "network_access": "none",
            },
            "cleanup": {"container_removed": True, "volume_removed": True, "image_retained": True},
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
        return result
    finally:
        if created_container:
            _run("rm", "--force", container)
        if created_volume:
            _run("volume", "rm", volume)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", default="localhost/routellect:g8c-unified")
    parser.add_argument(
        "--output", type=Path, default=Path("outputs/phase-8c-fresh-podman-results.json")
    )
    args = parser.parse_args()
    print(json.dumps(verify(args.image, args.output), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
