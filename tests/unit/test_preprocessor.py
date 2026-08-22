"""
Unit tests for ``src/data/preprocessor.py``.

Tests cover:
- Budget tier derivation
- Null / missing value handling (name, rating, cost, votes, cuisines)
- Duplicate deduplication
- Location and city normalization (trim, title-case)
- Cache round-trip (save → load)
- Malformed cost strings
- Edge-case rating strings ('NEW', '-', '/5')
"""

from __future__ import annotations

import pandas as pd
import pytest

from src.data.preprocessor import (
    LOW_MAX,
    MEDIUM_MAX,
    Preprocessor,
    _derive_budget_tier,
)
from src.models.restaurant import Restaurant


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_raw_row(**overrides) -> dict:
    """Return a minimal valid raw row dict with optional field overrides."""
    base = {
        "name": "Test Restaurant",
        "location": "Koramangala",
        "city": "Bangalore",
        "rate": "4.1/5",
        "votes": 100,
        "cuisines": "North Indian, Chinese",
        "cost_raw": "800",
        "address": "123 Main St",
    }
    base.update(overrides)
    return base


def _make_df(*rows: dict) -> pd.DataFrame:
    """Build a DataFrame from one or more row dicts."""
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# _derive_budget_tier
# ---------------------------------------------------------------------------

class TestDeriveBudgetTier:
    def test_low_boundary_exact(self):
        assert _derive_budget_tier(LOW_MAX) == "low"

    def test_low_below_boundary(self):
        assert _derive_budget_tier(0) == "low"
        assert _derive_budget_tier(499) == "low"

    def test_medium_above_low(self):
        assert _derive_budget_tier(501) == "medium"

    def test_medium_boundary_exact(self):
        assert _derive_budget_tier(MEDIUM_MAX) == "medium"

    def test_high_above_medium(self):
        assert _derive_budget_tier(1501) == "high"
        assert _derive_budget_tier(5000) == "high"

    def test_none_returns_medium(self):
        """Missing cost → neutral 'medium' tier."""
        assert _derive_budget_tier(None) == "medium"


# ---------------------------------------------------------------------------
# Preprocessor.preprocess — valid inputs
# ---------------------------------------------------------------------------

class TestPreprocessorValidInputs:
    def setup_method(self):
        self.preprocessor = Preprocessor(cache_dir=None)

    def test_single_valid_row_returns_one_restaurant(self):
        df = _make_df(_make_raw_row())
        result = self.preprocessor.preprocess(df)
        assert len(result) == 1
        r = result[0]
        assert r.name == "Test Restaurant"
        assert r.location == "Koramangala"
        assert r.city == "Bangalore"

    def test_rating_parsed_correctly(self):
        df = _make_df(_make_raw_row(rate="4.1/5"))
        result = self.preprocessor.preprocess(df)
        assert result[0].rating == pytest.approx(4.1)

    def test_cost_parsed_and_budget_tier_set(self):
        df = _make_df(_make_raw_row(cost_raw="800"))
        result = self.preprocessor.preprocess(df)
        assert result[0].cost_for_two == pytest.approx(800.0)
        assert result[0].budget_tier == "medium"

    def test_low_budget_tier(self):
        df = _make_df(_make_raw_row(cost_raw="300"))
        result = self.preprocessor.preprocess(df)
        assert result[0].budget_tier == "low"

    def test_high_budget_tier(self):
        df = _make_df(_make_raw_row(cost_raw="2000"))
        result = self.preprocessor.preprocess(df)
        assert result[0].budget_tier == "high"

    def test_cuisines_parsed_to_list(self):
        df = _make_df(_make_raw_row(cuisines="North Indian, Chinese"))
        result = self.preprocessor.preprocess(df)
        assert result[0].cuisines == ["North Indian", "Chinese"]

    def test_votes_parsed(self):
        df = _make_df(_make_raw_row(votes=250))
        result = self.preprocessor.preprocess(df)
        assert result[0].votes == 250

    def test_restaurant_id_stable(self):
        """Same name+location+city always produces the same ID."""
        df = _make_df(_make_raw_row())
        r1 = self.preprocessor.preprocess(df)[0]
        r2 = self.preprocessor.preprocess(df)[0]
        assert r1.restaurant_id == r2.restaurant_id

    def test_multiple_rows(self):
        df = _make_df(
            _make_raw_row(name="A"),
            _make_raw_row(name="B"),
            _make_raw_row(name="C"),
        )
        result = self.preprocessor.preprocess(df)
        assert len(result) == 3


# ---------------------------------------------------------------------------
# Preprocessor.preprocess — null / missing value handling
# ---------------------------------------------------------------------------

class TestPreprocessorNullHandling:
    def setup_method(self):
        self.preprocessor = Preprocessor(cache_dir=None)

    def test_null_rating_does_not_crash(self):
        df = _make_df(_make_raw_row(rate=None))
        result = self.preprocessor.preprocess(df)
        assert len(result) == 1
        assert result[0].rating is None

    def test_new_rating_string_returns_none(self):
        df = _make_df(_make_raw_row(rate="NEW"))
        result = self.preprocessor.preprocess(df)
        assert result[0].rating is None

    def test_dash_rating_string_returns_none(self):
        df = _make_df(_make_raw_row(rate="-"))
        result = self.preprocessor.preprocess(df)
        assert result[0].rating is None

    def test_null_cost_assigns_medium_tier(self):
        df = _make_df(_make_raw_row(cost_raw=None))
        result = self.preprocessor.preprocess(df)
        assert result[0].budget_tier == "medium"
        assert result[0].cost_for_two is None

    def test_malformed_cost_string_returns_none(self):
        df = _make_df(_make_raw_row(cost_raw="N/A"))
        result = self.preprocessor.preprocess(df)
        assert result[0].cost_for_two is None

    def test_cost_with_currency_symbol(self):
        df = _make_df(_make_raw_row(cost_raw="₹1,200"))
        result = self.preprocessor.preprocess(df)
        assert result[0].cost_for_two == pytest.approx(1200.0)
        assert result[0].budget_tier == "medium"

    def test_null_votes_defaults_to_zero(self):
        df = _make_df(_make_raw_row(votes=None))
        result = self.preprocessor.preprocess(df)
        assert result[0].votes == 0

    def test_null_cuisines_returns_empty_list(self):
        df = _make_df(_make_raw_row(cuisines=None))
        result = self.preprocessor.preprocess(df)
        assert result[0].cuisines == []

    def test_row_with_missing_name_is_dropped(self):
        df = _make_df(
            _make_raw_row(name=None),
            _make_raw_row(name="Valid Restaurant"),
        )
        result = self.preprocessor.preprocess(df)
        assert len(result) == 1
        assert result[0].name == "Valid Restaurant"

    def test_row_with_empty_name_is_dropped(self):
        df = _make_df(_make_raw_row(name="   "))
        result = self.preprocessor.preprocess(df)
        assert len(result) == 0


# ---------------------------------------------------------------------------
# Preprocessor — normalization
# ---------------------------------------------------------------------------

class TestPreprocessorNormalization:
    def setup_method(self):
        self.preprocessor = Preprocessor(cache_dir=None)

    def test_city_is_title_cased(self):
        df = _make_df(_make_raw_row(city="bangalore"))
        result = self.preprocessor.preprocess(df)
        assert result[0].city == "Bangalore"

    def test_location_is_title_cased(self):
        df = _make_df(_make_raw_row(location="  koramangala  "))
        result = self.preprocessor.preprocess(df)
        assert result[0].location == "Koramangala"

    def test_cuisine_is_title_cased(self):
        df = _make_df(_make_raw_row(cuisines="north indian, CHINESE"))
        result = self.preprocessor.preprocess(df)
        assert "North Indian" in result[0].cuisines
        assert "Chinese" in result[0].cuisines


# ---------------------------------------------------------------------------
# Preprocessor — deduplication
# ---------------------------------------------------------------------------

class TestPreprocessorDeduplication:
    def setup_method(self):
        self.preprocessor = Preprocessor(cache_dir=None)

    def test_exact_duplicates_removed(self):
        row = _make_raw_row()
        df = _make_df(row, row)  # identical rows
        result = self.preprocessor.preprocess(df)
        assert len(result) == 1

    def test_different_names_not_deduplicated(self):
        df = _make_df(
            _make_raw_row(name="Alpha"),
            _make_raw_row(name="Beta"),
        )
        result = self.preprocessor.preprocess(df)
        assert len(result) == 2

    def test_same_name_different_location_not_deduplicated(self):
        df = _make_df(
            _make_raw_row(name="Cafe X", location="Indiranagar"),
            _make_raw_row(name="Cafe X", location="Koramangala"),
        )
        result = self.preprocessor.preprocess(df)
        assert len(result) == 2


# ---------------------------------------------------------------------------
# Preprocessor — cache round-trip
# ---------------------------------------------------------------------------

class TestPreprocessorCache:
    def test_save_and_load_cache(self, tmp_path):
        preprocessor = Preprocessor(cache_dir=tmp_path)
        df = _make_df(_make_raw_row(name="Cache Test"))
        restaurants = preprocessor.preprocess(df)

        preprocessor.save_cache(restaurants)
        loaded = preprocessor.load_cache()

        assert loaded is not None
        assert len(loaded) == 1
        assert loaded[0].name == "Cache Test"

    def test_load_cache_returns_none_when_missing(self, tmp_path):
        preprocessor = Preprocessor(cache_dir=tmp_path)
        assert preprocessor.load_cache() is None

    def test_clear_cache_removes_file(self, tmp_path):
        preprocessor = Preprocessor(cache_dir=tmp_path)
        df = _make_df(_make_raw_row())
        restaurants = preprocessor.preprocess(df)
        preprocessor.save_cache(restaurants)
        preprocessor.clear_cache()
        assert preprocessor.load_cache() is None

    def test_corrupt_cache_returns_none(self, tmp_path):
        preprocessor = Preprocessor(cache_dir=tmp_path)
        # Write invalid Parquet data
        (tmp_path / "restaurants.parquet").write_bytes(b"not-a-parquet-file")
        assert preprocessor.load_cache() is None

    def test_cache_disabled_when_none(self):
        preprocessor = Preprocessor(cache_dir=None)
        df = _make_df(_make_raw_row())
        restaurants = preprocessor.preprocess(df)
        # Should not raise, just no-op
        preprocessor.save_cache(restaurants)
        assert preprocessor.load_cache() is None
