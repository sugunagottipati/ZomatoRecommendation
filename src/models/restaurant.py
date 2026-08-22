"""
Domain model for a single restaurant record.

This model is populated by the ``Preprocessor`` and stored in the
``RestaurantRepository``.  All fields are optional-tolerant so that records
with missing source data survive ingestion with sensible defaults rather than
being silently dropped.
"""

from __future__ import annotations

import hashlib
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# Budget tier derived from the cost-for-two field:
#   low    ≤ ₹500
#   medium ₹501 – ₹1500
#   high   > ₹1500
BudgetTier = Literal["low", "medium", "high"]


class Restaurant(BaseModel):
    """Immutable snapshot of a single restaurant entry from the Zomato dataset.

    Fields mirror the raw dataset columns after preprocessing.  ``restaurant_id``
    is a stable hash derived from name + location so it survives cache
    round-trips without requiring an auto-increment column.
    """

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------
    restaurant_id: str = Field(
        description="Stable, content-addressable identifier (SHA-1 of name+location).",
    )
    name: str = Field(description="Restaurant display name.")

    # ------------------------------------------------------------------
    # Location
    # ------------------------------------------------------------------
    location: str = Field(description="Locality / neighbourhood within the city.")
    city: str = Field(description="City name, title-cased and trimmed.")
    address: str = Field(default="", description="Full street address when available.")

    # ------------------------------------------------------------------
    # Cuisine & Cost
    # ------------------------------------------------------------------
    cuisines: list[str] = Field(
        default_factory=list,
        description="List of cuisine types offered (normalised to title-case).",
    )
    cost_for_two: float | None = Field(
        default=None,
        ge=0,
        description="Average cost for two people in INR.",
    )
    budget_tier: BudgetTier = Field(
        description="Derived budget category based on cost_for_two.",
    )

    # ------------------------------------------------------------------
    # Quality Signals
    # ------------------------------------------------------------------
    rating: float | None = Field(
        default=None,
        ge=0.0,
        le=5.0,
        description="Aggregate rating on a 0–5 scale.",
    )
    votes: int = Field(
        default=0,
        ge=0,
        description="Total number of user votes / reviews.",
    )

    # ------------------------------------------------------------------
    # Validators
    # ------------------------------------------------------------------
    @field_validator("name", "location", "city", "address", mode="before")
    @classmethod
    def strip_string(cls, v: object) -> str:
        """Coerce None/NaN to empty string and strip surrounding whitespace."""
        if v is None or (isinstance(v, float)):
            return ""
        return str(v).strip()

    @field_validator("cuisines", mode="before")
    @classmethod
    def parse_cuisines(cls, v: object) -> list[str]:
        """Accept a comma-separated string, a list, or None."""
        if v is None or (isinstance(v, float)):
            return []
        if isinstance(v, list):
            return [c.strip().title() for c in v if c and str(c).strip()]
        # Treat as comma-separated string
        return [c.strip().title() for c in str(v).split(",") if c.strip()]

    @field_validator("rating", mode="before")
    @classmethod
    def parse_rating(cls, v: object) -> float | None:
        """Convert string ratings (e.g. '4.1 /5', 'NEW', '-') to float or None."""
        if v is None or (isinstance(v, float) and v != v):  # NaN check
            return None
        raw = str(v).strip()
        # Handle patterns like '4.1 /5' or '4.1/5'
        raw = raw.split("/")[0].strip()
        try:
            parsed = float(raw)
        except ValueError:
            return None
        if parsed < 0 or parsed > 5:
            return None
        return parsed

    @field_validator("votes", mode="before")
    @classmethod
    def parse_votes(cls, v: object) -> int:
        """Coerce missing / non-numeric votes to 0."""
        if v is None or (isinstance(v, float) and v != v):
            return 0
        try:
            return int(float(str(v).replace(",", "")))
        except (ValueError, TypeError):
            return 0

    @field_validator("cost_for_two", mode="before")
    @classmethod
    def parse_cost(cls, v: object) -> float | None:
        """Parse cost strings like '₹800', '800', '1,200' to float."""
        if v is None or (isinstance(v, float) and v != v):
            return None
        raw = str(v).strip()
        # Strip currency symbols and commas
        raw = raw.replace("₹", "").replace(",", "").replace(" ", "")
        try:
            parsed = float(raw)
            return parsed if parsed >= 0 else None
        except ValueError:
            return None

    # ------------------------------------------------------------------
    # Class-level helpers
    # ------------------------------------------------------------------
    @classmethod
    def make_id(cls, name: str, location: str, city: str) -> str:
        """Create a stable SHA-1-based restaurant ID from identity fields."""
        key = f"{name.lower().strip()}|{location.lower().strip()}|{city.lower().strip()}"
        return hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]

    model_config = ConfigDict(frozen=True)  # Restaurants are value objects
