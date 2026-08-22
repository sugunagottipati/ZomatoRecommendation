"""
RestaurantRepository — in-memory store with O(1) indexed lookups.

The repository is built once at startup (from the preprocessed list) and
shared across all request handlers via FastAPI dependency injection.

Indexes
-------
* ``_by_location``  : city → List[Restaurant]
* ``_by_cuisine``   : cuisine_lower → List[Restaurant]

Both indexes are case-insensitive.  Lookup keys are lowercased before
storage and before querying.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Iterator

from src.models.restaurant import BudgetTier, Restaurant

logger = logging.getLogger(__name__)


class RestaurantRepository:
    """Thread-safe, read-only in-memory restaurant store.

    Parameters
    ----------
    restaurants:
        Pre-validated list of ``Restaurant`` objects (output of
        ``Preprocessor.preprocess()``).
    """

    def __init__(self, restaurants: list[Restaurant]) -> None:
        self._restaurants: list[Restaurant] = restaurants
        self._by_id: dict[str, Restaurant] = {}
        self._by_location: dict[str, list[Restaurant]] = defaultdict(list)
        self._by_cuisine: dict[str, list[Restaurant]] = defaultdict(list)

        self._build_indexes()

    # ------------------------------------------------------------------
    # Index construction
    # ------------------------------------------------------------------

    def _build_indexes(self) -> None:
        """Populate all lookup indexes from the restaurant list."""
        logger.info("Building repository indexes for %d records…", len(self._restaurants))

        for restaurant in self._restaurants:
            # ID index
            self._by_id[restaurant.restaurant_id] = restaurant

            # Location index: keyed by lowercase location (neighbourhood/area)
            location_key = restaurant.location.lower().strip()
            if location_key:
                self._by_location[location_key].append(restaurant)

            # Cuisine index: one entry per cuisine tag
            for cuisine in restaurant.cuisines:
                cuisine_key = cuisine.lower().strip()
                if cuisine_key:
                    self._by_cuisine[cuisine_key].append(restaurant)

        logger.info(
            "Indexes built — %d unique locations, %d unique cuisines.",
            len(self._by_location),
            len(self._by_cuisine),
        )

    # ------------------------------------------------------------------
    # Query API
    # ------------------------------------------------------------------

    def count(self) -> int:
        """Return the total number of restaurants in the repository."""
        return len(self._restaurants)

    def get_by_id(self, restaurant_id: str) -> Restaurant | None:
        """Return a restaurant by its stable ID, or ``None`` if not found."""
        return self._by_id.get(restaurant_id)

    def find_by_location(self, location: str) -> list[Restaurant]:
        """Return all restaurants in the given location/neighbourhood (case-insensitive).

        Parameters
        ----------
        location:
            Location/area name to look up (e.g. ``"Koramangala"``).  This
            corresponds to the ``Restaurant.location`` field, not the city.

        Returns
        -------
        list[Restaurant]
            All restaurants in that area, or an empty list if none found.
        """
        return list(self._by_location.get(location.lower().strip(), []))

    def find_by_cuisine(self, cuisine: str) -> list[Restaurant]:
        """Return all restaurants serving the given cuisine (case-insensitive).

        This is an exact match against the normalised cuisine tags.
        For fuzzy matching, use ``FilterService`` instead.
        """
        return list(self._by_cuisine.get(cuisine.lower().strip(), []))

    def get_all_locations(self) -> list[str]:
        """Return a sorted list of known location/area names (original title-case).

        These are neighbourhood-level names (``Restaurant.location`` field), not
        city names.  De-duplicated and sorted alphabetically.
        """
        seen: dict[str, str] = {}  # lower → original-case
        for restaurant in self._restaurants:
            key = restaurant.location.lower().strip()
            if key and key not in seen:
                seen[key] = restaurant.location
        return sorted(seen.values())

    def get_all_cuisines(self) -> list[str]:
        """Return a sorted list of distinct cuisine names (original title-case).

        Derived from the ``cuisines`` field across all restaurants.
        """
        seen: dict[str, str] = {}  # lower → original-case
        for restaurant in self._restaurants:
            for cuisine in restaurant.cuisines:
                key = cuisine.lower().strip()
                if key and key not in seen:
                    seen[key] = cuisine
        return sorted(seen.values())

    def __iter__(self) -> Iterator[Restaurant]:
        """Iterate over all restaurants in insertion order."""
        return iter(self._restaurants)

    def __len__(self) -> int:
        return self.count()

    def __repr__(self) -> str:
        return (
            f"RestaurantRepository("
            f"records={self.count()}, "
            f"locations={len(self._by_location)}, "
            f"cuisines={len(self._by_cuisine)})"
        )
