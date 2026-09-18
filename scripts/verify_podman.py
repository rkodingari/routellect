#!/usr/bin/env python3
"""Measure the hardened Routellect Podman release candidate and clean up QA resources."""

from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path


def _run(*arguments: str, capture: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        ["podman", *arguments],
        check=True,
        text=True,
        capture_output=capture,
    )


def _exists(resource: str, name: str) -> bool:
    result = subprocess.run(  # noqa: S603
        ["podman", resource, "exists", name],
        check=False,
        capture_output=True,
    )
    return result.returncode == 0


def _request(url: str, timeout: float = 2.0) -> tuple[int, bytes]:
    with urllib.request.urlopen(url, timeout=timeout) as response:  # noqa: S310
        return response.status, response.read()


def _post_json(url: str, payload: dict[str, object]) -> tuple[int, dict[str, object]]:
    body = json.dumps(payload).encode()
    request = urllib.request.Request(  # noqa: S310
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=5) as response:  # noqa: S310
        return response.status, json.loads(response.read())


def verify(image: str, output: Path, requests: int, port: int) -> dict[str, object]:
    container = "routellect-g5-qa"
    volume = "routellect-g5-qa-data"
    if _exists("container", container) or _exists("volume", volume):
        raise RuntimeError("reserved QA container or volume already exists; refusing to replace it")

    created_volume = False
    created_container = False
    try:
        _run("volume", "create", volume)
        created_volume = True
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
        created_container = True
        ready_url = f"http://127.0.0.1:{port}/health/ready"
        deadline = time.perf_counter() + 30
        body = b""
        while time.perf_counter() < deadline:
            try:
                status, body = _request(ready_url)
                if status == 200:
                    break
            except OSError:
                time.sleep(0.05)
        else:
            raise RuntimeError("container did not become ready within 30 seconds")
        readiness_seconds = time.perf_counter() - started

        advisor_url = f"http://127.0.0.1:{port}/v1/model-recommendations"
        payload = {
            "messages": [
                {
                    "role": "user",
                    "content": "Summarize this quarterly report into five key points.",
                }
            ],
            "assessor_mode": "off",
        }
        latencies_ms: list[float] = []
        throughput_started = time.perf_counter()
        for _ in range(requests):
            request_started = time.perf_counter()
            status, response_body = _post_json(advisor_url, payload)
            if status != 200 or response_body.get("non_executing") is not True:
                raise RuntimeError(f"unexpected advisory response: {status}")
            latencies_ms.append((time.perf_counter() - request_started) * 1_000)
        throughput_seconds = time.perf_counter() - throughput_started
        latencies_ms.sort()

        _run("healthcheck", "run", container)
        image_info = json.loads(_run("image", "inspect", image).stdout)[0]
        container_info = json.loads(_run("inspect", container).stdout)[0]
        stats_text = _run("stats", "--no-stream", "--format", "json", container).stdout
        stats = json.loads(stats_text)
        if isinstance(stats, list):
            stats = stats[0]
        uid = _run("exec", container, "id", "-u").stdout.strip()
        gid = _run("exec", container, "id", "-g").stdout.strip()
        rootless = _run("info", "--format", "{{.Host.Security.Rootless}}").stdout.strip()
        health = container_info.get("State", {}).get("Health", {}).get("Status")
        host_config = container_info["HostConfig"]
        result = {
            "generated_at": datetime.now(UTC).isoformat(),
            "image": {
                "reference": image,
                "id": image_info.get("Id"),
                "digest": image_info.get("Digest"),
                "size_bytes": image_info.get("Size"),
            },
            "runtime": {
                "rootless": rootless == "true",
                "uid": int(uid),
                "gid": int(gid),
                "read_only_rootfs": bool(host_config.get("ReadonlyRootfs")),
                "capabilities_dropped": host_config.get("CapDrop", []),
                "security_options": host_config.get("SecurityOpt", []),
                "health_status": health,
                "ready_body": json.loads(body),
            },
            "performance": {
                "readiness_seconds": readiness_seconds,
                "sequential_advisory_requests": requests,
                "advisory_throughput_requests_per_second": requests / throughput_seconds,
                "advisory_latency_p50_ms": latencies_ms[round(0.50 * (requests - 1))],
                "advisory_latency_p95_ms": latencies_ms[round(0.95 * (requests - 1))],
                "advisory_latency_mean_ms": statistics.fmean(latencies_ms),
                "podman_stats": stats,
            },
            "cleanup": {
                "container_removed": True,
                "volume_removed": True,
                "image_retained": True,
            },
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
    parser.add_argument("--image", default="localhost/routellect:0.4.0")
    parser.add_argument(
        "--output", type=Path, default=Path("outputs/phase-5-container-benchmark.json")
    )
    parser.add_argument("--requests", type=int, default=500)
    parser.add_argument("--port", type=int, default=18_080)
    args = parser.parse_args()
    if args.requests < 1:
        parser.error("--requests must be positive")
    result = verify(args.image, args.output, args.requests, args.port)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
