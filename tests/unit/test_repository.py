"""
Unit tests for ``src/data/repository.py``.

Tests cover:
- Index construction (count, cities, cuisines)
- find_by_location (case-insensitive, unknown city)
- find_by_cuisine (case-insensitive, unknown cuisine)
- get_by_id (hit, miss)
- get_all_locations (sorted, de-duplicated)
- get_all_cuisines (sorted, de-duplicated)
- Iteration and len()
- Empty repository edge case
"""

from __future__ import annotations

import pytest

from src.data.repository import RestaurantRepository
from src.models.restaurant import Restaurant


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_restaurant(
    name: str,
    city: str = "Bangalore",
    location: str = "Koramangala",
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


@pytest.fixture()
def sample_restaurants() -> list[Restaurant]:
    return [
        _make_restaurant("Truffles", city="Bangalore", location="Koramangala", cuisines=["Italian", "Continental"]),
        _make_restaurant("Meghana Foods", city="Bangalore", location="Indiranagar", cuisines=["Biryani", "Andhra"]),
        _make_restaurant("Karavalli", city="Bangalore", location="Residency Road", cuisines=["Seafood", "Coastal"]),
        _make_restaurant("Buhari", city="Chennai", location="Anna Nagar", cuisines=["Biryani", "Mughlai"]),
        _make_restaurant("Saravana Bhavan", city="Chennai", location="T Nagar", cuisines=["South Indian"]),
    ]


@pytest.fixture()
def repo(sample_restaurants) -> RestaurantRepository:
    return RestaurantRepository(sample_restaurants)


# ---------------------------------------------------------------------------
# Basic construction
# ---------------------------------------------------------------------------

class TestRepositoryConstruction:
    def test_count_matches_input(self, repo, sample_restaurants):
        assert repo.count() == len(sample_restaurants)

    def test_len_matches_count(self, repo):
        assert len(repo) == repo.count()

    def test_repr_contains_counts(self, repo):
        r = repr(repo)
        assert "RestaurantRepository(" in r
        assert "records=5" in r
        assert "locations=" in r


# ---------------------------------------------------------------------------
# find_by_location
# ---------------------------------------------------------------------------

class TestFindByLocation:
    def test_known_location_returns_correct_restaurant(self, repo):
        results = repo.find_by_location("Koramangala")
        assert len(results) == 1
        assert results[0].name == "Truffles"

    def test_lookup_is_case_insensitive(self, repo):
        lower = repo.find_by_location("koramangala")
        upper = repo.find_by_location("KORAMANGALA")
        title = repo.find_by_location("Koramangala")
        assert {r.restaurant_id for r in lower} == {r.restaurant_id for r in upper} == {r.restaurant_id for r in title}

    def test_unknown_location_returns_empty_list(self, repo):
        assert repo.find_by_location("NonExistentArea") == []

    def test_city_name_does_not_match(self, repo):
        """City names are not indexed — only neighbourhood locations are."""
        assert repo.find_by_location("Bangalore") == []
        assert repo.find_by_location("Chennai") == []

    def test_different_location_returns_correct_restaurant(self, repo):
        results = repo.find_by_location("Anna Nagar")
        assert len(results) == 1
        assert results[0].name == "Buhari"

    def test_returns_list_not_reference(self, repo):
        """Mutating the returned list should not affect the index."""
        results = repo.find_by_location("Koramangala")
        original_len = len(results)
        results.clear()
        assert len(repo.find_by_location("Koramangala")) == original_len


# ---------------------------------------------------------------------------
# find_by_cuisine
# ---------------------------------------------------------------------------

class TestFindByCuisine:
    def test_known_cuisine_returns_correct_results(self, repo):
        results = repo.find_by_cuisine("Biryani")
        assert len(results) == 2
        names = {r.name for r in results}
        assert "Meghana Foods" in names
        assert "Buhari" in names

    def test_case_insensitive_cuisine_lookup(self, repo):
        lower = repo.find_by_cuisine("biryani")
        upper = repo.find_by_cuisine("BIRYANI")
        assert {r.restaurant_id for r in lower} == {r.restaurant_id for r in upper}

    def test_unknown_cuisine_returns_empty(self, repo):
        assert repo.find_by_cuisine("Martian Fusion") == []

    def test_multi_cuisine_restaurant_indexed_under_all_cuisines(self, repo):
        italian = repo.find_by_cuisine("Italian")
        continental = repo.find_by_cuisine("Continental")
        assert any(r.name == "Truffles" for r in italian)
        assert any(r.name == "Truffles" for r in continental)


# ---------------------------------------------------------------------------
# get_by_id
# ---------------------------------------------------------------------------

class TestGetById:
    def test_known_id_returns_restaurant(self, repo, sample_restaurants):
        target = sample_restaurants[0]
        result = repo.get_by_id(target.restaurant_id)
        assert result is not None
        assert result.name == target.name

    def test_unknown_id_returns_none(self, repo):
        assert repo.get_by_id("nonexistent_id_xyz") is None


# ---------------------------------------------------------------------------
# get_all_locations
# ---------------------------------------------------------------------------

class TestGetAllLocations:
    def test_returns_sorted_list(self, repo):
        locations = repo.get_all_locations()
        assert locations == sorted(locations)

    def test_no_duplicates(self, repo):
        locations = repo.get_all_locations()
        assert len(locations) == len(set(locations))

    def test_contains_known_locations(self, repo):
        locations = repo.get_all_locations()
        assert "Koramangala" in locations
        assert "Indiranagar" in locations
        assert "Anna Nagar" in locations

    def test_does_not_contain_city_names(self, repo):
        locations = repo.get_all_locations()
        assert "Bangalore" not in locations
        assert "Chennai" not in locations

    def test_count_matches_unique_location_fields(self, repo):
        # 5 restaurants each with a distinct location
        assert len(repo.get_all_locations()) == 5


# ---------------------------------------------------------------------------
# get_all_cuisines
# ---------------------------------------------------------------------------

class TestGetAllCuisines:
    def test_returns_sorted_list(self, repo):
        cuisines = repo.get_all_cuisines()
        assert cuisines == sorted(cuisines)

    def test_no_duplicates(self, repo):
        cuisines = repo.get_all_cuisines()
        assert len(cuisines) == len(set(cuisines))

    def test_contains_known_cuisines(self, repo):
        cuisines = repo.get_all_cuisines()
        assert "Biryani" in cuisines
        assert "Italian" in cuisines
        assert "South Indian" in cuisines


# ---------------------------------------------------------------------------
# Iteration
# ---------------------------------------------------------------------------

class TestIteration:
    def test_iteration_yields_all_restaurants(self, repo, sample_restaurants):
        collected = list(repo)
        assert len(collected) == len(sample_restaurants)

    def test_iteration_order_matches_insertion(self, repo, sample_restaurants):
        collected = list(repo)
        assert [r.name for r in collected] == [r.name for r in sample_restaurants]


# ---------------------------------------------------------------------------
# Empty repository
# ---------------------------------------------------------------------------

class TestEmptyRepository:
    def setup_method(self):
        self.repo = RestaurantRepository([])

    def test_count_is_zero(self):
        assert self.repo.count() == 0

    def test_find_by_location_returns_empty(self):
        assert self.repo.find_by_location("Koramangala") == []

    def test_find_by_cuisine_returns_empty(self):
        assert self.repo.find_by_cuisine("Italian") == []

    def test_get_all_locations_empty(self):
        assert self.repo.get_all_locations() == []

    def test_get_all_cuisines_empty(self):
        assert self.repo.get_all_cuisines() == []
