"""
PromptBuilder — constructs the LLM prompt from filtered candidates and user preferences.

The prompt is structured in three sections:
    1. System message  — role + strict grounding constraint (no hallucination)
    2. User message    — preferences block + candidate JSON

LLM Output Contract (JSON the model must return):
    {
      "summary": "Brief overview of the recommendations",
      "recommendations": [
        {
          "restaurant_id": "<id from candidates>",
          "rank": 1,
          "explanation": "Why this restaurant fits the user"
        }
      ]
    }
"""

from __future__ import annotations

import json
import logging

from src.models.preferences import UserPreferences
from src.models.restaurant import Restaurant

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are an expert restaurant recommendation assistant.

Your job is to rank and explain a set of pre-filtered restaurant candidates \
based on the user's dining preferences.

STRICT RULES — you MUST follow these exactly:
1. Only recommend restaurants from the CANDIDATES LIST provided. \
   Do NOT invent, add, or reference any restaurant not in the list.
2. Return your response as a single, valid JSON object — no markdown, \
   no extra text, no code fences.
3. The JSON must match this exact schema:
   {{
     "summary": "<one or two sentences summarising the recommendations>",
     "recommendations": [
       {{
         "restaurant_id": "<id from the candidates list>",
         "rank": <integer starting at 1>,
         "explanation": "<why this restaurant fits the user's preferences>"
       }}
     ]
   }}
4. Include at most {{limit}} recommendations, ordered best-match first.
5. If no candidate is a good fit, still return the best available options \
   from the list — do not return an empty recommendations array.
"""

_USER_PROMPT_TEMPLATE = """\
## User Preferences
- Location: {location}
- Budget: {budget}
- Cuisine: {cuisine}
- Minimum rating: {min_rating}
- Additional preferences: {additional_preferences}

## Candidates List
{candidates_json}

Rank the best {limit} restaurants from the candidates list for this user.
"""


class PromptBuilder:
    """Build the system and user prompt messages for the LLM.

    Parameters
    ----------
    max_candidates:
        Maximum number of candidates to include in the prompt.  Extra
        candidates are silently dropped to stay within token budget.
    """

    def __init__(self, max_candidates: int = 20) -> None:
        self._max_candidates = max_candidates

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build(
        self,
        preferences: UserPreferences,
        candidates: list[Restaurant],
    ) -> list[dict[str, str]]:
        """Return a list of ``{"role": ..., "content": ...}`` message dicts.

        Parameters
        ----------
        preferences:
            Validated user preferences.
        candidates:
            Pre-filtered and sorted restaurant candidates from ``FilterService``.

        Returns
        -------
        list[dict[str, str]]
            ``[{"role": "system", "content": ...}, {"role": "user", "content": ...}]``
        """
        capped = candidates[: self._max_candidates]
        if len(capped) < len(candidates):
            logger.debug(
                "PromptBuilder: dropped %d excess candidates (max=%d).",
                len(candidates) - len(capped),
                self._max_candidates,
            )

        system_msg = _SYSTEM_PROMPT.format(limit=preferences.limit)
        user_msg = _USER_PROMPT_TEMPLATE.format(
            location=preferences.location,
            budget=preferences.budget,
            cuisine=preferences.cuisine or "Any",
            min_rating=preferences.min_rating if preferences.min_rating is not None else "None",
            additional_preferences=(
                ", ".join(preferences.additional_preferences)
                if preferences.additional_preferences
                else "None"
            ),
            candidates_json=self._format_candidates(capped),
            limit=preferences.limit,
        )

        return [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ]

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _format_candidates(candidates: list[Restaurant]) -> str:
        """Serialize candidates to a compact JSON array for the prompt."""
        records = [
            {
                "restaurant_id": r.restaurant_id,
                "name": r.name,
                "location": r.location,
                "cuisines": r.cuisines,
                "rating": r.rating,
                "cost_for_two": r.cost_for_two,
                "budget_tier": r.budget_tier,
                "votes": r.votes,
            }
            for r in candidates
        ]
        return json.dumps(records, ensure_ascii=False, indent=2)
