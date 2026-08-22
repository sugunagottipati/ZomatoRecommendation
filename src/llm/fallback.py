"""
FallbackRanker — rule-based restaurant ranking used when the LLM is unavailable.

When the LLM provider fails (timeout, API error, parse failure), the
``RecommendationService`` falls back to this ranker.  It produces deterministic
results based on rating (descending) with a generic explanation for each entry.

The fallback result uses ``source="fallback"`` and ``summary=None`` so the UI
can display an appropriate notice to the user.
"""

from __future__ import annotations

import logging

from src.models.preferences import UserPreferences
from src.models.recommendation import Recommendation, RecommendationResponse
from src.models.restaurant import Restaurant

logger = logging.getLogger(__name__)


class FallbackRanker:
    """Rank filtered candidates by rating when the LLM is unavailable.

    Parameters
    ----------
    limit:
        Maximum number of recommendations to return.  Defaults to 5.
        The ``UserPreferences.limit`` value should be passed in at call time.
    """

    def rank(
        self,
        candidates: list[Restaurant],
        preferences: UserPreferences,
    ) -> RecommendationResponse:
        """Return a :class:`RecommendationResponse` ranked by rating DESC.

        Parameters
        ----------
        candidates:
            Pre-filtered restaurants (output of ``FilterService.filter()``).
        preferences:
            Validated user preferences; used to respect the ``limit`` field.

        Returns
        -------
        RecommendationResponse
            ``source="fallback"``, ``summary=None``, up to ``preferences.limit``
            recommendations with generic explanations.
        """
        limit = preferences.limit
        top = candidates[:limit]

        recommendations = [
            Recommendation(
                restaurant=restaurant,
                rank=rank,
                explanation=self._generic_explanation(restaurant),
            )
            for rank, restaurant in enumerate(top, start=1)
        ]

        logger.info(
            "FallbackRanker produced %d recommendations for location '%s'.",
            len(recommendations),
            preferences.location,
        )
        return RecommendationResponse(
            summary=None,
            recommendations=recommendations,
            source="fallback",
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _generic_explanation(restaurant: Restaurant) -> str:
        """Build a rule-based explanation from available restaurant fields."""
        parts: list[str] = []

        if restaurant.rating is not None:
            parts.append(f"Rated {restaurant.rating:.1f}/5")

        if restaurant.cuisines:
            cuisine_str = ", ".join(restaurant.cuisines[:2])
            parts.append(f"serves {cuisine_str}")

        if restaurant.cost_for_two is not None:
            parts.append(f"costs approximately ₹{restaurant.cost_for_two:.0f} for two")

        if parts:
            return ". ".join(parts) + "."
        return "Matches your search criteria."
