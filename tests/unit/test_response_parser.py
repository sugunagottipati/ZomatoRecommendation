"""
Unit tests for ``src/llm/response_parser.py``.

Tests cover:
- Valid JSON response is parsed correctly into RecommendationResponse
- Summary field is extracted and stored
- Grounding check rejects hallucinated restaurant_ids
- Duplicate restaurant_ids are deduplicated
- Markdown code fences are stripped before parsing
- Missing 'recommendations' key raises ResponseParseError
- Non-JSON response raises ResponseParseError
- Invalid rank is replaced by positional rank
- Empty valid list after grounding raises ResponseParseError
"""

from __future__ import annotations

import json

import pytest

from src.exceptions import ResponseParseError
from src.llm.response_parser import ResponseParser
from src.models.restaurant import Restaurant


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _make_restaurant(
    name: str,
    location: str = "Koramangala",
    city: str = "Bangalore",
    cuisines: list[str] | None = None,
    rating: float | None = 4.2,
    budget_tier: str = "medium",
    cost_for_two: float | None = 900.0,
) -> Restaurant:
    return Restaurant(
        restaurant_id=Restaurant.make_id(name, location, city),
        name=name,
        city=city,
        location=location,
        cuisines=cuisines or ["North Indian"],
        rating=rating,
        budget_tier=budget_tier,  # type: ignore[arg-type]
        cost_for_two=cost_for_two,
        votes=200,
        address="",
    )


@pytest.fixture()
def restaurants() -> list[Restaurant]:
    return [
        _make_restaurant("Truffles"),
        _make_restaurant("Empire"),
        _make_restaurant("Meghana Foods"),
    ]


@pytest.fixture()
def candidate_map(restaurants: list[Restaurant]) -> dict[str, Restaurant]:
    return {r.restaurant_id: r for r in restaurants}


def _make_response(
    recs: list[dict],
    summary: str | None = "Great matches for your preferences.",
) -> str:
    payload: dict = {"recommendations": recs}
    if summary is not None:
        payload["summary"] = summary
    return json.dumps(payload)


# ---------------------------------------------------------------------------
# Happy-path tests
# ---------------------------------------------------------------------------


def test_parses_valid_response(
    candidate_map: dict[str, Restaurant],
    restaurants: list[Restaurant],
) -> None:
    rid1 = restaurants[0].restaurant_id
    rid2 = restaurants[1].restaurant_id
    raw = _make_response(
        [
            {"restaurant_id": rid1, "rank": 1, "explanation": "Best match."},
            {"restaurant_id": rid2, "rank": 2, "explanation": "Second best."},
        ]
    )
    parser = ResponseParser(candidate_map)
    result = parser.parse(raw)

    assert result.source == "llm"
    assert len(result.recommendations) == 2
    assert result.recommendations[0].rank == 1
    assert result.recommendations[0].restaurant.name == "Truffles"
    assert result.recommendations[1].rank == 2
    assert result.recommendations[1].restaurant.name == "Empire"


def test_summary_is_extracted(
    candidate_map: dict[str, Restaurant],
    restaurants: list[Restaurant],
) -> None:
    rid = restaurants[0].restaurant_id
    raw = _make_response(
        [{"restaurant_id": rid, "rank": 1, "explanation": "Good."}],
        summary="You will love these places.",
    )
    result = ResponseParser(candidate_map).parse(raw)
    assert result.summary == "You will love these places."


def test_summary_none_when_absent(
    candidate_map: dict[str, Restaurant],
    restaurants: list[Restaurant],
) -> None:
    rid = restaurants[0].restaurant_id
    raw = json.dumps(
        {"recommendations": [{"restaurant_id": rid, "rank": 1, "explanation": "Good."}]}
    )
    result = ResponseParser(candidate_map).parse(raw)
    assert result.summary is None


def test_results_sorted_by_rank(
    candidate_map: dict[str, Restaurant],
    restaurants: list[Restaurant],
) -> None:
    rid1, rid2, rid3 = (r.restaurant_id for r in restaurants)
    # Send in reverse rank order
    raw = _make_response(
        [
            {"restaurant_id": rid3, "rank": 3, "explanation": "Third."},
            {"restaurant_id": rid1, "rank": 1, "explanation": "First."},
            {"restaurant_id": rid2, "rank": 2, "explanation": "Second."},
        ]
    )
    result = ResponseParser(candidate_map).parse(raw)
    ranks = [r.rank for r in result.recommendations]
    assert ranks == sorted(ranks)


def test_markdown_fences_stripped(
    candidate_map: dict[str, Restaurant],
    restaurants: list[Restaurant],
) -> None:
    rid = restaurants[0].restaurant_id
    payload = json.dumps(
        {"recommendations": [{"restaurant_id": rid, "rank": 1, "explanation": "Good."}]}
    )
    fenced = f"```json\n{payload}\n```"
    result = ResponseParser(candidate_map).parse(fenced)
    assert len(result.recommendations) == 1


# ---------------------------------------------------------------------------
# Grounding / deduplication
# ---------------------------------------------------------------------------


def test_hallucinated_id_is_rejected(
    candidate_map: dict[str, Restaurant],
    restaurants: list[Restaurant],
) -> None:
    rid_real = restaurants[0].restaurant_id
    raw = _make_response(
        [
            {"restaurant_id": "fake-id-not-in-candidates", "rank": 1, "explanation": "Fake."},
            {"restaurant_id": rid_real, "rank": 2, "explanation": "Real."},
        ]
    )
    result = ResponseParser(candidate_map).parse(raw)
    # Only the real recommendation survives
    assert len(result.recommendations) == 1
    assert result.recommendations[0].restaurant.restaurant_id == rid_real


def test_all_hallucinated_raises(candidate_map: dict[str, Restaurant]) -> None:
    raw = _make_response(
        [{"restaurant_id": "ghost-restaurant", "rank": 1, "explanation": "Fake."}]
    )
    with pytest.raises(ResponseParseError, match="grounding"):
        ResponseParser(candidate_map).parse(raw)


def test_duplicate_ids_are_deduplicated(
    candidate_map: dict[str, Restaurant],
    restaurants: list[Restaurant],
) -> None:
    rid = restaurants[0].restaurant_id
    raw = _make_response(
        [
            {"restaurant_id": rid, "rank": 1, "explanation": "First copy."},
            {"restaurant_id": rid, "rank": 2, "explanation": "Duplicate copy."},
        ]
    )
    result = ResponseParser(candidate_map).parse(raw)
    assert len(result.recommendations) == 1


# ---------------------------------------------------------------------------
# Invalid rank handling
# ---------------------------------------------------------------------------


def test_invalid_rank_uses_positional(
    candidate_map: dict[str, Restaurant],
    restaurants: list[Restaurant],
) -> None:
    rid = restaurants[0].restaurant_id
    raw = _make_response(
        [{"restaurant_id": rid, "rank": -5, "explanation": "Bad rank."}]
    )
    result = ResponseParser(candidate_map).parse(raw)
    assert result.recommendations[0].rank >= 1


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------


def test_non_json_raises_parse_error(candidate_map: dict[str, Restaurant]) -> None:
    with pytest.raises(ResponseParseError, match="not valid JSON"):
        ResponseParser(candidate_map).parse("This is not JSON at all.")


def test_missing_recommendations_key_raises(candidate_map: dict[str, Restaurant]) -> None:
    raw = json.dumps({"summary": "No recs here."})
    with pytest.raises(ResponseParseError, match="recommendations"):
        ResponseParser(candidate_map).parse(raw)


def test_recommendations_not_a_list_raises(candidate_map: dict[str, Restaurant]) -> None:
    raw = json.dumps({"recommendations": "should be a list"})
    with pytest.raises(ResponseParseError):
        ResponseParser(candidate_map).parse(raw)
