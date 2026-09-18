from __future__ import annotations

import json
import math
import os
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from importlib.resources import files
from pathlib import Path
from typing import Literal

from pydantic import Field

from routellect.schemas import AssessorMode, AssessorReport, PromptProfile, StrictModel

ALLOWED_TASKS = {
    "general",
    "code",
    "reasoning",
    "research",
    "writing",
    "summarization",
    "extraction",
    "agent",
}
ALLOWED_CAPABILITIES = {
    "text",
    "vision",
    "audio",
    "tools",
    "structured_output",
    "long_context",
    "reasoning",
    "code",
}


class SemanticAssessment(StrictModel):
    task_family: Literal[
        "general",
        "code",
        "reasoning",
        "research",
        "writing",
        "summarization",
        "extraction",
        "agent",
    ]
    difficulty: Literal["low", "medium", "high", "uncertain"]
    required_capabilities: set[str] = Field(default_factory=lambda: {"text"})
    privacy_flags: list[str] = Field(default_factory=list, max_length=8)
    confidence: float = Field(ge=0, le=1)
    reason_codes: list[str] = Field(default_factory=list, max_length=5)


class AssessorUnavailableError(RuntimeError):
    pass


class LocalAssessor:
    """Bounded local semantic assessor with deterministic fallback.

    The backend accepts prompt text and returns a JSON string. Tests can inject a backend;
    production lazily creates an in-process llama.cpp backend from the pinned GGUF artifact.
    """

    def __init__(
        self,
        backend: Callable[[str], str] | None = None,
        *,
        model_path: str | None = None,
        threshold: float | None = None,
        timeout_seconds: float | None = None,
    ) -> None:
        self._backend = backend
        self._model_path = Path(
            model_path
            or os.getenv("ROUTELLECT_ASSESSOR_MODEL", "/opt/routellect/models/assessor.gguf")
        )
        self._threshold = threshold or float(os.getenv("ROUTELLECT_ASSESSOR_THRESHOLD", "0.55"))
        self._timeout = timeout_seconds or float(os.getenv("ROUTELLECT_ASSESSOR_TIMEOUT", "5.0"))
        self._lock = threading.Lock()
        self._circuit_open = False
        self.version = "smollm2-360m-embedding-prototypes-v1@sha256:48ab3034d0dd"

    def should_invoke(self, profile: PromptProfile, mode: AssessorMode) -> bool:
        return mode == AssessorMode.ALWAYS or (
            mode == AssessorMode.AUTO and profile.uncertainty >= self._threshold
        )

    def assess(self, prompt: str, profile: PromptProfile, mode: AssessorMode) -> PromptProfile:
        if mode == AssessorMode.OFF:
            return self._with_report(profile, mode, "disabled")
        if not self.should_invoke(profile, mode):
            return self._with_report(profile, mode, "not_needed")
        if self._circuit_open:
            return self._with_report(profile, mode, "unavailable", invoked=False, fallback=True)

        started = time.perf_counter()
        executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="routellect-assessor")

        def invoke() -> str:
            backend = self._backend
            if backend is None:
                if not self._model_path.is_file():
                    raise AssessorUnavailableError(str(self._model_path))
                try:
                    backend = self._load_llama_backend()
                except (ImportError, OSError, RuntimeError) as exc:
                    raise AssessorUnavailableError from exc
            return backend(prompt)

        future = executor.submit(invoke)
        try:
            raw = future.result(timeout=self._timeout)
        except TimeoutError:
            future.cancel()
            executor.shutdown(wait=False, cancel_futures=True)
            self._circuit_open = True
            return self._with_report(
                profile,
                mode,
                "timed_out",
                invoked=True,
                fallback=True,
                latency_ms=(time.perf_counter() - started) * 1000,
            )
        except AssessorUnavailableError:
            executor.shutdown(wait=False, cancel_futures=True)
            self._circuit_open = True
            return self._with_report(
                profile,
                mode,
                "unavailable",
                invoked=False,
                fallback=True,
                latency_ms=(time.perf_counter() - started) * 1000,
            )
        except Exception:
            executor.shutdown(wait=False, cancel_futures=True)
            return self._with_report(
                profile,
                mode,
                "invalid_output",
                invoked=True,
                fallback=True,
                latency_ms=(time.perf_counter() - started) * 1000,
            )
        else:
            executor.shutdown(wait=True)

        latency_ms = (time.perf_counter() - started) * 1000
        try:
            assessment = SemanticAssessment.model_validate_json(self._extract_json(raw))
            if not assessment.required_capabilities <= ALLOWED_CAPABILITIES:
                raise ValueError("unsupported assessor capability")
        except (ValueError, json.JSONDecodeError):
            return self._with_report(
                profile,
                mode,
                "invalid_output",
                invoked=True,
                fallback=True,
                latency_ms=latency_ms,
            )
        return self._merge(profile, assessment, mode, latency_ms)

    def _load_llama_backend(self) -> Callable[[str], str]:
        with self._lock:
            if self._backend is not None:
                return self._backend
            from llama_cpp import Llama

            prototype_artifact = json.loads(
                files("routellect")
                .joinpath("data/assessor_prototypes.json")
                .read_text(encoding="utf-8")
            )
            if prototype_artifact.get("model_version") != (
                "smollm2-360m-instruct-q8_0@sha256:48ab3034d0dd"
            ):
                raise RuntimeError("assessor prototype/model version mismatch")
            dimensions = int(prototype_artifact["dimensions"])
            prototypes = prototype_artifact["prototypes"]
            if not prototypes or any(len(vector) != dimensions for vector in prototypes.values()):
                raise RuntimeError("invalid assessor prototype artifact")

            model = Llama(
                model_path=str(self._model_path),
                n_ctx=2048,
                n_threads=max(1, min(8, os.cpu_count() or 1)),
                n_batch=256,
                n_ubatch=256,
                verbose=False,
                embedding=True,
                pooling_type=1,
            )

            def run(prompt: str) -> str:
                with self._lock:
                    result = model.create_embedding(prompt[:8_000])
                vector = [float(value) for value in result["data"][0]["embedding"]]
                norm = math.sqrt(sum(value * value for value in vector))
                if not math.isfinite(norm) or norm == 0 or len(vector) != dimensions:
                    raise ValueError("invalid assessor embedding")
                normalized = [value / norm for value in vector]
                scores = sorted(
                    (
                        sum(
                            value * float(reference)
                            for value, reference in zip(normalized, proto, strict=True)
                        ),
                        task,
                    )
                    for task, proto in prototypes.items()
                )
                best_score, best_task = scores[-1]
                margin = max(0.0, best_score - scores[-2][0])
                confidence = min(0.9, 0.55 + 5 * margin)
                return json.dumps(
                    {
                        "task_family": best_task,
                        "difficulty": "low",
                        "required_capabilities": ["text"],
                        "privacy_flags": [],
                        "confidence": confidence,
                        "reason_codes": ["semantic_embedding_match"],
                    },
                    separators=(",", ":"),
                )

            self._backend = run
            return run

    @staticmethod
    def _extract_json(raw: str) -> str:
        start = raw.find("{")
        end = raw.rfind("}")
        if start < 0 or end <= start:
            raise json.JSONDecodeError("no JSON object", raw, 0)
        return raw[start : end + 1]

    def _merge(
        self,
        profile: PromptProfile,
        assessment: SemanticAssessment,
        mode: AssessorMode,
        latency_ms: float,
    ) -> PromptProfile:
        use_semantic_task = assessment.confidence >= 0.65 and profile.uncertainty >= 0.45
        task = assessment.task_family if use_semantic_task else profile.task_family
        difficulty_order = {"low": 0, "medium": 1, "high": 2, "uncertain": 1}
        difficulty = max(
            (profile.difficulty, assessment.difficulty), key=lambda value: difficulty_order[value]
        )
        return profile.model_copy(
            update={
                "task_family": task,
                "difficulty": difficulty,
                "required_capabilities": profile.required_capabilities
                | assessment.required_capabilities,
                "privacy_flags": sorted(set(profile.privacy_flags + assessment.privacy_flags)),
                "uncertainty": min(profile.uncertainty, 1 - assessment.confidence),
                "reason_codes": list(dict.fromkeys(profile.reason_codes + assessment.reason_codes))[
                    :6
                ],
                "assessor": AssessorReport(
                    mode=mode,
                    invoked=True,
                    status="completed",
                    assessor_version=self.version,
                    confidence=assessment.confidence,
                    latency_ms=latency_ms,
                ),
            }
        )

    def _with_report(
        self,
        profile: PromptProfile,
        mode: AssessorMode,
        status: str,
        *,
        invoked: bool = False,
        fallback: bool = False,
        latency_ms: float = 0,
    ) -> PromptProfile:
        return profile.model_copy(
            update={
                "assessor": AssessorReport(
                    mode=mode,
                    invoked=invoked,
                    status=status,
                    assessor_version=self.version if invoked else None,
                    fallback_used=fallback,
                    latency_ms=latency_ms,
                )
            }
        )
