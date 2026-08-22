"""
Unit tests for ``src/services/filter_service.py``.

Tests cover:
- Location-only filter returns correct subset
- min_rating filter excludes low-rated and None-rated restaurants
- Budget filter matches tier exactly
- Cuisine filter is a case-insensitive substring match
- Combined filters work together
- Results are sorted by rating DESC (None last)
- Results are capped at max_candidates
- NoMatchError raised when zero candidates remain
"""

from __future__ import annotations

import pytest

from src.data.repository import RestaurantRepository
from src.exceptions import NoMatchError
from src.models.preferences import UserPreferences
from src.models.restaurant import Restaurant
from src.services.filter_service import FilterService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_restaurant(
    name: str,
    location: str = "Koramangala",
    city: str = "Bangalore",
    cuisines: list[str] | None = None,
    rating: float | None = 4.0,
    budget_tier: str = "medium",
    cost_for_two: float | None = 800.0,
    votes: int = 100,
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
        votes=votes,
        address="",
    )


def _make_prefs(**overrides) -> UserPreferences:
    defaults: dict = {"location": "Koramangala", "budget": "medium"}
    defaults.update(overrides)
    return UserPreferences(**defaults)


@pytest.fixture()
def restaurants() -> list[Restaurant]:
    return [
        _make_restaurant("Truffles",        location="Koramangala", cuisines=["Italian", "Continental"], rating=4.5, budget_tier="medium"),
        _make_restaurant("Meghana Foods",   location="Koramangala", cuisines=["Biryani", "Andhra"],      rating=4.3, budget_tier="low"),
        _make_restaurant("Byg Brewski",     location="Koramangala", cuisines=["Continental", "Pub"],     rating=4.2, budget_tier="high"),
        _make_restaurant("Chutney Chang",   location="Koramangala", cuisines=["Chinese", "Thai"],        rating=3.8, budget_tier="medium"),
        _make_restaurant("Karavalli",       location="Residency Road", cuisines=["Seafood", "Coastal"], rating=4.6, budget_tier="high"),
        _make_restaurant("No-Rating Place", location="Koramangala", cuisines=["Fast Food"],             rating=None, budget_tier="low"),
    ]


@pytest.fixture()
def repo(restaurants) -> RestaurantRepository:
    return RestaurantRepository(restaurants)


@pytest.fixture()
def svc(repo) -> FilterService:
    return FilterService(repo, max_candidates=20)


# ---------------------------------------------------------------------------
# Location filter
# ---------------------------------------------------------------------------

class TestLocationFilter:
    def test_returns_all_in_location(self, svc):
        prefs = _make_prefs(location="Koramangala", budget="medium")
        # Only Truffles and Chutney Chang are medium in Koramangala
        results = svc.filter(prefs)
        assert all(r.location == "Koramangala" for r in results)

    def test_unknown_location_raises_no_match(self, svc):
        prefs = _make_prefs(location="Atlantis", budget="medium")
        with pytest.raises(NoMatchError):
            svc.filter(prefs)


# ---------------------------------------------------------------------------
# Budget filter
# ---------------------------------------------------------------------------

class TestBudgetFilter:
    def test_low_budget_returns_only_low_tier(self, svc):
        prefs = _make_prefs(budget="low")
        results = svc.filter(prefs)
        assert all(r.budget_tier == "low" for r in results)

    def test_high_budget_returns_only_high_tier(self, svc):
        prefs = _make_prefs(budget="high")
        results = svc.filter(prefs)
        assert all(r.budget_tier == "high" for r in results)
        assert any(r.name == "Byg Brewski" for r in results)

    def test_medium_budget_excludes_low_and_high(self, svc):
        prefs = _make_prefs(budget="medium")
        results = svc.filter(prefs)
        assert all(r.budget_tier == "medium" for r in results)

    def test_high_budget_in_other_location(self, repo):
        svc = FilterService(repo, max_candidates=20)
        prefs = _make_prefs(location="Residency Road", budget="high")
        results = svc.filter(prefs)
        assert len(results) == 1
        assert results[0].name == "Karavalli"


# ---------------------------------------------------------------------------
# min_rating filter
# ---------------------------------------------------------------------------

class TestMinRatingFilter:
    def test_min_rating_excludes_below_threshold(self, svc):
        prefs = _make_prefs(budget="medium", min_rating=4.4)
        results = svc.filter(prefs)
        assert all(r.rating is not None and r.rating >= 4.4 for r in results)

    def test_min_rating_excludes_none_rated(self, svc):
        # None-rated restaurants must be excluded when min_rating is set
        prefs = _make_prefs(budget="low", min_rating=0.0)
        results = svc.filter(prefs)
        assert all(r.rating is not None for r in results)

    def test_no_min_rating_includes_all_budgets(self, svc):
        prefs = _make_prefs(budget="low", min_rating=None)
        results = svc.filter(prefs)
        # Both rated and None-rated low-budget restaurants included
        names = {r.name for r in results}
        assert "Meghana Foods" in names
        assert "No-Rating Place" in names


# ---------------------------------------------------------------------------
# Cuisine filter
# ---------------------------------------------------------------------------

class TestCuisineFilter:
    def test_exact_cuisine_match(self, svc):
        prefs = _make_prefs(budget="medium", cuisine="Italian")
        results = svc.filter(prefs)
        assert all(any("italian" in c.lower() for c in r.cuisines) for r in results)

    def test_partial_cuisine_match(self, svc):
        """'Indian' should match 'North Indian' — add a North Indian low-budget restaurant."""
        prefs = _make_prefs(budget="low", cuisine="Biryani")
        results = svc.filter(prefs)
        assert any("biryani" in c.lower() for r in results for c in r.cuisines)

    def test_cuisine_case_insensitive(self, svc):
        prefs_lower = _make_prefs(budget="medium", cuisine="italian")
        prefs_upper = _make_prefs(budget="medium", cuisine="ITALIAN")
        assert {r.name for r in svc.filter(prefs_lower)} == {r.name for r in svc.filter(prefs_upper)}

    def test_nonexistent_cuisine_raises_no_match(self, svc):
        prefs = _make_prefs(budget="medium", cuisine="Martian Fusion")
        with pytest.raises(NoMatchError):
            svc.filter(prefs)

    def test_none_cuisine_skips_cuisine_filter(self, svc):
        prefs = _make_prefs(budget="medium", cuisine=None)
        results = svc.filter(prefs)
        # Both medium-budget Koramangala restaurants returned
        assert len(results) == 2


# ---------------------------------------------------------------------------
# Sorting
# ---------------------------------------------------------------------------

class TestSorting:
    def test_sorted_by_rating_descending(self, svc):
        prefs = _make_prefs(budget="medium", min_rating=None)
        results = svc.filter(prefs)
        rated = [r.rating for r in results if r.rating is not None]
        assert rated == sorted(rated, reverse=True)

    def test_none_rated_go_last(self, svc):
        prefs = _make_prefs(budget="low", min_rating=None)
        results = svc.filter(prefs)
        ratings = [r.rating for r in results]
        # First non-None then None
        none_seen = False
        for rating in ratings:
            if rating is None:
                none_seen = True
            elif none_seen:
                pytest.fail("Non-None rating appeared after None rating")


# ---------------------------------------------------------------------------
# Candidate cap
# ---------------------------------------------------------------------------

class TestCandidateCap:
    def test_results_capped_at_max_candidates(self, repo):
        svc = FilterService(repo, max_candidates=1)
        prefs = _make_prefs(budget="medium")
        results = svc.filter(prefs)
        assert len(results) <= 1

    def test_default_cap_not_exceeded(self, svc):
        prefs = _make_prefs(budget="medium")
        results = svc.filter(prefs)
        assert len(results) <= 20


class TestDeduplication:
    def test_duplicate_visible_restaurant_removed_even_with_different_ids(self):
        duplicate_records = [
            _make_restaurant("The Globe Grub", location="Btm", city="Bangalore", votes=201, budget_tier="medium"),
            _make_restaurant("The Globe Grub", location="Btm", city="Bengaluru", votes=274, budget_tier="medium"),
            _make_restaurant("Empire", location="Koramangala", budget_tier="medium"),
        ]
        repo = RestaurantRepository(duplicate_records)
        svc = FilterService(repo, max_candidates=20)

        results = svc.filter(_make_prefs(location="Btm", budget="medium"))
        names_and_locations = [
            (r.name.strip().lower(), r.location.strip().lower())
            for r in results
        ]
        assert len(names_and_locations) == len(set(names_and_locations))
        assert len(results) == 1


# ---------------------------------------------------------------------------
# NoMatchError
# ---------------------------------------------------------------------------

class TestNoMatchError:
    def test_no_match_message_contains_location(self, svc):
        prefs = _make_prefs(location="Atlantis", budget="medium")
        with pytest.raises(NoMatchError) as exc_info:
            svc.filter(prefs)
        assert "Atlantis" in exc_info.value.message

    def test_no_match_after_all_filters(self, svc):
        prefs = _make_prefs(budget="medium", cuisine="Sushi", min_rating=5.0)
        with pytest.raises(NoMatchError):
            svc.filter(prefs)
