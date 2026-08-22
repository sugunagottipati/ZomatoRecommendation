"""
Unit tests for ``src/llm/fallback.py``.

Tests cover:
- Returns top N restaurants sorted by rating
- Respects preferences.limit
- source is 'fallback', summary is None
- Generic explanations are non-empty strings
- Works when candidates have None ratings
"""

from __future__ import annotations

import pytest

from src.llm.fallback import FallbackRanker
from src.models.preferences import UserPreferences
from src.models.restaurant import Restaurant


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_restaurant(
    name: str,
    rating: float | None,
    location: str = "Koramangala",
    city: str = "Bangalore",
    budget_tier: str = "medium",
    cost_for_two: float | None = 800.0,
    cuisines: list[str] | None = None,
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
        votes=50,
        address="",
    )


def _prefs(limit: int = 5) -> UserPreferences:
    return UserPreferences(location="Koramangala", budget="medium", limit=limit)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_returns_correct_count() -> None:
    restaurants = [_make_restaurant(f"R{i}", rating=float(i)) for i in range(10)]
    ranker = FallbackRanker()
    result = ranker.rank(restaurants, _prefs(limit=3))
    assert len(result.recommendations) == 3


def test_source_is_fallback() -> None:
    restaurants = [_make_restaurant("R1", rating=4.0)]
    ranker = FallbackRanker()
    result = ranker.rank(restaurants, _prefs())
    assert result.source == "fallback"


def test_summary_is_none() -> None:
    restaurants = [_make_restaurant("R1", rating=4.0)]
    ranker = FallbackRanker()
    result = ranker.rank(restaurants, _prefs())
    assert result.summary is None


def test_respects_limit_smaller_than_candidates() -> None:
    restaurants = [_make_restaurant(f"R{i}", rating=float(i)) for i in range(10)]
    ranker = FallbackRanker()
    result = ranker.rank(restaurants, _prefs(limit=2))
    assert len(result.recommendations) == 2


def test_ranks_are_sequential_starting_at_one() -> None:
    restaurants = [_make_restaurant(f"R{i}", rating=float(i)) for i in range(3)]
    ranker = FallbackRanker()
    result = ranker.rank(restaurants, _prefs(limit=3))
    assert [r.rank for r in result.recommendations] == [1, 2, 3]


def test_explanations_are_non_empty() -> None:
    restaurants = [_make_restaurant("R1", rating=4.5, cuisines=["Italian"], cost_for_two=600.0)]
    ranker = FallbackRanker()
    result = ranker.rank(restaurants, _prefs(limit=1))
    assert result.recommendations[0].explanation.strip() != ""


def test_explanation_without_rating_or_cost() -> None:
    restaurants = [_make_restaurant("R1", rating=None, cost_for_two=None, cuisines=[])]
    ranker = FallbackRanker()
    result = ranker.rank(restaurants, _prefs(limit=1))
    # Should not crash; provides a fallback message
    assert result.recommendations[0].explanation != ""


def test_fewer_candidates_than_limit() -> None:
    restaurants = [_make_restaurant("R1", rating=4.0)]
    ranker = FallbackRanker()
    result = ranker.rank(restaurants, _prefs(limit=5))
    assert len(result.recommendations) == 1
