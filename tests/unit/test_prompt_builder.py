"""
Unit tests for ``src/llm/prompt_builder.py``.

Tests cover:
- Output structure (two messages: system + user)
- System message contains grounding constraint (no hallucination)
- System message contains the limit
- User message contains location, budget, cuisine, min_rating, additional_preferences
- User message contains all candidate restaurant_ids
- Candidate list is capped at max_candidates
- None cuisine rendered as "Any"
- None min_rating rendered as "None"
- Empty additional_preferences rendered as "None"
"""

from __future__ import annotations

import json

import pytest

from src.llm.prompt_builder import PromptBuilder
from src.models.preferences import UserPreferences
from src.models.restaurant import Restaurant


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_restaurant(name: str, location: str = "Koramangala") -> Restaurant:
    return Restaurant(
        restaurant_id=Restaurant.make_id(name, location, "Bangalore"),
        name=name,
        city="Bangalore",
        location=location,
        cuisines=["Italian"],
        rating=4.2,
        budget_tier="medium",
        cost_for_two=800.0,
        votes=50,
        address="",
    )


def _make_prefs(**overrides) -> UserPreferences:
    defaults: dict = {"location": "Koramangala", "budget": "medium"}
    defaults.update(overrides)
    return UserPreferences(**defaults)


def _build(prefs: UserPreferences, candidates: list[Restaurant], max_candidates: int = 20) -> list[dict]:
    return PromptBuilder(max_candidates=max_candidates).build(prefs, candidates)


# ---------------------------------------------------------------------------
# Message structure
# ---------------------------------------------------------------------------

class TestMessageStructure:
    def test_returns_two_messages(self):
        msgs = _build(_make_prefs(), [_make_restaurant("R1")])
        assert len(msgs) == 2

    def test_first_message_is_system(self):
        msgs = _build(_make_prefs(), [_make_restaurant("R1")])
        assert msgs[0]["role"] == "system"

    def test_second_message_is_user(self):
        msgs = _build(_make_prefs(), [_make_restaurant("R1")])
        assert msgs[1]["role"] == "user"

    def test_both_messages_have_content(self):
        msgs = _build(_make_prefs(), [_make_restaurant("R1")])
        assert msgs[0]["content"]
        assert msgs[1]["content"]


# ---------------------------------------------------------------------------
# System message content
# ---------------------------------------------------------------------------

class TestSystemMessage:
    def test_system_contains_grounding_constraint(self):
        msgs = _build(_make_prefs(), [_make_restaurant("R1")])
        system = msgs[0]["content"]
        assert "candidates" in system.lower() or "candidate" in system.lower()
        assert "not" in system.lower()  # "do NOT invent"

    def test_system_contains_json_schema(self):
        msgs = _build(_make_prefs(), [_make_restaurant("R1")])
        system = msgs[0]["content"]
        assert "restaurant_id" in system
        assert "explanation" in system
        assert "summary" in system

    def test_system_contains_limit(self):
        prefs = _make_prefs(limit=3)
        msgs = _build(prefs, [_make_restaurant("R1")])
        assert "3" in msgs[0]["content"]


# ---------------------------------------------------------------------------
# User message content
# ---------------------------------------------------------------------------

class TestUserMessage:
    def test_user_contains_location(self):
        prefs = _make_prefs(location="Indiranagar")
        msgs = _build(prefs, [_make_restaurant("R1", location="Indiranagar")])
        assert "Indiranagar" in msgs[1]["content"]

    def test_user_contains_budget(self):
        prefs = _make_prefs(budget="high")
        msgs = _build(prefs, [_make_restaurant("R1")])
        assert "high" in msgs[1]["content"]

    def test_user_contains_cuisine(self):
        prefs = _make_prefs(cuisine="Italian")
        msgs = _build(prefs, [_make_restaurant("R1")])
        assert "Italian" in msgs[1]["content"]

    def test_none_cuisine_shown_as_any(self):
        prefs = _make_prefs(cuisine=None)
        msgs = _build(prefs, [_make_restaurant("R1")])
        assert "Any" in msgs[1]["content"]

    def test_min_rating_included(self):
        prefs = _make_prefs(min_rating=4.0)
        msgs = _build(prefs, [_make_restaurant("R1")])
        assert "4.0" in msgs[1]["content"]

    def test_none_min_rating_shown_as_none(self):
        prefs = _make_prefs(min_rating=None)
        msgs = _build(prefs, [_make_restaurant("R1")])
        assert "None" in msgs[1]["content"]

    def test_additional_preferences_included(self):
        prefs = _make_prefs(additional_preferences=["family-friendly", "rooftop"])
        msgs = _build(prefs, [_make_restaurant("R1")])
        assert "family-friendly" in msgs[1]["content"]
        assert "rooftop" in msgs[1]["content"]

    def test_empty_additional_preferences_shown_as_none(self):
        prefs = _make_prefs(additional_preferences=[])
        msgs = _build(prefs, [_make_restaurant("R1")])
        assert "None" in msgs[1]["content"]

    def test_user_contains_limit(self):
        prefs = _make_prefs(limit=7)
        msgs = _build(prefs, [_make_restaurant("R1")])
        assert "7" in msgs[1]["content"]


# ---------------------------------------------------------------------------
# Candidate serialisation
# ---------------------------------------------------------------------------

class TestCandidateSerialisation:
    def test_all_candidate_ids_in_user_message(self):
        candidates = [_make_restaurant(f"R{i}") for i in range(5)]
        msgs = _build(_make_prefs(), candidates)
        user_content = msgs[1]["content"]
        for c in candidates:
            assert c.restaurant_id in user_content

    def test_candidates_serialised_as_valid_json(self):
        candidates = [_make_restaurant("R1"), _make_restaurant("R2")]
        msgs = _build(_make_prefs(), candidates)
        user_content = msgs[1]["content"]
        # Extract the JSON block — it should be parseable
        start = user_content.index("[")
        end = user_content.rindex("]") + 1
        parsed = json.loads(user_content[start:end])
        assert len(parsed) == 2
        assert parsed[0]["name"] == "R1"

    def test_candidate_fields_present(self):
        candidates = [_make_restaurant("R1")]
        msgs = _build(_make_prefs(), candidates)
        user_content = msgs[1]["content"]
        for field in ("restaurant_id", "name", "cuisines", "rating", "cost_for_two", "budget_tier"):
            assert field in user_content


# ---------------------------------------------------------------------------
# Candidate cap
# ---------------------------------------------------------------------------

class TestCandidateCap:
    def test_candidates_capped_at_max(self):
        candidates = [_make_restaurant(f"R{i}") for i in range(10)]
        msgs = _build(_make_prefs(), candidates, max_candidates=3)
        user_content = msgs[1]["content"]
        # Only first 3 restaurant IDs should appear
        present = sum(1 for c in candidates if c.restaurant_id in user_content)
        assert present == 3

    def test_no_cap_includes_all(self):
        candidates = [_make_restaurant(f"R{i}") for i in range(5)]
        msgs = _build(_make_prefs(), candidates, max_candidates=20)
        user_content = msgs[1]["content"]
        assert all(c.restaurant_id in user_content for c in candidates)
