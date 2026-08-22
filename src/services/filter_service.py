"""
FilterService — multi-criteria restaurant filtering pipeline.

Pipeline order (per implementation plan §3.2):
    1. Filter by location (exact, case-insensitive via repository index)
    2. Filter by min_rating (if provided)
    3. Filter by budget tier
    4. Filter by cuisine (if provided, case-insensitive substring match)
    5. Sort by rating DESC (None ratings go last)
    6. Cap to max_candidates (default 20)

Raises ``NoMatchError`` when the pipeline yields zero candidates so the
caller can return a structured 404 rather than sending an empty prompt to
the LLM.
"""

from __future__ import annotations

import logging

from src.data.repository import RestaurantRepository
from src.exceptions import NoMatchError
from src.models.preferences import UserPreferences
from src.models.restaurant import Restaurant

logger = logging.getLogger(__name__)

_DEFAULT_MAX_CANDIDATES = 20


class FilterService:
    """Apply ``UserPreferences`` filters against the ``RestaurantRepository``.

    Parameters
    ----------
    repository:
        Initialised ``RestaurantRepository`` to query.
    max_candidates:
        Hard cap on the number of candidates returned.  Defaults to 20.
    """

    def __init__(
        self,
        repository: RestaurantRepository,
        max_candidates: int = _DEFAULT_MAX_CANDIDATES,
    ) -> None:
        self._repo = repository
        self._max_candidates = max_candidates

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def filter(self, preferences: UserPreferences) -> list[Restaurant]:
        """Run the full filter pipeline and return ranked candidates.

        Parameters
        ----------
        preferences:
            Validated ``UserPreferences`` from the request.

        Returns
        -------
        list[Restaurant]
            Filtered and sorted candidates, capped at ``max_candidates``.

        Raises
        ------
        NoMatchError
            If zero restaurants remain after applying all filters.
        """
        candidates = self._by_location(preferences.location)
        logger.debug(
            "After location filter ('%s'): %d candidates.",
            preferences.location,
            len(candidates),
        )

        if preferences.min_rating is not None:
            candidates = self._by_min_rating(candidates, preferences.min_rating)
            logger.debug(
                "After rating filter (≥%.1f): %d candidates.",
                preferences.min_rating,
                len(candidates),
            )

        candidates = self._by_budget(candidates, preferences.budget)
        logger.debug(
            "After budget filter ('%s'): %d candidates.",
            preferences.budget,
            len(candidates),
        )

        if preferences.cuisine is not None:
            candidates = self._by_cuisine(candidates, preferences.cuisine)
            logger.debug(
                "After cuisine filter ('%s'): %d candidates.",
                preferences.cuisine,
                len(candidates),
            )

        if not candidates:
            raise NoMatchError(
                f"No restaurants found in '{preferences.location}' matching your "
                f"preferences (budget={preferences.budget}"
                + (f", cuisine={preferences.cuisine}" if preferences.cuisine else "")
                + (f", min_rating={preferences.min_rating}" if preferences.min_rating else "")
                + "). Try relaxing some filters."
            )

        candidates = self._sort_by_rating(candidates)
        candidates = self._dedupe_by_identity(candidates)
        logger.debug("After deduplication: %d candidates.", len(candidates))
        candidates = candidates[: self._max_candidates]

        logger.info(
            "FilterService returning %d candidates for location='%s'.",
            len(candidates),
            preferences.location,
        )
        return candidates

    # ------------------------------------------------------------------
    # Filter steps
    # ------------------------------------------------------------------

    def _by_location(self, location: str) -> list[Restaurant]:
        """Fetch all restaurants for the given location from the index."""
        return self._repo.find_by_location(location)

    def _by_min_rating(
        self, candidates: list[Restaurant], min_rating: float
    ) -> list[Restaurant]:
        """Keep only restaurants with rating >= min_rating.

        Restaurants with no rating (``None``) are excluded when a minimum
        is specified, since we cannot confirm they meet the threshold.
        """
        return [
            r for r in candidates
            if r.rating is not None and r.rating >= min_rating
        ]

    def _by_budget(
        self, candidates: list[Restaurant], budget: str
    ) -> list[Restaurant]:
        """Keep only restaurants whose budget tier matches."""
        return [r for r in candidates if r.budget_tier == budget]

    def _by_cuisine(
        self, candidates: list[Restaurant], cuisine: str
    ) -> list[Restaurant]:
        """Fuzzy cuisine match: keep restaurants that contain the cuisine substring.

        Matching is case-insensitive and checks each cuisine tag in the list.
        E.g. searching for "Indian" matches "North Indian" and "South Indian".
        """
        needle = cuisine.lower()
        return [
            r for r in candidates
            if any(needle in tag.lower() for tag in r.cuisines)
        ]

    @staticmethod
    def _sort_by_rating(candidates: list[Restaurant]) -> list[Restaurant]:
        """Sort by rating descending; restaurants with no rating go last."""
        return sorted(
            candidates,
            key=lambda r: r.rating if r.rating is not None else -1.0,
            reverse=True,
        )

    @staticmethod
    def _dedupe_by_identity(candidates: list[Restaurant]) -> list[Restaurant]:
        """Remove display-duplicates while preserving first-seen order.

        Uses visible identity (name + location) rather than restaurant_id so
        duplicate source rows with different IDs cannot appear twice in output.
        """
        seen_keys: set[tuple[str, str]] = set()
        unique: list[Restaurant] = []
        for restaurant in candidates:
            key = (
                restaurant.name.strip().lower(),
                restaurant.location.strip().lower(),
            )
            if key in seen_keys:
                continue
            seen_keys.add(key)
            unique.append(restaurant)
        return unique
