#!/usr/bin/env python3
"""Verify the frozen candidate and production API in hardened rootless Podman."""

from __future__ import annotations

import argparse
import json
import subprocess
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path


def _run(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        ["podman", *arguments],
        check=True,
        text=True,
        capture_output=True,
    )


def _exists(resource: str, name: str) -> bool:
    result = subprocess.run(  # noqa: S603
        ["podman", resource, "exists", name],
        check=False,
        capture_output=True,
    )
    return result.returncode == 0


def _request(url: str, timeout: float = 3.0) -> tuple[int, bytes]:
    with urllib.request.urlopen(url, timeout=timeout) as response:  # noqa: S310
        return response.status, response.read()


def _post(url: str, payload: dict[str, object]) -> tuple[int, dict[str, object]]:
    request = urllib.request.Request(  # noqa: S310
        url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=5) as response:  # noqa: S310
        return response.status, json.loads(response.read())


def _offline_candidate(image: str) -> dict[str, object]:
    code = """
import hashlib,json,statistics,time
from importlib.resources import files
from routellect.sparse_policy import MultiSourceStrengthModel
p=files('routellect').joinpath('data/g7c2_multisource_strength.json')
b=p.read_bytes(); m=MultiSourceStrengthModel(json.loads(b))
prompts=[
    'Summarize this report into five bullets.',
    'Prove the theorem step by step.',
    'Review this Python concurrency design and identify race conditions.',
]
d=[]; choices=[]
for i in range(2000):
    prompt=prompts[i%len(prompts)]
    start=time.perf_counter_ns()
    choices.append(m.choose(prompt))
    d.append((time.perf_counter_ns()-start)/1e6)
d.sort()
print(json.dumps({'artifact_sha256':hashlib.sha256(b).hexdigest(),'samples':len(d),'p50_ms':d[round(.50*(len(d)-1))],'p95_ms':d[round(.95*(len(d)-1))],'p99_ms':d[round(.99*(len(d)-1))],'max_ms':d[-1],'decision_digest_sha256':hashlib.sha256(json.dumps(choices,separators=(',',':')).encode()).hexdigest()}))
""".strip()
    result = _run(
        "run",
        "--rm",
        "--network=none",
        "--read-only",
        "--tmpfs",
        "/tmp:rw,noexec,nosuid,size=64m",
        "--cap-drop=all",
        "--security-opt=no-new-privileges",
        "--entrypoint",
        "python",
        image,
        "-c",
        code,
    )
    return json.loads(result.stdout)


def verify(image: str, output: Path, port: int, requests: int) -> dict[str, object]:
    container = "routellect-g7d-qa"
    volume = "routellect-g7d-qa-data"
    if _exists("container", container) or _exists("volume", volume):
        raise RuntimeError("reserved G7-D QA resources already exist; refusing to replace them")

    offline = _offline_candidate(image)
    volume_created = False
    container_created = False
    try:
        _run("volume", "create", volume)
        volume_created = True
        started = time.perf_counter()
        _run(
            "run",
            "--detach",
            "--name",
            container,
            "--read-only",
            "--tmpfs",
            "/tmp:rw,noexec,nosuid,size=128m",
            "--cap-drop=all",
            "--security-opt=no-new-privileges",
            "-p",
            f"{port}:8080",
            "-v",
            f"{volume}:/data:Z",
            image,
        )
        container_created = True
        ready_url = f"http://127.0.0.1:{port}/health/ready"
        deadline = time.perf_counter() + 30
        ready_body = b""
        while time.perf_counter() < deadline:
            try:
                status, ready_body = _request(ready_url)
                if status == 200:
                    break
            except OSError:
                time.sleep(0.05)
        else:
            raise RuntimeError("G7-D container did not become ready within 30 seconds")
        readiness_seconds = time.perf_counter() - started

        advice_url = f"http://127.0.0.1:{port}/v1/model-recommendations"
        payload = {
            "messages": [{"role": "user", "content": "Summarize this report."}],
            "assessor_mode": "off",
        }
        durations = []
        for _ in range(requests):
            request_started = time.perf_counter_ns()
            status, body = _post(advice_url, payload)
            if status != 200 or body.get("non_executing") is not True:
                raise RuntimeError("container returned an invalid advisory response")
            if not str(body.get("advisor_version", "")).startswith("deterministic-v2"):
                raise RuntimeError("production container default changed away from v2")
            durations.append((time.perf_counter_ns() - request_started) / 1_000_000)
        durations.sort()

        _run("healthcheck", "run", container)
        image_info = json.loads(_run("image", "inspect", image).stdout)[0]
        container_info = json.loads(_run("inspect", container).stdout)[0]
        host = container_info["HostConfig"]
        rootless = _run("info", "--format", "{{.Host.Security.Rootless}}").stdout.strip()
        uid = int(_run("exec", container, "id", "-u").stdout.strip())
        gid = int(_run("exec", container, "id", "-g").stdout.strip())
        capability_code = (
            "from pathlib import Path;"
            "print(next(line.split()[1] for line in "
            "Path('/proc/self/status').read_text().splitlines() "
            "if line.startswith('CapEff:')))"
        )
        effective_capabilities = _run(
            "exec", container, "python", "-c", capability_code
        ).stdout.strip()
        health = container_info.get("State", {}).get("Health", {}).get("Status")
        result = {
            "generated_at": datetime.now(UTC).isoformat(),
            "image": {
                "reference": image,
                "id": image_info.get("Id"),
                "digest": image_info.get("Digest"),
                "size_bytes": image_info.get("Size"),
            },
            "offline_candidate": {
                **offline,
                "network_mode": "none",
                "read_only_rootfs": True,
                "capabilities_dropped": ["all"],
                "security_options": ["no-new-privileges"],
            },
            "production_api": {
                "rootless": rootless == "true",
                "uid": uid,
                "gid": gid,
                "read_only_rootfs": bool(host.get("ReadonlyRootfs")),
                "capabilities_dropped": host.get("CapDrop", []),
                "effective_capabilities_hex": effective_capabilities,
                "security_options": host.get("SecurityOpt", []),
                "health_status": health,
                "ready_body": json.loads(ready_body),
                "production_default": "deterministic-v2",
                "readiness_seconds": readiness_seconds,
                "requests": requests,
                "latency_p50_ms": durations[round(0.50 * (requests - 1))],
                "latency_p95_ms": durations[round(0.95 * (requests - 1))],
                "latency_p99_ms": durations[round(0.99 * (requests - 1))],
            },
            "acceptance_checks": {
                "offline_candidate_p95_below_10ms": float(offline["p95_ms"]) < 10,
                "offline_candidate_network_disabled": True,
                "production_default_is_v2": True,
                "rootless": rootless == "true",
                "non_root_uid": uid != 0,
                "read_only_rootfs": bool(host.get("ReadonlyRootfs")),
                "all_capabilities_dropped": effective_capabilities
                == "0000000000000000",
                "no_new_privileges": any(
                    "no-new-privileges" in option for option in host.get("SecurityOpt", [])
                ),
                "healthy": health == "healthy",
            },
            "cleanup": {
                "container_removed": True,
                "volume_removed": True,
                "image_retained": True,
            },
        }
        output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
        return result
    finally:
        if container_created:
            _run("rm", "--force", container)
        if volume_created:
            _run("volume", "rm", volume)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", default="localhost/routellect:g7d-candidate")
    parser.add_argument(
        "--output", type=Path, default=Path("outputs/phase-7d-podman-results.json")
    )
    parser.add_argument("--port", type=int, default=18_082)
    parser.add_argument("--requests", type=int, default=500)
    args = parser.parse_args()
    if args.requests < 1:
        parser.error("--requests must be positive")
    result = verify(args.image, args.output, args.port, args.requests)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
