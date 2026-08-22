"""
FastAPI dependency providers.

All shared service instances are created once at startup and stored in
``app.state``.  Request handlers obtain them via these ``Depends`` callables
so they are testable via ``app.dependency_overrides``.
"""

from __future__ import annotations

from fastapi import Request

from src.data.repository import RestaurantRepository
from src.services.metadata_service import MetadataService
from src.services.recommendation_service import RecommendationService


def get_repository(request: Request) -> RestaurantRepository:
    """Return the application-wide ``RestaurantRepository``."""
    return request.app.state.repository  # type: ignore[no-any-return]


def get_recommendation_service(request: Request) -> RecommendationService:
    """Return the application-wide ``RecommendationService``."""
    return request.app.state.recommendation_service  # type: ignore[no-any-return]


def get_metadata_service(request: Request) -> MetadataService:
    """Return the application-wide ``MetadataService``."""
    return request.app.state.metadata_service  # type: ignore[no-any-return]
