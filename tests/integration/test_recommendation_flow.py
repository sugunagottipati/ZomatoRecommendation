"""
Integration test for the full recommendation flow (end-to-end with mock LLM).

Tests cover:
- Full pipeline: FilterService → PromptBuilder → MockLLMProvider → ResponseParser
- RecommendationService.recommend() returns LLM-sourced recommendations
- Fallback activates when MockLLMProvider is configured to fail
- NoMatchError propagates when no candidates match filters
- Fallback response has source='fallback' and summary=None
"""

from __future__ import annotations

import pytest

from src.data.repository import RestaurantRepository
from src.exceptions import NoMatchError
from src.llm.fallback import FallbackRanker
from src.llm.prompt_builder import PromptBuilder
from src.llm.provider import MockLLMProvider
from src.models.preferences import UserPreferences
from src.models.restaurant import Restaurant
from src.services.filter_service import FilterService
from src.services.recommendation_service import RecommendationService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_restaurant(
    name: str,
    location: str = "Koramangala",
    city: str = "Bangalore",
    cuisines: list[str] | None = None,
    rating: float | None = 4.0,
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
        _make_restaurant("Onesta", rating=4.1, cuisines=["Italian", "Pizza"]),
        _make_restaurant("B-Blunt", rating=3.8, cuisines=["Cafe"]),
        _make_restaurant(
            "High Budget Place",
            budget_tier="high",
            cost_for_two=2000.0,
            rating=4.6,
        ),
    ]


@pytest.fixture()
def repo(restaurants: list[Restaurant]) -> RestaurantRepository:
    return RestaurantRepository(restaurants)


def _build_service(
    repo: RestaurantRepository,
    fail_with: str | None = None,
    summary: str = "Great matches.",
) -> RecommendationService:
    return RecommendationService(
        filter_service=FilterService(repo, max_candidates=20),
        prompt_builder=PromptBuilder(max_candidates=20),
        llm_provider=MockLLMProvider(summary=summary, fail_with=fail_with),
        fallback_ranker=FallbackRanker(),
    )


def _prefs(**overrides) -> UserPreferences:
    defaults: dict = {"location": "Koramangala", "budget": "medium", "limit": 3}
    defaults.update(overrides)
    return UserPreferences(**defaults)


# ---------------------------------------------------------------------------
# Happy-path: LLM succeeds
# ---------------------------------------------------------------------------


def test_llm_path_returns_recommendations(repo: RestaurantRepository) -> None:
    service = _build_service(repo, summary="Excellent choices for you.")
    result = service.recommend(_prefs())

    assert result.source == "llm"
    assert result.summary == "Excellent choices for you."
    assert len(result.recommendations) <= 3
    assert all(r.rank >= 1 for r in result.recommendations)


def test_llm_path_respects_limit(repo: RestaurantRepository) -> None:
    service = _build_service(repo)
    result = service.recommend(_prefs(limit=2))
    assert len(result.recommendations) <= 2


def test_llm_path_enriches_metadata(repo: RestaurantRepository) -> None:
    service = _build_service(repo)
    result = service.recommend(_prefs())

    for rec in result.recommendations:
        # Each recommendation should have a full Restaurant object
        assert rec.restaurant.name
        assert rec.restaurant.restaurant_id
        assert isinstance(rec.explanation, str)


def test_cuisine_filter_applied(repo: RestaurantRepository) -> None:
    """Only Italian restaurants should be candidates — MockLLM picks from them."""
    service = _build_service(repo)
    result = service.recommend(_prefs(cuisine="Italian"))

    assert result.source == "llm"
    for rec in result.recommendations:
        assert any(
            "italian" in c.lower() for c in rec.restaurant.cuisines
        ), f"Expected Italian cuisine for {rec.restaurant.name}"


# ---------------------------------------------------------------------------
# Fallback path
# ---------------------------------------------------------------------------


def test_fallback_activates_on_llm_error(repo: RestaurantRepository) -> None:
    service = _build_service(repo, fail_with="Simulated API timeout")
    result = service.recommend(_prefs())

    assert result.source == "fallback"
    assert result.summary is None
    assert len(result.recommendations) >= 1


def test_fallback_recommendations_have_explanations(repo: RestaurantRepository) -> None:
    service = _build_service(repo, fail_with="Simulated error")
    result = service.recommend(_prefs())

    for rec in result.recommendations:
        assert rec.explanation.strip() != ""


def test_fallback_respects_limit(repo: RestaurantRepository) -> None:
    service = _build_service(repo, fail_with="error")
    result = service.recommend(_prefs(limit=2))
    assert len(result.recommendations) <= 2


# ---------------------------------------------------------------------------
# No-match path
# ---------------------------------------------------------------------------


def test_no_match_raises_no_match_error(repo: RestaurantRepository) -> None:
    service = _build_service(repo)
    with pytest.raises(NoMatchError):
        service.recommend(_prefs(location="NonExistentCity123"))


def test_no_match_unknown_cuisine_raises(repo: RestaurantRepository) -> None:
    """If cuisine filter removes all candidates, NoMatchError should propagate."""
    service = _build_service(repo)
    # "Sushi" doesn't exist in our fixture data
    with pytest.raises(NoMatchError):
        service.recommend(_prefs(cuisine="Sushi"))
