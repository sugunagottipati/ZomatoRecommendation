"""
POST /api/v1/recommendations — generate ranked restaurant recommendations.
"""

from __future__ import annotations

import logging
import time

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import ValidationError

from src.api.dependencies import get_recommendation_service
from src.exceptions import NoMatchError
from src.models.preferences import UserPreferences
from src.models.recommendation import RecommendationResponse
from src.services.recommendation_service import RecommendationService

logger = logging.getLogger(__name__)

router = APIRouter()


class RecommendationRequest(UserPreferences):
    """Request body for the recommendations endpoint.

    Inherits all fields and validators from ``UserPreferences``.
    Documented separately so FastAPI renders clean OpenAPI schema.
    """


@router.post(
    "/recommendations",
    response_model=RecommendationResponse,
    summary="Generate restaurant recommendations",
    description=(
        "Filter the Zomato dataset by the supplied preferences, then use an LLM "
        "to rank and explain the best matches.  Falls back to rating-based ranking "
        "when the LLM is unavailable."
    ),
    status_code=status.HTTP_200_OK,
)
def recommend(
    body: RecommendationRequest,
    request: Request,
    service: RecommendationService = Depends(get_recommendation_service),
) -> RecommendationResponse:
    start = time.perf_counter()

    # Service-level location validation (requires repository knowledge)
    repository = request.app.state.repository
    try:
        body.validate_against_repository(repository)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    try:
        result = service.recommend(body)
    except NoMatchError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=exc.message,
        ) from exc

    elapsed_ms = (time.perf_counter() - start) * 1000
    logger.info(
        "POST /recommendations completed in %.1f ms — %d results (source=%s).",
        elapsed_ms,
        len(result.recommendations),
        result.source,
    )
    return result
