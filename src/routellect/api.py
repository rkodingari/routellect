from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from importlib.resources import files
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.responses import Response

from routellect import __version__
from routellect.advisor import Advisor
from routellect.benchmark import run_builtin_benchmark
from routellect.catalog import CatalogManager
from routellect.learning import FeedbackLearner
from routellect.schemas import (
    BenchmarkRun,
    BenchmarkRunRequest,
    CatalogImportResult,
    CatalogRollbackResult,
    CatalogSummary,
    DeletionResult,
    FeedbackExport,
    FeedbackReplayReport,
    FeedbackRequest,
    FeedbackResponse,
    FeedbackSettings,
    FeedbackSettingsUpdate,
    PersonalizationPromotionRequest,
    PromotionAudit,
    RecommendationRequest,
    RecommendationResponse,
)
from routellect.security import TokenBucketLimiter
from routellect.storage import (
    DuplicateFeedbackError,
    FeedbackDisabledError,
    InvalidFeedbackError,
    Store,
)

advisor = Advisor()
store = Store()
catalog_manager = CatalogManager()
MAX_REQUEST_BYTES = int(os.getenv("ROUTELLECT_MAX_REQUEST_BYTES", "1048576"))
WRITE_RATE_PER_MINUTE = int(os.getenv("ROUTELLECT_RATE_LIMIT_PER_MINUTE", "600"))
write_limiter = TokenBucketLimiter(WRITE_RATE_PER_MINUTE)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    store.initialize()
    yield


app = FastAPI(
    title="Routellect API",
    version=__version__,
    description="Advisory-only model selection. No target model execution or provider credentials.",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url=None,
)


@app.middleware("http")
async def security_headers(request: Request, call_next):  # type: ignore[no-untyped-def]
    response: Response | None
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                too_large = int(content_length) > MAX_REQUEST_BYTES
            except ValueError:
                too_large = True
            if too_large:
                response = JSONResponse(
                    status_code=413,
                    content={"detail": "Request body exceeds the configured limit"},
                )
            else:
                response = None
        else:
            response = None
        if response is None:
            client = request.client.host if request.client else "local"
            allowed, retry_after = write_limiter.allow(client)
            if not allowed:
                response = JSONResponse(
                    status_code=429,
                    content={"detail": "Write request rate limit exceeded"},
                    headers={"Retry-After": str(retry_after)},
                )
        if response is None:
            response = await call_next(request)
    else:
        response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self'; "
        "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'"
    )
    response.headers["Cache-Control"] = "no-store"
    return response


@app.exception_handler(ValueError)
async def value_error_handler(_: Request, exc: ValueError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "type": "about:blank",
            "title": "Request could not be completed",
            "status": 422,
            "detail": str(exc),
        },
        media_type="application/problem+json",
    )


@app.get("/health/live")
def liveness() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


@app.get("/health/ready")
def readiness() -> dict[str, str]:
    return {
        "status": "ok",
        "version": __version__,
        "catalog_version": catalog_manager.current().version,
    }


@app.post("/v1/model-recommendations", response_model=RecommendationResponse)
def create_recommendation(request: RecommendationRequest) -> RecommendationResponse:
    active_advisor = Advisor(
        catalog=catalog_manager.current(),
        assessor=advisor.assessor,
        feedback_signals=FeedbackLearner(store).signals,
    )
    response = active_advisor.recommend(request)
    store.save_recommendation(
        response,
        objective=request.objective.value,
        privacy=request.privacy.value,
        feedback_profile_id=request.feedback_profile_id,
    )
    return response


@app.get("/v1/model-recommendations/{recommendation_id}")
def get_recommendation_receipt(recommendation_id: str) -> dict[str, object]:
    receipt = store.get_receipt(recommendation_id)
    if receipt is None:
        raise HTTPException(status_code=404, detail="Recommendation receipt not found")
    return receipt


@app.post(
    "/v1/model-recommendations/{recommendation_id}/feedback",
    response_model=FeedbackResponse,
    status_code=201,
)
def create_feedback(recommendation_id: str, feedback: FeedbackRequest) -> FeedbackResponse:
    try:
        response = store.save_feedback(recommendation_id, feedback)
    except FeedbackDisabledError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except DuplicateFeedbackError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except InvalidFeedbackError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if response is None:
        raise HTTPException(status_code=404, detail="Recommendation receipt not found")
    return response


@app.get("/v1/catalog/summary", response_model=CatalogSummary)
def catalog_summary() -> CatalogSummary:
    return catalog_manager.summary()


@app.post("/v1/catalog/import", response_model=CatalogImportResult)
def import_catalog(payload: dict[str, object]) -> CatalogImportResult:
    previous, summary = catalog_manager.import_envelope(payload)
    return CatalogImportResult(previous_catalog_version=previous, catalog=summary)


@app.post("/v1/catalog/rollback", response_model=CatalogRollbackResult)
def rollback_catalog() -> CatalogRollbackResult:
    replaced, summary = catalog_manager.rollback()
    return CatalogRollbackResult(replaced_catalog_version=replaced, catalog=summary)


@app.get("/v1/feedback/settings", response_model=FeedbackSettings)
def get_feedback_settings() -> FeedbackSettings:
    return store.get_feedback_settings()


@app.patch("/v1/feedback/settings", response_model=FeedbackSettings)
def update_feedback_settings(update: FeedbackSettingsUpdate) -> FeedbackSettings:
    return store.update_feedback_settings(update)


@app.post("/v1/feedback/personalization/promote", response_model=FeedbackReplayReport)
def promote_personalization(
    request: PersonalizationPromotionRequest,
) -> FeedbackReplayReport:
    return FeedbackLearner(store).replay_and_promote(request.feedback_profile_id)


@app.post(
    "/v1/feedback/personalization/rollback", response_model=PromotionAudit
)
def rollback_personalization(
    request: PersonalizationPromotionRequest,
) -> PromotionAudit:
    return store.rollback_personalization(request.feedback_profile_id)


@app.get("/v1/feedback/personalization/audit")
def list_personalization_audit() -> dict[str, list[PromotionAudit]]:
    return {"items": store.list_promotions()}


@app.get("/v1/feedback/export", response_model=FeedbackExport)
def export_feedback() -> FeedbackExport:
    return store.export_feedback()


@app.get("/v1/feedback/history")
def feedback_history() -> dict[str, object]:
    exported = store.export_feedback()
    return {
        "prompt_included": False,
        "items": list(reversed(exported.items[-100:])),
    }


@app.delete("/v1/feedback/{feedback_id}", response_model=DeletionResult)
def delete_feedback(feedback_id: str) -> DeletionResult:
    result = store.delete_feedback(feedback_id)
    if result.deleted == 0:
        raise HTTPException(status_code=404, detail="Feedback item not found")
    return result


@app.delete("/v1/feedback", response_model=DeletionResult)
def reset_feedback() -> DeletionResult:
    return store.reset_feedback()


@app.get("/v1/benchmarks/runs")
def list_benchmark_runs() -> dict[str, list[BenchmarkRun]]:
    return {"items": store.list_benchmarks()}


@app.post("/v1/benchmarks/runs", response_model=BenchmarkRun, status_code=202)
def create_benchmark_run(request: BenchmarkRunRequest) -> BenchmarkRun:
    active_advisor = Advisor(
        catalog=catalog_manager.current(),
        assessor=advisor.assessor,
        feedback_signals=FeedbackLearner(store).signals,
    )
    run = run_builtin_benchmark(request, active_advisor)
    store.save_benchmark(run)
    return run


@app.get("/v1/benchmarks/runs/{run_id}", response_model=BenchmarkRun)
def get_benchmark_run(run_id: str) -> BenchmarkRun:
    run = store.get_benchmark(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Benchmark run not found")
    return run


development_static = Path(__file__).resolve().parents[2] / "frontend" / "dist"
static_directory = (
    development_static if development_static.is_dir() else files("routellect").joinpath("static")
)
app.mount("/", StaticFiles(directory=str(static_directory), html=True), name="dashboard")
