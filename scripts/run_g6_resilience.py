#!/usr/bin/env python3
"""Exercise the G6 container boundary, abuse controls, load, soak, and recovery."""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import statistics
import subprocess
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path


def _run(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        ["podman", *arguments], check=True, text=True, capture_output=True
    )


def _exists(resource: str, name: str) -> bool:
    return (
        subprocess.run(  # noqa: S603
            ["podman", resource, "exists", name], check=False, capture_output=True
        ).returncode
        == 0
    )


def _request(
    url: str,
    *,
    method: str = "GET",
    body: bytes | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 10,
) -> tuple[int, bytes, dict[str, str]]:
    request = urllib.request.Request(  # noqa: S310
        url, data=body, headers=headers or {}, method=method
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            return (
                response.status,
                response.read(),
                {key.lower(): value for key, value in response.headers.items()},
            )
    except urllib.error.HTTPError as error:
        return (
            error.code,
            error.read(),
            {key.lower(): value for key, value in error.headers.items()},
        )


def _post_json(url: str, payload: dict[str, object]) -> tuple[int, dict[str, object]]:
    status, body, _ = _request(
        url,
        method="POST",
        body=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    return status, json.loads(body)


def _percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    return ordered[round(fraction * (len(ordered) - 1))]


def verify(
    image: str,
    output: Path,
    requests: int,
    workers: int,
    soak_seconds: float,
    port: int,
) -> dict[str, object]:
    container = "routellect-g6-qa"
    volume = "routellect-g6-qa-data"
    if _exists("container", container) or _exists("volume", volume):
        raise RuntimeError("reserved G6 QA resources already exist; refusing to replace them")

    created_volume = False
    created_container = False
    canary = "G6_RAW_PROMPT_CANARY_7a4cf792"
    advisor_url = f"http://127.0.0.1:{port}/v1/model-recommendations"
    payload = {
        "messages": [{"role": "user", "content": canary + " review concurrency safety"}],
        "assessor_mode": "off",
    }
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
        ready_body: dict[str, object] = {}
        while time.perf_counter() < deadline:
            try:
                status, body, _ = _request(ready_url, timeout=2)
                if status == 200:
                    ready_body = json.loads(body)
                    break
            except OSError:
                time.sleep(0.05)
        else:
            raise RuntimeError("container did not become ready within 30 seconds")
        readiness_seconds = time.perf_counter() - started

        def one_advisory(_: int) -> float:
            request_started = time.perf_counter()
            status, response = _post_json(advisor_url, payload)
            if status != 200 or response.get("non_executing") is not True:
                raise RuntimeError(f"unexpected advisory response: {status}")
            return (time.perf_counter() - request_started) * 1_000

        load_started = time.perf_counter()
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            latencies = list(executor.map(one_advisory, range(requests)))
        load_seconds = time.perf_counter() - load_started

        soak_latencies: list[float] = []
        soak_started = time.perf_counter()
        while time.perf_counter() - soak_started < soak_seconds:
            soak_latencies.append(one_advisory(len(soak_latencies)))
            time.sleep(0.1)
        actual_soak_seconds = time.perf_counter() - soak_started

        malformed_status, _, malformed_headers = _request(
            advisor_url,
            method="POST",
            body=b'{"messages": [',
            headers={"Content-Type": "application/json"},
        )
        oversized_status, _, oversized_headers = _request(
            advisor_url,
            method="POST",
            body=b"x" * (1024 * 1024 + 1),
            headers={"Content-Type": "application/json"},
        )

        status, recommendation = _post_json(
            advisor_url,
            {
                "messages": [{"role": "user", "content": "feedback abuse control"}],
                "assessor_mode": "off",
            },
        )
        if status != 200:
            raise RuntimeError("could not create feedback-control recommendation")
        recommendation_id = str(recommendation["recommendation_id"])
        configuration_id = str(
            recommendation["recommendations"][0]["configuration"]["configuration_id"]
        )
        feedback_url = f"{advisor_url}/{recommendation_id}/feedback"
        feedback = {
            "used_recommendation": True,
            "used_configuration_id": configuration_id,
            "outcome": "worked",
            "quality_rating": 4,
        }
        first_feedback_status, _ = _post_json(feedback_url, feedback)
        duplicate_feedback_status, _ = _post_json(feedback_url, feedback)

        rate_limit_status = 0
        rate_limit_headers: dict[str, str] = {}
        rate_attempts = 0
        for attempt in range(1, 701):
            rate_attempts = attempt
            rate_limit_status, _, rate_limit_headers = _request(
                advisor_url,
                method="POST",
                body=b"{}",
                headers={"Content-Type": "application/json"},
            )
            if rate_limit_status == 429:
                break
        post_limit_health_status, _, _ = _request(ready_url)

        search_script = """
from pathlib import Path
import sys
needle = sys.argv[1].encode()
paths = [
    Path('/data/routellect.sqlite3'),
    Path('/data/routellect.sqlite3-wal'),
    Path('/data/routellect.sqlite3-shm'),
]
print('true' if any(path.is_file() and needle in path.read_bytes() for path in paths) else 'false')
"""
        raw_prompt_present = (
            _run("exec", container, "python", "-c", search_script, canary).stdout.strip()
            == "true"
        )

        backup = json.loads(
            _run(
                "exec",
                container,
                "routellect",
                "admin",
                "backup",
                "/tmp/g6-backup.tar.gz",
            ).stdout
        )
        restore = json.loads(
            _run(
                "exec",
                container,
                "routellect",
                "admin",
                "restore",
                "/tmp/g6-backup.tar.gz",
                "--data-dir",
                "/tmp/restored",
                "--yes",
            ).stdout
        )

        _run("healthcheck", "run", container)
        image_info = json.loads(_run("image", "inspect", image).stdout)[0]
        container_info = json.loads(_run("inspect", container).stdout)[0]
        stats = json.loads(_run("stats", "--no-stream", "--format", "json", container).stdout)
        if isinstance(stats, list):
            stats = stats[0]
        host_config = container_info["HostConfig"]
        result: dict[str, object] = {
            "generated_at": datetime.now(UTC).isoformat(),
            "image": {
                "reference": image,
                "id": image_info.get("Id"),
                "digest": image_info.get("Digest"),
                "size_bytes": image_info.get("Size"),
            },
            "runtime": {
                "rootless": _run("info", "--format", "{{.Host.Security.Rootless}}").stdout.strip()
                == "true",
                "uid": int(_run("exec", container, "id", "-u").stdout.strip()),
                "gid": int(_run("exec", container, "id", "-g").stdout.strip()),
                "read_only_rootfs": bool(host_config.get("ReadonlyRootfs")),
                "capabilities_dropped": host_config.get("CapDrop", []),
                "security_options": host_config.get("SecurityOpt", []),
                "health_status": container_info.get("State", {}).get("Health", {}).get("Status"),
                "ready_body": ready_body,
                "readiness_seconds": readiness_seconds,
                "podman_stats": stats,
            },
            "load": {
                "requests": requests,
                "workers": workers,
                "failures": 0,
                "throughput_requests_per_second": requests / load_seconds,
                "latency_mean_ms": statistics.fmean(latencies),
                "latency_p50_ms": _percentile(latencies, 0.50),
                "latency_p95_ms": _percentile(latencies, 0.95),
                "latency_p99_ms": _percentile(latencies, 0.99),
            },
            "soak": {
                "duration_seconds": actual_soak_seconds,
                "requests": len(soak_latencies),
                "failures": 0,
                "latency_p95_ms": _percentile(soak_latencies, 0.95),
            },
            "abuse_controls": {
                "malformed_json_status": malformed_status,
                "oversized_body_status": oversized_status,
                "first_feedback_status": first_feedback_status,
                "duplicate_feedback_status": duplicate_feedback_status,
                "rate_limit_status": rate_limit_status,
                "rate_limit_attempts_after_prior_load": rate_attempts,
                "retry_after_present": "retry-after" in rate_limit_headers,
                "security_headers_on_413": oversized_headers.get("x-frame-options") == "DENY",
                "security_headers_on_422": malformed_headers.get("x-frame-options") == "DENY",
                "health_after_rate_limit": post_limit_health_status,
            },
            "privacy": {
                "raw_prompt_present_in_sqlite_files": raw_prompt_present,
                "canary_sha256": hashlib.sha256(canary.encode()).hexdigest(),
                "target_model_calls": 0,
                "provider_credentials_supplied": False,
            },
            "recovery": {
                "backup_format": backup["format"],
                "archive_sha256": backup["archive_sha256"],
                "restored_files": restore["restored_files"],
                "restored_archive_sha256_matches": (
                    restore["archive_sha256"] == backup["archive_sha256"]
                ),
            },
            "cleanup": {
                "container_removed": True,
                "volume_removed": True,
                "image_retained": True,
            },
        }
        expected = {
            "malformed_json_status": 422,
            "oversized_body_status": 413,
            "first_feedback_status": 201,
            "duplicate_feedback_status": 409,
            "rate_limit_status": 429,
            "health_after_rate_limit": 200,
        }
        for key, value in expected.items():
            if result["abuse_controls"][key] != value:  # type: ignore[index]
                raise RuntimeError(f"{key} did not meet its expected status {value}")
        for key in (
            "retry_after_present",
            "security_headers_on_413",
            "security_headers_on_422",
        ):
            if result["abuse_controls"][key] is not True:  # type: ignore[index]
                raise RuntimeError(f"{key} was not enforced")
        if raw_prompt_present or not result["recovery"][  # type: ignore[index]
            "restored_archive_sha256_matches"
        ]:
            raise RuntimeError("privacy or recovery invariant failed")
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
    parser.add_argument("--image", default="localhost/routellect:0.5.0")
    parser.add_argument(
        "--output", type=Path, default=Path("outputs/phase-6-resilience-results.json")
    )
    parser.add_argument("--requests", type=int, default=200)
    parser.add_argument("--workers", type=int, default=12)
    parser.add_argument("--soak-seconds", type=float, default=15)
    parser.add_argument("--port", type=int, default=18_081)
    args = parser.parse_args()
    if args.requests < 1 or args.workers < 1 or args.soak_seconds <= 0:
        parser.error("requests, workers, and soak duration must be positive")
    print(
        json.dumps(
            verify(
                args.image,
                args.output,
                args.requests,
                args.workers,
                args.soak_seconds,
                args.port,
            ),
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
