"""
UserPreferences — validated input schema for the restaurant recommendation pipeline.

This model is populated from the API request body (or UI form) and drives all
downstream filtering and prompt-building steps.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

if TYPE_CHECKING:
    from src.data.repository import RestaurantRepository

# ------------------------------------------------------------------
# Type alias (mirrors BudgetTier in restaurant.py)
# ------------------------------------------------------------------
BudgetTier = Literal["low", "medium", "high"]

_MAX_LIMIT = 20  # hard cap on returned recommendations


class UserPreferences(BaseModel):
    """Validated user preferences used to filter and rank restaurants.

    Attributes
    ----------
    location:
        City or locality to search within.  Must be a non-empty string.
        Service-level validation against the repository's known cities is
        performed via :meth:`validate_against_repository`.
    budget:
        Desired spend tier — one of ``"low"``, ``"medium"``, or ``"high"``.
    cuisine:
        Optional preferred cuisine type (e.g. ``"Italian"``).  If omitted,
        all cuisines are considered.
    min_rating:
        Optional minimum acceptable rating on a 0.0–5.0 scale.
    additional_preferences:
        Optional list of free-text tags (e.g. ``["family-friendly", "outdoor seating"]``).
    limit:
        Maximum number of recommendations to return (default 5, max 20).
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    location: str = Field(
        description="City or locality to search in.",
    )
    budget: BudgetTier = Field(
        description="Desired budget tier: 'low', 'medium', or 'high'.",
    )
    cuisine: str | None = Field(
        default=None,
        description="Preferred cuisine type.  None means no cuisine filter.",
    )
    min_rating: float | None = Field(
        default=None,
        ge=0.0,
        le=5.0,
        description="Minimum acceptable rating (0.0–5.0).  None means no rating filter.",
    )
    additional_preferences: list[str] = Field(
        default_factory=list,
        description="Free-text preference tags supplied by the user.",
    )
    limit: int = Field(
        default=5,
        ge=1,
        le=_MAX_LIMIT,
        description=f"Number of recommendations to return (1–{_MAX_LIMIT}).",
    )

    # ------------------------------------------------------------------
    # Field-level validators
    # ------------------------------------------------------------------

    @field_validator("location", mode="after")
    @classmethod
    def location_not_empty(cls, v: str) -> str:
        """Reject blank location strings (whitespace-only)."""
        if not v:
            raise ValueError("location must not be empty")
        return v

    @field_validator("cuisine", mode="after")
    @classmethod
    def cuisine_not_empty_string(cls, v: str | None) -> str | None:
        """Normalise cuisine: empty string → None; non-empty → title-cased."""
        if v is None:
            return None
        if not v:  # empty after strip
            return None
        return v.title()

    @field_validator("additional_preferences", mode="before")
    @classmethod
    def parse_additional_preferences(cls, v: object) -> list[str]:
        """Accept a list, a comma-separated string, or None."""
        if v is None:
            return []
        if isinstance(v, str):
            return [tag.strip() for tag in v.split(",") if tag.strip()]
        if isinstance(v, list):
            return [str(tag).strip() for tag in v if str(tag).strip()]
        return []

    @model_validator(mode="after")
    def normalise_fields(self) -> "UserPreferences":
        """Post-construction normalisation pass."""
        # Ensure location is title-cased for consistent downstream matching
        self.location = self.location.title()
        return self

    # ------------------------------------------------------------------
    # Repository-level location validation
    # ------------------------------------------------------------------

    def validate_against_repository(self, repository: "RestaurantRepository") -> None:
        """Raise ``ValueError`` if *location* is not found in the repository.

        This check is intentionally separated from Pydantic validation because
        the repository is a runtime dependency that is unavailable at schema
        definition time.  Call this method in the service layer after
        dependency injection.

        Parameters
        ----------
        repository:
            Initialised ``RestaurantRepository`` instance.

        Raises
        ------
        ValueError
            If the location is not present in any known city in the repository.
        """
        known = {city.lower() for city in repository.get_all_locations()}
        if self.location.lower() not in known:
            raise ValueError(
                f"Location '{self.location}' is not found in the dataset. "
                f"Use GET /api/v1/meta/locations for the list of supported cities."
            )
