"""
Integration tests for the FastAPI application (Phase 5).

Strategy
--------
* Use FastAPI's ``TestClient`` (synchronous httpx wrapper).
* Override ``app.state`` directly and use ``app.dependency_overrides`` to
  inject a pre-built repository and services — no real dataset download.
* ``MockLLMProvider`` is used so no real LLM calls are made.

Tests cover:
- GET /health returns 200 with dataset_loaded=True
- POST /api/v1/recommendations returns 200 with ranked results
- POST /api/v1/recommendations with invalid body returns 400
- POST /api/v1/recommendations with unknown location returns 400
- POST /api/v1/recommendations with no matching restaurants returns 404
- GET /api/v1/meta/locations returns sorted list
- GET /api/v1/meta/cuisines returns sorted list
- OpenAPI schema is accessible at /openapi.json
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.data.repository import RestaurantRepository
from src.llm.fallback import FallbackRanker
from src.llm.prompt_builder import PromptBuilder
from src.llm.provider import MockLLMProvider
from src.main import create_app
from src.models.restaurant import Restaurant
from src.services.filter_service import FilterService
from src.services.metadata_service import MetadataService
from src.services.recommendation_service import RecommendationService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_restaurant(
    name: str,
    location: str = "Koramangala",
    city: str = "Bangalore",
    cuisines: list[str] | None = None,
    rating: float | None = 4.2,
    budget_tier: str = "medium",
    cost_for_two: float | None = 900.0,
) -> Restaurant:
    return Restaurant(
        restaurant_id=Restaurant.make_id(name, location, city),
        name=name,
        city=city,
        location=location,
        cuisines=cuisines or ["North Indian"],
        rating=rating,
        budget_tier=budget_tier,  # type: ignore[arg-type]
        cost_for_two=cost_for_two,
        votes=100,
        address="",
    )


@pytest.fixture()
def restaurants() -> list[Restaurant]:
    return [
        _make_restaurant("Truffles", rating=4.5, cuisines=["Continental", "Italian"]),
        _make_restaurant("Empire", rating=4.2, cuisines=["North Indian"]),
        _make_restaurant("Meghana Foods", rating=4.4, cuisines=["Biryani"]),
        _make_restaurant(
            "Cheap Eats", budget_tier="low", cost_for_two=300.0, rating=3.9
        ),
        _make_restaurant(
            "Luxury Dine", budget_tier="high", cost_for_two=2500.0, rating=4.7
        ),
    ]


@pytest.fixture()
def repo(restaurants: list[Restaurant]) -> RestaurantRepository:
    return RestaurantRepository(restaurants)


def _build_test_client(
    repo: RestaurantRepository,
    fail_with: str | None = None,
) -> TestClient:
    """Create a ``TestClient`` with pre-wired services (no real startup)."""
    app = create_app()

    llm = MockLLMProvider(fail_with=fail_with)
    filter_svc = FilterService(repo, max_candidates=20)
    prompt_builder = PromptBuilder(max_candidates=20)
    rec_svc = RecommendationService(
        filter_service=filter_svc,
        prompt_builder=prompt_builder,
        llm_provider=llm,
        fallback_ranker=FallbackRanker(),
    )
    meta_svc = MetadataService(repo)

    # Bypass the lifespan by pre-setting app.state
    app.state.repository = repo
    app.state.recommendation_service = rec_svc
    app.state.metadata_service = meta_svc
    app.state.dataset_loaded = True
    app.state.record_count = repo.count()

    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# /health
# ---------------------------------------------------------------------------


def test_health_ok(repo: RestaurantRepository) -> None:
    client = _build_test_client(repo)
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["dataset_loaded"] is True
    assert data["record_count"] == repo.count()


# ---------------------------------------------------------------------------
# POST /api/v1/recommendations — happy path
# ---------------------------------------------------------------------------


def test_recommendations_returns_200(repo: RestaurantRepository) -> None:
    client = _build_test_client(repo)
    resp = client.post(
        "/api/v1/recommendations",
        json={"location": "Koramangala", "budget": "medium"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "recommendations" in data
    assert len(data["recommendations"]) >= 1


def test_recommendations_response_schema(repo: RestaurantRepository) -> None:
    client = _build_test_client(repo)
    resp = client.post(
        "/api/v1/recommendations",
        json={"location": "Koramangala", "budget": "medium", "limit": 2},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["recommendations"]) <= 2
    for rec in data["recommendations"]:
        assert "rank" in rec
        assert "explanation" in rec
        assert "restaurant" in rec
        r = rec["restaurant"]
        assert "name" in r
        assert "rating" in r
        assert "cuisines" in r


def test_recommendations_source_llm(repo: RestaurantRepository) -> None:
    client = _build_test_client(repo)
    resp = client.post(
        "/api/v1/recommendations",
        json={"location": "Koramangala", "budget": "medium"},
    )
    assert resp.json()["source"] == "llm"


def test_recommendations_fallback_on_llm_error(repo: RestaurantRepository) -> None:
    client = _build_test_client(repo, fail_with="Simulated LLM timeout")
    resp = client.post(
        "/api/v1/recommendations",
        json={"location": "Koramangala", "budget": "medium"},
    )
    assert resp.status_code == 200
    assert resp.json()["source"] == "fallback"


def test_recommendations_with_cuisine_filter(repo: RestaurantRepository) -> None:
    client = _build_test_client(repo)
    resp = client.post(
        "/api/v1/recommendations",
        json={"location": "Koramangala", "budget": "medium", "cuisine": "Italian"},
    )
    assert resp.status_code == 200


def test_recommendations_with_min_rating(repo: RestaurantRepository) -> None:
    client = _build_test_client(repo)
    resp = client.post(
        "/api/v1/recommendations",
        json={"location": "Koramangala", "budget": "medium", "min_rating": 4.0},
    )
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# POST /api/v1/recommendations — validation errors (400)
# ---------------------------------------------------------------------------


def test_recommendations_missing_location_returns_400(repo: RestaurantRepository) -> None:
    client = _build_test_client(repo)
    resp = client.post(
        "/api/v1/recommendations",
        json={"budget": "medium"},
    )
    assert resp.status_code == 400


def test_recommendations_missing_budget_returns_400(repo: RestaurantRepository) -> None:
    client = _build_test_client(repo)
    resp = client.post(
        "/api/v1/recommendations",
        json={"location": "Koramangala"},
    )
    assert resp.status_code == 400


def test_recommendations_invalid_budget_returns_400(repo: RestaurantRepository) -> None:
    client = _build_test_client(repo)
    resp = client.post(
        "/api/v1/recommendations",
        json={"location": "Koramangala", "budget": "ultra-premium"},
    )
    assert resp.status_code == 400


def test_recommendations_invalid_rating_returns_400(repo: RestaurantRepository) -> None:
    client = _build_test_client(repo)
    resp = client.post(
        "/api/v1/recommendations",
        json={"location": "Koramangala", "budget": "medium", "min_rating": 6.0},
    )
    assert resp.status_code == 400


def test_recommendations_unknown_location_returns_400(repo: RestaurantRepository) -> None:
    client = _build_test_client(repo)
    resp = client.post(
        "/api/v1/recommendations",
        json={"location": "Atlantis", "budget": "medium"},
    )
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# POST /api/v1/recommendations — no match (404)
# ---------------------------------------------------------------------------


def test_recommendations_no_match_returns_404(repo: RestaurantRepository) -> None:
    """Cuisine that doesn't exist → NoMatchError → 404."""
    client = _build_test_client(repo)
    resp = client.post(
        "/api/v1/recommendations",
        json={"location": "Koramangala", "budget": "medium", "cuisine": "Molecular Gastronomy"},
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/v1/meta/locations
# ---------------------------------------------------------------------------


def test_meta_locations_returns_200(repo: RestaurantRepository) -> None:
    client = _build_test_client(repo)
    resp = client.get("/api/v1/meta/locations")
    assert resp.status_code == 200
    data = resp.json()
    assert "locations" in data
    assert "count" in data
    assert data["count"] == len(data["locations"])


def test_meta_locations_contains_koramangala(repo: RestaurantRepository) -> None:
    client = _build_test_client(repo)
    resp = client.get("/api/v1/meta/locations")
    locations = resp.json()["locations"]
    assert any("koramangala" in loc.lower() for loc in locations)


def test_meta_locations_sorted(repo: RestaurantRepository) -> None:
    client = _build_test_client(repo)
    locations = client.get("/api/v1/meta/locations").json()["locations"]
    assert locations == sorted(locations)


# ---------------------------------------------------------------------------
# GET /api/v1/meta/cuisines
# ---------------------------------------------------------------------------


def test_meta_cities_returns_200(repo: RestaurantRepository) -> None:
    client = _build_test_client(repo)
    resp = client.get("/api/v1/meta/cities")
    assert resp.status_code == 200
    data = resp.json()
    assert "cities" in data
    assert "count" in data
    assert data["count"] == len(data["cities"])


def test_meta_cities_uses_location_values_not_city_column(
    repo: RestaurantRepository,
) -> None:
    custom_repo = RestaurantRepository(
        [
            _make_restaurant("Spot A", location="Koramangala", city="Bangalore"),
            _make_restaurant("Spot B", location="Anna Nagar", city="Chennai"),
            _make_restaurant("Spot C", location="Indiranagar", city="Bangalore"),
        ]
    )
    client = _build_test_client(custom_repo)
    cities = client.get("/api/v1/meta/cities").json()["cities"]
    assert "Koramangala" in cities
    assert "Anna Nagar" in cities
    assert "Indiranagar" in cities
    assert "Bangalore" not in cities
    assert "Chennai" not in cities


def test_meta_cities_matches_locations(repo: RestaurantRepository) -> None:
    client = _build_test_client(repo)
    cities = client.get("/api/v1/meta/cities").json()["cities"]
    locations = client.get("/api/v1/meta/locations").json()["locations"]
    assert cities == locations


def test_meta_cuisines_returns_200(repo: RestaurantRepository) -> None:
    client = _build_test_client(repo)
    resp = client.get("/api/v1/meta/cuisines")
    assert resp.status_code == 200
    data = resp.json()
    assert "cuisines" in data
    assert "count" in data
    assert data["count"] == len(data["cuisines"])


def test_meta_cuisines_sorted(repo: RestaurantRepository) -> None:
    client = _build_test_client(repo)
    cuisines = client.get("/api/v1/meta/cuisines").json()["cuisines"]
    assert cuisines == sorted(cuisines)


def test_meta_cuisines_non_empty(repo: RestaurantRepository) -> None:
    client = _build_test_client(repo)
    cuisines = client.get("/api/v1/meta/cuisines").json()["cuisines"]
    assert len(cuisines) > 0


# ---------------------------------------------------------------------------
# OpenAPI schema
# ---------------------------------------------------------------------------


def test_openapi_schema_accessible(repo: RestaurantRepository) -> None:
    client = _build_test_client(repo)
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    schema = resp.json()
    assert "openapi" in schema
    assert "paths" in schema
