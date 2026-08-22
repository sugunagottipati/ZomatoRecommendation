"""
Preprocessor — clean, normalize, and enrich raw Zomato data.

Responsibilities
----------------
1. Drop duplicate records (same name + location + city).
2. Handle null / missing values without crashing.
3. Parse and normalize rating, votes, cost, cuisines, location, city.
4. Derive budget tier from cost_for_two.
5. Generate a stable ``restaurant_id`` for each record.
6. Serialize/deserialize processed records to/from a local Parquet cache.

Budget Tier Thresholds (INR, cost for two)
------------------------------------------
    low    : cost_for_two ≤ 500
    medium : 501 ≤ cost_for_two ≤ 1500
    high   : cost_for_two > 1500

If cost_for_two is missing/unparseable the record is assigned 'medium' as
a neutral default so it remains discoverable.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Final

import pandas as pd

from src.models.restaurant import BudgetTier, Restaurant

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Budget tier boundaries (INR, cost for two people)
# ------------------------------------------------------------------
LOW_MAX: Final[float] = 500.0
MEDIUM_MAX: Final[float] = 1500.0

# Default cache filename inside the configured cache_dir
CACHE_FILENAME: Final[str] = "restaurants.parquet"


def _derive_budget_tier(cost: float | None) -> BudgetTier:
    """Map a numeric cost-for-two value to a budget tier label.

    Parameters
    ----------
    cost:
        Cost for two people in INR, or ``None`` if unknown.

    Returns
    -------
    BudgetTier
        'low', 'medium', or 'high'.
    """
    if cost is None:
        return "medium"  # neutral fallback for unknown cost
    if cost <= LOW_MAX:
        return "low"
    if cost <= MEDIUM_MAX:
        return "medium"
    return "high"


class Preprocessor:
    """Convert a raw Zomato DataFrame into a list of ``Restaurant`` objects.

    Parameters
    ----------
    cache_dir:
        Directory where the preprocessed pickle cache is stored.  Pass
        ``None`` to disable caching entirely (useful in tests).
    """

    def __init__(self, cache_dir: str | Path | None = "data/processed") -> None:
        self._cache_dir = Path(cache_dir) if cache_dir else None
        self._cache_path = (
            self._cache_dir / CACHE_FILENAME if self._cache_dir else None
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def preprocess(self, raw_df: pd.DataFrame) -> list[Restaurant]:
        """Transform raw DataFrame rows into validated ``Restaurant`` objects.

        Steps
        -----
        1. Drop rows where name, location, or city are entirely missing.
        2. De-duplicate on (name, location, city).
        3. Parse each row into a ``Restaurant`` via Pydantic validators.
        4. Log and skip any rows that fail validation.

        Parameters
        ----------
        raw_df:
            DataFrame returned by ``DatasetLoader.load()``.

        Returns
        -------
        list[Restaurant]
            Validated, de-duplicated restaurant records.
        """
        logger.info("Starting preprocessing of %d raw rows.", len(raw_df))

        df = raw_df.copy()

        # Step 1 — Normalise location & city strings before dedup
        df = self._normalise_location_columns(df)

        # Step 2 — Drop rows with no usable identity fields
        before = len(df)
        df = df.dropna(subset=["name"]).copy()
        df = df[df["name"].str.strip() != ""]
        logger.debug("Dropped %d rows with missing name.", before - len(df))

        # Step 3 — Fill missing location / city with empty string
        for col in ("location", "city", "address"):
            if col not in df.columns:
                df[col] = ""
            else:
                df[col] = df[col].fillna("").astype(str)

        # Step 4 — De-duplicate
        before = len(df)
        df = df.drop_duplicates(subset=["name", "location", "city"]).copy()
        logger.info("Removed %d duplicate records.", before - len(df))

        # Step 5 — Parse each row into a Restaurant
        restaurants: list[Restaurant] = []
        skipped = 0
        for _, row in df.iterrows():
            try:
                restaurant = self._row_to_restaurant(row)
                restaurants.append(restaurant)
            except Exception as exc:  # noqa: BLE001
                logger.debug("Skipping row due to validation error: %s — %s", row.get("name"), exc)
                skipped += 1

        logger.info(
            "Preprocessing complete: %d valid records, %d skipped.",
            len(restaurants),
            skipped,
        )
        return restaurants

    # ------------------------------------------------------------------
    # Cache helpers
    # ------------------------------------------------------------------

    def save_cache(self, restaurants: list[Restaurant]) -> None:
        """Persist preprocessed records to a local Parquet file.

        Parameters
        ----------
        restaurants:
            Preprocessed list to cache.
        """
        if self._cache_path is None:
            return
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        records = [r.model_dump() for r in restaurants]
        df = pd.DataFrame(records)
        df.to_parquet(self._cache_path, index=False)
        logger.info("Saved %d records to cache: %s", len(restaurants), self._cache_path)

    def load_cache(self) -> list[Restaurant] | None:
        """Return cached records if a valid Parquet cache file exists, else ``None``.

        Returns
        -------
        list[Restaurant] | None
        """
        if self._cache_path is None or not self._cache_path.exists():
            return None
        try:
            df = pd.read_parquet(self._cache_path)
            restaurants = [Restaurant(**row) for row in df.to_dict(orient="records")]
            logger.info(
                "Loaded %d records from cache: %s", len(restaurants), self._cache_path
            )
            return restaurants
        except Exception as exc:  # noqa: BLE001
            logger.warning("Cache read failed (%s); will re-preprocess.", exc)
            return None

    def clear_cache(self) -> None:
        """Delete the cache file if it exists."""
        if self._cache_path and self._cache_path.exists():
            self._cache_path.unlink()
            logger.info("Cache cleared: %s", self._cache_path)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _normalise_location_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Trim and title-case location and city columns in-place."""
        for col in ("location", "city"):
            if col in df.columns:
                df[col] = (
                    df[col]
                    .fillna("")
                    .astype(str)
                    .str.strip()
                    .str.title()
                )
        return df

    def _row_to_restaurant(self, row: pd.Series) -> Restaurant:  # type: ignore[type-arg]
        """Convert a single DataFrame row to a ``Restaurant`` instance.

        Pydantic validators on the model handle all type coercion and
        validation; this method only extracts the raw values.
        """
        name: str = str(row.get("name", "")).strip()
        location: str = str(row.get("location", "")).strip()
        city: str = str(row.get("city", "")).strip()

        restaurant_id = Restaurant.make_id(name, location, city)

        # cost_for_two is parsed by the Pydantic validator on the model
        raw_cost = row.get("cost_raw") or row.get("cost_for_two")

        # Derive budget tier from the raw cost value
        # We parse cost similarly to the validator to get the float here
        cost_float = self._parse_cost_float(raw_cost)
        budget_tier = _derive_budget_tier(cost_float)

        return Restaurant(
            restaurant_id=restaurant_id,
            name=name,
            location=location,
            city=city,
            address=str(row.get("address", "") or "").strip(),
            cuisines=row.get("cuisines"),  # Pydantic validator parses this
            cost_for_two=raw_cost,          # Pydantic validator parses this
            budget_tier=budget_tier,
            rating=row.get("rate"),         # Pydantic validator parses this
            votes=row.get("votes"),         # Pydantic validator parses this
        )

    @staticmethod
    def _parse_cost_float(v: object) -> float | None:
        """Parse a raw cost value to float (mirrors Restaurant.parse_cost logic)."""
        if v is None or (isinstance(v, float) and v != v):
            return None
        raw = str(v).strip().replace("₹", "").replace(",", "").replace(" ", "")
        try:
            parsed = float(raw)
            return parsed if parsed >= 0 else None
        except ValueError:
            return None
