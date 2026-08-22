"""
RecommendationService — orchestrates the full recommendation pipeline.

Pipeline
--------
1. ``FilterService.filter()``   — narrow the repository to matching candidates
2. ``PromptBuilder.build()``    — assemble LLM messages from candidates + prefs
3. ``LLMProvider.complete()``   — call the LLM
4. ``ResponseParser.parse()``   — validate and ground the LLM response
5. Enrich                       — merge full metadata (already in parser)
6. Fallback                     — if any step raises, use ``FallbackRanker``

The service is stateless between calls; all mutable state lives in the
injected collaborators.
"""

from __future__ import annotations

import logging

from src.exceptions import LLMError, NoMatchError, ResponseParseError
from src.llm.fallback import FallbackRanker
from src.llm.prompt_builder import PromptBuilder
from src.llm.provider import LLMProvider
from src.llm.response_parser import ResponseParser
from src.models.preferences import UserPreferences
from src.models.recommendation import RecommendationResponse
from src.services.filter_service import FilterService

logger = logging.getLogger(__name__)


class RecommendationService:
    """Orchestrate filtering, LLM ranking, and fallback logic.

    Parameters
    ----------
    filter_service:
        Configured ``FilterService`` with an attached repository.
    prompt_builder:
        ``PromptBuilder`` instance (controls candidate cap, prompt templates).
    llm_provider:
        Any :class:`~src.llm.provider.LLMProvider` implementation.
    fallback_ranker:
        ``FallbackRanker`` used when the LLM call or parse step fails.
    """

    def __init__(
        self,
        filter_service: FilterService,
        prompt_builder: PromptBuilder,
        llm_provider: LLMProvider,
        fallback_ranker: FallbackRanker,
    ) -> None:
        self._filter_service = filter_service
        self._prompt_builder = prompt_builder
        self._llm_provider = llm_provider
        self._fallback_ranker = fallback_ranker

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def recommend(self, preferences: UserPreferences) -> RecommendationResponse:
        """Run the full recommendation pipeline.

        Parameters
        ----------
        preferences:
            Validated ``UserPreferences`` from the request.

        Returns
        -------
        RecommendationResponse
            Ranked recommendations with explanations and optional summary.
            ``source`` is ``"llm"`` on success, ``"fallback"`` on LLM failure.

        Raises
        ------
        NoMatchError
            If zero restaurants match the user's filters (re-raised; the caller
            should surface this as a 404).
        """
        # Step 1 — Filter (raises NoMatchError if no candidates)
        candidates = self._filter_service.filter(preferences)
        logger.info(
            "Filtered %d candidates for location='%s', budget='%s'.",
            len(candidates),
            preferences.location,
            preferences.budget,
        )

        # Build candidate lookup for the parser's grounding check
        candidate_map = {r.restaurant_id: r for r in candidates}

        # Steps 2–5 — LLM path (with fallback)
        try:
            messages = self._prompt_builder.build(preferences, candidates)
            raw_response = self._llm_provider.complete(messages)
            parser = ResponseParser(candidate_map=candidate_map)
            response = parser.parse(raw_response)
            # Respect the user's requested limit
            trimmed = response.recommendations[: preferences.limit]
            return RecommendationResponse(
                summary=response.summary,
                recommendations=trimmed,
                source="llm",
            )
        except LLMError as exc:
            logger.warning(
                "LLM call failed (%s). Activating fallback ranker.", exc.message
            )
        except ResponseParseError as exc:
            logger.warning(
                "LLM response parse failed (%s). Activating fallback ranker.",
                exc.message,
            )
        except Exception as exc:  # noqa: BLE001 — broad catch, log and fall back
            logger.warning(
                "Unexpected error during LLM step (%r). Activating fallback ranker.",
                exc,
            )

        # Step 6 — Fallback
        return self._fallback_ranker.rank(candidates, preferences)
