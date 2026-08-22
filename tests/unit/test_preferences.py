"""
Unit tests for ``src/models/preferences.py``.

Tests cover:
- Valid input constructs correctly
- Location normalisation (trimming, title-casing)
- Cuisine normalisation (title-casing, empty → None)
- Additional preferences parsing (list, comma-separated string, None)
- Budget enum validation (invalid value rejected)
- min_rating range validation (0.0–5.0 boundaries; out-of-range rejected)
- limit defaults and bounds (min 1, max 20)
- Empty location rejected
- validate_against_repository (known city passes, unknown city raises)
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from src.models.preferences import UserPreferences, _MAX_LIMIT


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_prefs(**overrides) -> UserPreferences:
    """Return a valid ``UserPreferences`` with optional field overrides."""
    defaults: dict = {
        "location": "Koramangala",
        "budget": "medium",
    }
    defaults.update(overrides)
    return UserPreferences(**defaults)


def _make_mock_repo(known_cities: list[str]) -> MagicMock:
    """Return a mock repository whose ``get_all_locations`` returns *known_cities*."""
    repo = MagicMock()
    repo.get_all_locations.return_value = known_cities
    return repo


# ---------------------------------------------------------------------------
# Construction — valid inputs
# ---------------------------------------------------------------------------

class TestValidInputs:
    def test_minimal_valid_input(self):
        prefs = _make_prefs()
        assert prefs.location == "Koramangala"
        assert prefs.budget == "medium"
        assert prefs.cuisine is None
        assert prefs.min_rating is None
        assert prefs.additional_preferences == []
        assert prefs.limit == 5

    def test_all_fields_provided(self):
        prefs = _make_prefs(
            cuisine="Italian",
            min_rating=4.0,
            additional_preferences=["family-friendly", "outdoor"],
            limit=10,
        )
        assert prefs.cuisine == "Italian"
        assert prefs.min_rating == 4.0
        assert prefs.additional_preferences == ["family-friendly", "outdoor"]
        assert prefs.limit == 10

    def test_budget_low(self):
        prefs = _make_prefs(budget="low")
        assert prefs.budget == "low"

    def test_budget_high(self):
        prefs = _make_prefs(budget="high")
        assert prefs.budget == "high"


# ---------------------------------------------------------------------------
# Location normalisation
# ---------------------------------------------------------------------------

class TestLocationNormalisation:
    def test_leading_trailing_whitespace_stripped(self):
        prefs = _make_prefs(location="  Bangalore  ")
        assert prefs.location == "Bangalore"

    def test_location_title_cased(self):
        prefs = _make_prefs(location="new delhi")
        assert prefs.location == "New Delhi"

    def test_location_mixed_case_normalised(self):
        prefs = _make_prefs(location="MUMBAI")
        assert prefs.location == "Mumbai"


class TestLocationValidation:
    def test_empty_location_raises(self):
        with pytest.raises(ValidationError) as exc_info:
            _make_prefs(location="")
        assert "location" in str(exc_info.value).lower()

    def test_whitespace_only_location_raises(self):
        with pytest.raises(ValidationError):
            _make_prefs(location="   ")


# ---------------------------------------------------------------------------
# Budget validation
# ---------------------------------------------------------------------------

class TestBudgetValidation:
    def test_invalid_budget_raises(self):
        with pytest.raises(ValidationError) as exc_info:
            _make_prefs(budget="expensive")  # type: ignore[arg-type]
        assert "budget" in str(exc_info.value).lower()

    def test_uppercase_budget_rejected(self):
        """Budget must be lowercase; 'Medium' is not the same as 'medium'."""
        with pytest.raises(ValidationError):
            _make_prefs(budget="Medium")  # type: ignore[arg-type]

    def test_numeric_budget_rejected(self):
        with pytest.raises(ValidationError):
            _make_prefs(budget=500)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Cuisine normalisation
# ---------------------------------------------------------------------------

class TestCuisineNormalisation:
    def test_cuisine_title_cased(self):
        prefs = _make_prefs(cuisine="north indian")
        assert prefs.cuisine == "North Indian"

    def test_cuisine_leading_whitespace_stripped(self):
        prefs = _make_prefs(cuisine="  Italian  ")
        assert prefs.cuisine == "Italian"

    def test_empty_string_cuisine_becomes_none(self):
        prefs = _make_prefs(cuisine="")
        assert prefs.cuisine is None

    def test_whitespace_only_cuisine_becomes_none(self):
        prefs = _make_prefs(cuisine="   ")
        assert prefs.cuisine is None

    def test_none_cuisine_stays_none(self):
        prefs = _make_prefs(cuisine=None)
        assert prefs.cuisine is None


# ---------------------------------------------------------------------------
# min_rating validation
# ---------------------------------------------------------------------------

class TestMinRatingValidation:
    def test_valid_min_rating_zero(self):
        prefs = _make_prefs(min_rating=0.0)
        assert prefs.min_rating == 0.0

    def test_valid_min_rating_five(self):
        prefs = _make_prefs(min_rating=5.0)
        assert prefs.min_rating == 5.0

    def test_valid_mid_range(self):
        prefs = _make_prefs(min_rating=3.5)
        assert prefs.min_rating == 3.5

    def test_below_zero_raises(self):
        with pytest.raises(ValidationError) as exc_info:
            _make_prefs(min_rating=-0.1)
        assert "min_rating" in str(exc_info.value).lower()

    def test_above_five_raises(self):
        with pytest.raises(ValidationError) as exc_info:
            _make_prefs(min_rating=5.1)
        assert "min_rating" in str(exc_info.value).lower()

    def test_none_rating_accepted(self):
        prefs = _make_prefs(min_rating=None)
        assert prefs.min_rating is None


# ---------------------------------------------------------------------------
# additional_preferences parsing
# ---------------------------------------------------------------------------

class TestAdditionalPreferences:
    def test_list_input_preserved(self):
        prefs = _make_prefs(additional_preferences=["fast", "cheap"])
        assert prefs.additional_preferences == ["fast", "cheap"]

    def test_comma_separated_string_parsed(self):
        prefs = _make_prefs(additional_preferences="fast, cheap, outdoor")
        assert prefs.additional_preferences == ["fast", "cheap", "outdoor"]

    def test_none_input_becomes_empty_list(self):
        prefs = _make_prefs(additional_preferences=None)
        assert prefs.additional_preferences == []

    def test_empty_list_accepted(self):
        prefs = _make_prefs(additional_preferences=[])
        assert prefs.additional_preferences == []

    def test_whitespace_tags_stripped(self):
        prefs = _make_prefs(additional_preferences=["  family-friendly  ", "  rooftop  "])
        assert prefs.additional_preferences == ["family-friendly", "rooftop"]

    def test_empty_string_tags_removed(self):
        prefs = _make_prefs(additional_preferences="fast,,outdoor")
        assert prefs.additional_preferences == ["fast", "outdoor"]


# ---------------------------------------------------------------------------
# limit validation
# ---------------------------------------------------------------------------

class TestLimitValidation:
    def test_default_limit(self):
        prefs = _make_prefs()
        assert prefs.limit == 5

    def test_custom_limit(self):
        prefs = _make_prefs(limit=3)
        assert prefs.limit == 3

    def test_max_limit_accepted(self):
        prefs = _make_prefs(limit=_MAX_LIMIT)
        assert prefs.limit == _MAX_LIMIT

    def test_above_max_limit_raises(self):
        with pytest.raises(ValidationError) as exc_info:
            _make_prefs(limit=_MAX_LIMIT + 1)
        assert "limit" in str(exc_info.value).lower()

    def test_zero_limit_raises(self):
        with pytest.raises(ValidationError):
            _make_prefs(limit=0)

    def test_negative_limit_raises(self):
        with pytest.raises(ValidationError):
            _make_prefs(limit=-1)


# ---------------------------------------------------------------------------
# validate_against_repository
# ---------------------------------------------------------------------------

class TestValidateAgainstRepository:
    def test_known_location_passes(self):
        prefs = _make_prefs(location="Koramangala")
        repo = _make_mock_repo(["Koramangala", "Indiranagar", "Anna Nagar"])
        # Should not raise
        prefs.validate_against_repository(repo)

    def test_known_location_case_insensitive(self):
        prefs = _make_prefs(location="koramangala")  # will be normalised to "Koramangala"
        repo = _make_mock_repo(["Koramangala", "Indiranagar"])
        prefs.validate_against_repository(repo)

    def test_unknown_location_raises_value_error(self):
        prefs = _make_prefs(location="Atlantis")
        repo = _make_mock_repo(["Koramangala", "Indiranagar"])
        with pytest.raises(ValueError, match="Atlantis"):
            prefs.validate_against_repository(repo)

    def test_empty_repository_raises(self):
        prefs = _make_prefs(location="Bangalore")
        repo = _make_mock_repo([])
        with pytest.raises(ValueError):
            prefs.validate_against_repository(repo)
