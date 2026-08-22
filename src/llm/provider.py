"""
LLMProvider — protocol and concrete implementations for LLM backends.

Implementations
---------------
* ``GroqProvider``   — Groq cloud API (OpenAI-compatible SDK)
* ``OllamaProvider`` — Local Ollama server (OpenAI-compatible REST)
* ``MockLLMProvider``— Deterministic test double; never makes network calls

Usage
-----
Use :func:`build_provider` to obtain the correct implementation from Settings,
or instantiate directly for testing.
"""

from __future__ import annotations

import json
import logging
import textwrap
from typing import Protocol, runtime_checkable

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class LLMProvider(Protocol):
    """Interface every LLM backend must satisfy.

    A provider receives a list of chat messages and returns the LLM's text
    response.  Implementations are responsible for their own retry/timeout
    logic.
    """

    def complete(self, messages: list[dict[str, str]]) -> str:
        """Send *messages* to the LLM and return the raw response text.

        Parameters
        ----------
        messages:
            Sequence of ``{"role": ..., "content": ...}`` dicts.

        Returns
        -------
        str
            Raw LLM response text (should be valid JSON per prompt contract).

        Raises
        ------
        LLMError
            On any provider-level failure (network error, timeout, API error).
        """
        ...


# ---------------------------------------------------------------------------
# Groq Provider (OpenAI-compatible)
# ---------------------------------------------------------------------------


class GroqProvider:
    """LLM provider backed by the Groq cloud API.

    Parameters
    ----------
    api_key:
        Groq API key.
    model:
        Model name (e.g. ``"llama-3.3-70b-versatile"``).
    timeout:
        Request timeout in seconds.
    """

    def __init__(self, api_key: str, model: str, timeout: float = 30.0) -> None:
        try:
            from groq import Groq  # type: ignore[import-untyped]
        except ImportError as exc:  # pragma: no cover
            raise ImportError(
                "groq package is required for GroqProvider. "
                "Install it with: pip install groq"
            ) from exc

        self._client = Groq(api_key=api_key, timeout=timeout)
        self._model = model

    def complete(self, messages: list[dict[str, str]]) -> str:
        from groq import APIError, APITimeoutError  # type: ignore[import-untyped]

        from src.exceptions import LLMError

        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=messages,  # type: ignore[arg-type]
                response_format={"type": "json_object"},
                temperature=0.2,
            )
            content = response.choices[0].message.content or ""
            logger.debug("GroqProvider raw response (%d chars).", len(content))
            return content
        except APITimeoutError as exc:
            raise LLMError(f"Groq request timed out: {exc}") from exc
        except APIError as exc:
            raise LLMError(f"Groq API error: {exc}") from exc


# ---------------------------------------------------------------------------
# Ollama Provider (OpenAI-compatible local server)
# ---------------------------------------------------------------------------


class OllamaProvider:
    """LLM provider backed by a local Ollama server.

    Parameters
    ----------
    base_url:
        Ollama server base URL (e.g. ``"http://localhost:11434"``).
    model:
        Model name (e.g. ``"llama3.2"``).
    timeout:
        Request timeout in seconds.
    """

    def __init__(self, base_url: str, model: str, timeout: float = 30.0) -> None:
        try:
            from openai import OpenAI  # type: ignore[import-untyped]
        except ImportError as exc:  # pragma: no cover
            raise ImportError(
                "openai package is required for OllamaProvider. "
                "Install it with: pip install openai"
            ) from exc

        self._client = OpenAI(
            api_key="ollama",  # Ollama ignores the key but SDK requires it
            base_url=f"{base_url.rstrip('/')}/v1",
            timeout=timeout,
        )
        self._model = model

    def complete(self, messages: list[dict[str, str]]) -> str:
        from openai import APIError, APITimeoutError  # type: ignore[import-untyped]

        from src.exceptions import LLMError

        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=messages,  # type: ignore[arg-type]
                response_format={"type": "json_object"},
                temperature=0.2,
            )
            content = response.choices[0].message.content or ""
            logger.debug("OllamaProvider raw response (%d chars).", len(content))
            return content
        except APITimeoutError as exc:
            raise LLMError(f"Ollama request timed out: {exc}") from exc
        except APIError as exc:
            raise LLMError(f"Ollama API error: {exc}") from exc


# ---------------------------------------------------------------------------
# Mock Provider (deterministic test double)
# ---------------------------------------------------------------------------


class MockLLMProvider:
    """Deterministic LLM provider for unit and integration tests.

    Generates a valid JSON response using the ``restaurant_id`` values
    embedded in the user message so no network calls are made.

    Parameters
    ----------
    summary:
        Optional fixed summary text to embed in responses.
    fail_with:
        If provided, :meth:`complete` will raise :class:`~src.exceptions.LLMError`
        with this message — used to test fallback behaviour.
    """

    def __init__(
        self,
        summary: str = "Here are the best matches for your preferences.",
        fail_with: str | None = None,
    ) -> None:
        self._summary = summary
        self._fail_with = fail_with

    def complete(self, messages: list[dict[str, str]]) -> str:
        from src.exceptions import LLMError

        if self._fail_with is not None:
            raise LLMError(self._fail_with)

        # Extract restaurant_ids from the candidates JSON in the user message.
        restaurant_ids = self._extract_ids(messages)

        recommendations = [
            {
                "restaurant_id": rid,
                "rank": rank,
                "explanation": f"Mock explanation for rank {rank} restaurant.",
            }
            for rank, rid in enumerate(restaurant_ids, start=1)
        ]

        return json.dumps(
            {
                "summary": self._summary,
                "recommendations": recommendations,
            }
        )

    @staticmethod
    def _extract_ids(messages: list[dict[str, str]]) -> list[str]:
        """Parse restaurant_id values from the candidates JSON in messages."""
        for msg in messages:
            if msg.get("role") == "user":
                content = msg["content"]
                try:
                    # Find the JSON array embedded in the user message
                    start = content.index("[")
                    end = content.rindex("]") + 1
                    candidates = json.loads(content[start:end])
                    return [c["restaurant_id"] for c in candidates[:5]]
                except (ValueError, KeyError, json.JSONDecodeError):
                    pass
        return []


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def build_provider(settings: object) -> LLMProvider:
    """Construct the appropriate :class:`LLMProvider` from application settings.

    Parameters
    ----------
    settings:
        A ``Settings`` instance (from ``src.config``).

    Returns
    -------
    LLMProvider
        Configured provider ready for use.

    Raises
    ------
    ValueError
        For unknown ``llm_provider`` values.
    """
    provider_name: str = getattr(settings, "llm_provider", "mock")
    model: str = getattr(settings, "llm_model", "")
    timeout: float = getattr(settings, "llm_timeout_seconds", 30.0)

    if provider_name == "groq":
        api_key: str = getattr(settings, "groq_api_key", "")
        if not api_key:
            raise ValueError(
                "groq_api_key must be set in the environment when llm_provider=groq"
            )
        logger.info("Using GroqProvider with model '%s'.", model)
        return GroqProvider(api_key=api_key, model=model, timeout=timeout)

    if provider_name == "ollama":
        base_url: str = getattr(settings, "ollama_base_url", "http://localhost:11434")
        logger.info("Using OllamaProvider at '%s' with model '%s'.", base_url, model)
        return OllamaProvider(base_url=base_url, model=model, timeout=timeout)

    if provider_name == "mock":
        logger.info("Using MockLLMProvider (no real LLM calls).")
        return MockLLMProvider()

    raise ValueError(
        f"Unknown llm_provider '{provider_name}'. "
        "Valid choices: 'groq', 'ollama', 'mock'."
    )
