"""
Application-level exceptions shared across services.
"""

from __future__ import annotations


class NoMatchError(Exception):
    """Raised when the filter pipeline yields zero restaurant candidates.

    Attributes
    ----------
    location:
        The location the user searched in.
    message:
        Human-readable description surfaced to the API / UI error response.
    """

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class LLMError(Exception):
    """Raised when the LLM provider encounters a non-recoverable error.

    Attributes
    ----------
    message:
        Human-readable description of the failure (timeout, API error, etc.).
    """

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class ResponseParseError(Exception):
    """Raised when the LLM response cannot be parsed into the expected schema.

    Attributes
    ----------
    message:
        Human-readable description of what was malformed.
    raw_response:
        The raw LLM text that triggered the parse failure.
    """

    def __init__(self, message: str, raw_response: str = "") -> None:
        super().__init__(message)
        self.message = message
        self.raw_response = raw_response
