"""
GET /api/v1/meta/locations  — list supported location/area names.
GET /api/v1/meta/cuisines   — list available cuisine types.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from src.api.dependencies import get_metadata_service
from src.services.metadata_service import MetadataService

router = APIRouter()


class LocationsResponse(BaseModel):
    locations: list[str]
    count: int


class CuisinesResponse(BaseModel):
    cuisines: list[str]
    count: int


class CitiesResponse(BaseModel):
    cities: list[str]
    count: int


@router.get(
    "/locations",
    response_model=LocationsResponse,
    summary="List supported locations",
    description="Returns all location/area names present in the loaded dataset, sorted alphabetically.",
)
def get_locations(
    service: MetadataService = Depends(get_metadata_service),
) -> LocationsResponse:
    locations = service.get_locations()
    return LocationsResponse(locations=locations, count=len(locations))


@router.get(
    "/cities",
    response_model=CitiesResponse,
    summary="List supported cities",
    description=(
        "Returns all supported location values present in the dataset, "
        "sorted alphabetically. Note: values come from the location field "
        "(locality/area), not the city column."
    ),
)
def get_cities(
    service: MetadataService = Depends(get_metadata_service),
) -> CitiesResponse:
    cities = service.get_cities()
    return CitiesResponse(cities=cities, count=len(cities))


@router.get(
    "/cuisines",
    response_model=CuisinesResponse,
    summary="List available cuisines",
    description="Returns all distinct cuisine types present in the loaded dataset, sorted alphabetically.",
)
def get_cuisines(
    service: MetadataService = Depends(get_metadata_service),
) -> CuisinesResponse:
    cuisines = service.get_cuisines()
    return CuisinesResponse(cuisines=cuisines, count=len(cuisines))
