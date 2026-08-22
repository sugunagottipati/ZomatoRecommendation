"""
ResponseParser — parse and validate the LLM JSON response into domain objects.

The LLM is instructed to return this contract:
    {
      "summary": "<str>",
      "recommendations": [
        {
          "restaurant_id": "<id from candidates>",
          "rank": <int>,
          "explanation": "<str>"
        },
        ...
      ]
    }

Validation steps
----------------
1. Parse raw text as JSON.
2. Verify top-level keys ``recommendations`` exist.
3. For each recommendation entry: verify ``restaurant_id``, ``rank``, ``explanation``.
4. **Grounding check**: reject any ``restaurant_id`` not present in the candidate set
   — this prevents hallucinated restaurants from reaching the user.
5. Enrich each recommendation with the full ``Restaurant`` metadata from the
   candidate map.
6. Sort by ``rank`` and return as ``RecommendationResponse``.

On any structural failure, raises :class:`~src.exceptions.ResponseParseError` so
the caller can activate the fallback ranker.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from src.exceptions import ResponseParseError
from src.models.recommendation import Recommendation, RecommendationResponse
from src.models.restaurant import Restaurant

logger = logging.getLogger(__name__)


class ResponseParser:
    """Parse the raw LLM text response into a :class:`RecommendationResponse`.

    Parameters
    ----------
    candidate_map:
        ``{restaurant_id: Restaurant}`` lookup built from the candidates list.
        Only IDs present in this map are accepted; others are rejected as
        hallucinations.
    """

    def __init__(self, candidate_map: dict[str, Restaurant]) -> None:
        self._candidate_map = candidate_map

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def parse(self, raw_response: str) -> RecommendationResponse:
        """Parse *raw_response* and return a validated :class:`RecommendationResponse`.

        Parameters
        ----------
        raw_response:
            Raw text from the LLM (should be a JSON string).

        Returns
        -------
        RecommendationResponse
            Enriched response with full restaurant metadata.

        Raises
        ------
        ResponseParseError
            If the JSON is malformed, required keys are missing, or any
            ``restaurant_id`` is not in the candidate set (hallucination guard).
        """
        data = self._parse_json(raw_response)
        summary = self._extract_summary(data)
        raw_recs = self._extract_recommendations_list(data, raw_response)
        recommendations = self._build_recommendations(raw_recs, raw_response)

        logger.debug(
            "ResponseParser: parsed %d recommendations, summary=%s.",
            len(recommendations),
            bool(summary),
        )
        return RecommendationResponse(
            summary=summary,
            recommendations=recommendations,
            source="llm",
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _parse_json(self, raw: str) -> dict[str, Any]:
        """Attempt to parse *raw* as JSON, stripping markdown fences if present."""
        text = raw.strip()
        # Strip optional markdown code fences that some models add
        if text.startswith("```"):
            lines = text.splitlines()
            # Drop first line (```json or ```) and last line (```)
            text = "\n".join(lines[1:-1]) if len(lines) > 2 else text
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ResponseParseError(
                f"LLM response is not valid JSON: {exc}",
                raw_response=raw,
            ) from exc
        if not isinstance(parsed, dict):
            raise ResponseParseError(
                "LLM response JSON is not an object.",
                raw_response=raw,
            )
        return parsed  # type: ignore[return-value]

    @staticmethod
    def _extract_summary(data: dict[str, Any]) -> str | None:
        summary = data.get("summary")
        if summary and isinstance(summary, str):
            return summary.strip() or None
        return None

    @staticmethod
    def _extract_recommendations_list(
        data: dict[str, Any], raw: str
    ) -> list[dict[str, Any]]:
        recs = data.get("recommendations")
        if not isinstance(recs, list):
            raise ResponseParseError(
                "LLM response missing 'recommendations' list.",
                raw_response=raw,
            )
        return recs  # type: ignore[return-value]

    def _build_recommendations(
        self,
        raw_recs: list[dict[str, Any]],
        raw: str,
    ) -> list[Recommendation]:
        """Validate each entry, apply grounding check, and enrich with metadata."""
        seen_ids: set[str] = set()
        recommendations: list[Recommendation] = []

        for idx, item in enumerate(raw_recs):
            if not isinstance(item, dict):
                logger.warning("Skipping non-dict recommendation entry at index %d.", idx)
                continue

            restaurant_id = item.get("restaurant_id")
            rank = item.get("rank")
            explanation = item.get("explanation", "")

            # --- Field presence checks ---
            if not restaurant_id or not isinstance(restaurant_id, str):
                logger.warning(
                    "Skipping recommendation at index %d: missing/invalid restaurant_id.",
                    idx,
                )
                continue
            if not isinstance(rank, int) or rank < 1:
                logger.warning(
                    "Recommendation '%s' has invalid rank %r; using positional rank.",
                    restaurant_id,
                    rank,
                )
                rank = len(recommendations) + 1

            # --- Grounding check ---
            if restaurant_id not in self._candidate_map:
                logger.warning(
                    "Hallucination guard: restaurant_id '%s' not in candidate list. "
                    "Dropping this recommendation.",
                    restaurant_id,
                )
                continue

            # --- Deduplication ---
            if restaurant_id in seen_ids:
                logger.warning(
                    "Duplicate restaurant_id '%s' in LLM response. Dropping.",
                    restaurant_id,
                )
                continue
            seen_ids.add(restaurant_id)

            restaurant = self._candidate_map[restaurant_id]
            recommendations.append(
                Recommendation(
                    restaurant=restaurant,
                    rank=rank,
                    explanation=explanation if isinstance(explanation, str) else "",
                )
            )

        if not recommendations:
            raise ResponseParseError(
                "No valid recommendations survived grounding/validation checks.",
                raw_response=raw,
            )

        # Sort by rank so the caller gets a clean ordered list
        recommendations.sort(key=lambda r: r.rank)
        return recommendations
