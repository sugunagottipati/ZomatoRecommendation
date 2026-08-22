"""
MetadataService — read-only queries against the restaurant repository for
metadata endpoints (/meta/locations and /meta/cuisines).
"""

from __future__ import annotations

from src.data.repository import RestaurantRepository


class MetadataService:
    """Provides sorted lists of known locations and cuisines.

    Parameters
    ----------
    repository:
        Initialised ``RestaurantRepository``.
    """

    def __init__(self, repository: RestaurantRepository) -> None:
        self._repo = repository

    def get_locations(self) -> list[str]:
        """Return a sorted list of unique location/area names."""
        return self._repo.get_all_locations()

    def get_cities(self) -> list[str]:
        """Return city selector values derived from the location field.

        Product/UI labels may call this a "cities" list, but the returned values
        intentionally come from ``Restaurant.location`` (localities/areas), not
        ``Restaurant.city``.
        """
        return self.get_locations()

    def get_cuisines(self) -> list[str]:
        """Return a sorted list of unique cuisine names."""
        return self._repo.get_all_cuisines()

    def record_count(self) -> int:
        """Return the total number of restaurants in the repository."""
        return self._repo.count()
