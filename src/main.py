"""
FastAPI application entry point.

Startup sequence (lifespan handler)
------------------------------------
1. Load and preprocess the Zomato dataset (or read from local cache).
2. Build the ``RestaurantRepository`` in-memory index.
3. Construct ``FilterService``, ``PromptBuilder``, ``LLMProvider``,
   ``FallbackRanker``, and ``RecommendationService``.
4. Attach all service instances to ``app.state`` for use by dependencies.

Running
-------
    uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
"""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from src.api.routes import metadata as metadata_router
from src.api.routes import recommendations as recommendations_router
from src.config import get_settings
from src.data.loader import DatasetLoader
from src.data.preprocessor import Preprocessor
from src.data.repository import RestaurantRepository
from src.llm.fallback import FallbackRanker
from src.llm.prompt_builder import PromptBuilder
from src.llm.provider import build_provider
from src.services.metadata_service import MetadataService
from src.services.filter_service import FilterService
from src.services.recommendation_service import RecommendationService

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lifespan — dataset loading and service wiring
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Load the dataset and wire services before the server accepts requests."""
    settings = get_settings()

    logging.basicConfig(
        level=getattr(logging, settings.log_level, logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    logger.info("Starting up — loading dataset (this may take a moment)…")
    t0 = time.perf_counter()

    loader = DatasetLoader(
        dataset_id=settings.hf_dataset_id,
        cache_dir=settings.cache_dir,
    )
    raw_df = loader.load()

    preprocessor = Preprocessor(cache_dir=settings.cache_dir)
    restaurants = preprocessor.preprocess(raw_df)

    repository = RestaurantRepository(restaurants)
    logger.info(
        "Dataset ready: %d restaurants loaded in %.1f s.",
        repository.count(),
        time.perf_counter() - t0,
    )

    llm_provider = build_provider(settings)
    filter_service = FilterService(repository, max_candidates=settings.max_candidates)
    prompt_builder = PromptBuilder(max_candidates=settings.max_candidates)
    fallback_ranker = FallbackRanker()
    recommendation_service = RecommendationService(
        filter_service=filter_service,
        prompt_builder=prompt_builder,
        llm_provider=llm_provider,
        fallback_ranker=fallback_ranker,
    )
    metadata_service = MetadataService(repository)

    # Attach to app.state for dependency injection
    app.state.repository = repository
    app.state.recommendation_service = recommendation_service
    app.state.metadata_service = metadata_service
    app.state.dataset_loaded = True
    app.state.record_count = repository.count()

    yield

    # Shutdown — nothing to clean up for an in-memory store
    logger.info("Shutting down.")


# ---------------------------------------------------------------------------
# App creation
# ---------------------------------------------------------------------------


def create_app() -> FastAPI:
    app = FastAPI(
        title="Zomato AI Restaurant Recommendations",
        description=(
            "AI-powered restaurant recommendation API backed by the Zomato dataset. "
            "Filters candidates by location, budget, cuisine, and rating, then uses "
            "an LLM to rank and explain the best matches."
        ),
        version="1.0.0",
        lifespan=lifespan,
    )

    # ------------------------------------------------------------------
    # Middleware — per-request logging
    # ------------------------------------------------------------------

    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "%s %s → %d (%.1f ms)",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
        )
        return response

    # ------------------------------------------------------------------
    # Exception handlers
    # ------------------------------------------------------------------

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": exc.errors()},
        )

    @app.exception_handler(ValidationError)
    async def pydantic_error_handler(
        request: Request, exc: ValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": exc.errors()},
        )

    @app.exception_handler(Exception)
    async def generic_error_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        logger.exception("Unhandled error for %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "An unexpected error occurred. Please try again later."},
        )

    # ------------------------------------------------------------------
    # Routes
    # ------------------------------------------------------------------

    @app.get(
        "/health",
        summary="Health check",
        description="Returns dataset load status and record count.",
        tags=["Health"],
    )
    def health(request: Request) -> dict:
        loaded: bool = getattr(request.app.state, "dataset_loaded", False)
        count: int = getattr(request.app.state, "record_count", 0)
        return {
            "status": "ok" if loaded else "starting",
            "dataset_loaded": loaded,
            "record_count": count,
        }

    app.include_router(
        recommendations_router.router,
        prefix="/api/v1",
        tags=["Recommendations"],
    )
    app.include_router(
        metadata_router.router,
        prefix="/api/v1/meta",
        tags=["Metadata"],
    )

    return app


app = create_app()
