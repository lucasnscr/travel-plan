"""Unit tests for the hotel search MCP server.

Tests normalisation, scoring, filtering, retry logic, and MCP handlers
without hitting the real Enuygun upstream.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from travel_orchestrator.mcp_servers.hotels.models import (
    HotelLocation,
    HotelResult,
    HotelSearchInput,
)
from travel_orchestrator.mcp_servers.hotels.retry import RetryableError, with_retry
from travel_orchestrator.mcp_servers.hotels.scoring import compute_scores
from travel_orchestrator.mcp_servers.hotels.booking_provider import BookingProvider
from travel_orchestrator.mcp_servers.hotels.server import (
    call_tool,
    list_tools,
    normalise_raw,
    search_hotels_impl,
)


# ---------------------------------------------------------------------------
# Fixtures — raw upstream payloads
# ---------------------------------------------------------------------------


def _raw_hotel(
    *,
    name: str = "Grand Hotel",
    stars: int = 4,
    price: float = 600.0,
    review: float = 8.5,
    distance: float = 1.2,
    amenities: list[str] | None = None,
    lat: float = 41.01,
    lng: float = 28.97,
) -> dict[str, Any]:
    """Build a minimal raw upstream hotel dict."""
    return {
        "name": name,
        "stars": stars,
        "totalPrice": price,
        "currency": "USD",
        "rating": review,
        "distanceToCenter": distance,
        "amenities": amenities or ["wifi", "breakfast"],
        "latitude": lat,
        "longitude": lng,
        "url": f"https://enuygun.com/hotel/{name.lower().replace(' ', '-')}",
    }


def _make_result(
    *,
    name: str = "Grand Hotel",
    stars: int = 4,
    price_total: float = 600.0,
    review_score: float = 8.5,
    distance: float = 1.2,
    amenities: list[str] | None = None,
) -> HotelResult:
    return HotelResult(
        name=name,
        stars=stars,
        price_total=price_total,
        review_score=review_score,
        distance_to_center_km=distance,
        amenities=amenities or ["wifi", "breakfast"],
        currency="USD",
        nightly_price_avg=price_total / 3,
        location=HotelLocation(lat=41.01, lng=28.97),
    )


# ===================================================================
# Normalisation: raw → HotelResult
# ===================================================================


class TestNormaliseRaw:
    def test_basic_normalisation(self) -> None:
        raw = _raw_hotel()
        result = normalise_raw(raw, nights=3)
        assert result.name == "Grand Hotel"
        assert result.stars == 4
        assert result.price_total == 600.0
        assert result.currency == "USD"
        assert result.nightly_price_avg == 200.0
        assert result.review_score == 8.5
        assert result.distance_to_center_km == 1.2
        assert result.location.lat == 41.01
        assert result.location.lng == 28.97
        assert "wifi" in result.amenities
        assert result.deep_link is not None
        assert result.provider == "enuygun"

    def test_alternative_field_names(self) -> None:
        raw = {
            "hotelName": "Alt Hotel",
            "star_rating": 3,
            "price": 400.0,
            "priceCurrency": "EUR",
            "guestRating": 7.0,
            "distance_to_center_km": 2.5,
            "facilities": ["pool", "gym"],
            "lat": 48.86,
            "lon": 2.35,
            "neighborhood": "Marais",
            "deepLink": "https://example.com",
        }
        result = normalise_raw(raw, nights=2)
        assert result.name == "Alt Hotel"
        assert result.stars == 3
        assert result.price_total == 400.0
        assert result.currency == "EUR"
        assert result.nightly_price_avg == 200.0
        assert result.review_score == 7.0
        assert result.distance_to_center_km == 2.5
        assert "pool" in result.amenities
        assert result.location.area == "Marais"
        assert result.deep_link == "https://example.com"

    def test_missing_fields_graceful(self) -> None:
        raw = {"name": "Minimal Hotel"}
        result = normalise_raw(raw, nights=1)
        assert result.name == "Minimal Hotel"
        assert result.stars is None
        assert result.price_total is None
        assert result.review_score is None
        assert result.amenities == []

    def test_string_amenities_split(self) -> None:
        raw = {"name": "H", "amenities": "wifi, pool, spa"}
        result = normalise_raw(raw, nights=1)
        assert result.amenities == ["wifi", "pool", "spa"]

    def test_zero_nights_no_crash(self) -> None:
        raw = _raw_hotel()
        result = normalise_raw(raw, nights=0)
        assert result.nightly_price_avg is None


# ===================================================================
# Scoring
# ===================================================================


class TestScoring:
    def test_cheaper_scores_higher(self) -> None:
        hotels = [
            _make_result(name="Expensive", price_total=1000.0),
            _make_result(name="Cheap", price_total=200.0),
        ]
        scored = compute_scores(hotels)
        assert scored[0].name == "Cheap"
        assert scored[0].score > scored[1].score

    def test_closer_scores_higher(self) -> None:
        hotels = [
            _make_result(name="Far", distance=10.0, price_total=500.0),
            _make_result(name="Close", distance=0.5, price_total=500.0),
        ]
        scored = compute_scores(hotels)
        assert scored[0].name == "Close"

    def test_better_reviews_score_higher(self) -> None:
        hotels = [
            _make_result(name="Low", review_score=3.0, price_total=500.0, distance=1.0),
            _make_result(name="High", review_score=9.5, price_total=500.0, distance=1.0),
        ]
        scored = compute_scores(hotels)
        assert scored[0].name == "High"

    def test_amenity_match_boosts_score(self) -> None:
        hotels = [
            _make_result(name="NoMatch", amenities=["parking"]),
            _make_result(name="Match", amenities=["wifi", "pool", "breakfast"]),
        ]
        scored = compute_scores(hotels, desired_amenities=["wifi", "pool"])
        # Match has 2/2 desired amenities, NoMatch has 0/2
        match_hotel = next(h for h in scored if h.name == "Match")
        no_match = next(h for h in scored if h.name == "NoMatch")
        assert match_hotel.score > no_match.score

    def test_empty_list(self) -> None:
        assert compute_scores([]) == []

    def test_single_hotel(self) -> None:
        hotels = [_make_result()]
        scored = compute_scores(hotels)
        assert len(scored) == 1
        assert scored[0].score > 0

    def test_scores_between_zero_and_one(self) -> None:
        hotels = [
            _make_result(name="A", price_total=100.0, distance=0.1, review_score=10.0),
            _make_result(name="B", price_total=2000.0, distance=15.0, review_score=2.0),
        ]
        scored = compute_scores(hotels)
        for h in scored:
            assert 0.0 <= h.score <= 1.0

    def test_sorted_descending(self) -> None:
        hotels = [
            _make_result(name=f"H{i}", price_total=float(100 * (i + 1)))
            for i in range(5)
        ]
        scored = compute_scores(hotels)
        scores = [h.score for h in scored]
        assert scores == sorted(scores, reverse=True)


# ===================================================================
# Filtering (min_stars)
# ===================================================================


class TestFiltering:
    async def test_min_stars_filters(self) -> None:
        raw_hotels = [
            _raw_hotel(name="2Star", stars=2, price=200.0),
            _raw_hotel(name="4Star", stars=4, price=600.0),
            _raw_hotel(name="5Star", stars=5, price=900.0),
        ]
        with patch(
            "travel_orchestrator.mcp_servers.hotels.server._fetch_hotels",
            new_callable=AsyncMock,
            return_value=raw_hotels,
        ):
            result = await search_hotels_impl(
                destination="Istanbul",
                check_in="2025-06-01",
                check_out="2025-06-04",
                guests=2,
                min_stars=4,
            )
        names = [h["name"] for h in result]
        assert "2Star" not in names
        assert "4Star" in names
        assert "5Star" in names

    async def test_no_filter_returns_all(self) -> None:
        raw_hotels = [_raw_hotel(name=f"H{i}", stars=i + 1) for i in range(5)]
        with patch(
            "travel_orchestrator.mcp_servers.hotels.server._fetch_hotels",
            new_callable=AsyncMock,
            return_value=raw_hotels,
        ):
            result = await search_hotels_impl(
                destination="Istanbul",
                check_in="2025-06-01",
                check_out="2025-06-04",
            )
        assert len(result) == 5


# ===================================================================
# Retry logic
# ===================================================================


class TestRetry:
    async def test_succeeds_first_try(self) -> None:
        fn = AsyncMock(return_value="ok")
        result = await with_retry(fn)
        assert result == "ok"
        assert fn.call_count == 1

    async def test_retries_on_retryable_error(self) -> None:
        fn = AsyncMock(
            side_effect=[RetryableError("429", status_code=429), "ok"]
        )
        result = await with_retry(fn, max_retries=2, base_delay=0.01)
        assert result == "ok"
        assert fn.call_count == 2

    async def test_exhausts_retries(self) -> None:
        fn = AsyncMock(
            side_effect=RetryableError("500", status_code=500)
        )
        with pytest.raises(RetryableError):
            await with_retry(fn, max_retries=2, base_delay=0.01)
        assert fn.call_count == 3  # initial + 2 retries

    async def test_respects_retry_after(self) -> None:
        fn = AsyncMock(
            side_effect=[
                RetryableError("429", status_code=429, retry_after=0.01),
                "ok",
            ]
        )
        result = await with_retry(fn, max_retries=1, base_delay=0.01)
        assert result == "ok"

    async def test_non_retryable_error_still_retries(self) -> None:
        """Generic exceptions also get retried (network glitches etc.)."""
        fn = AsyncMock(side_effect=[OSError("conn reset"), "ok"])
        result = await with_retry(fn, max_retries=1, base_delay=0.01)
        assert result == "ok"


# ===================================================================
# MCP handlers
# ===================================================================


class TestMCPHandlers:
    async def test_list_tools_returns_five_tools(self) -> None:
        tools = await list_tools()
        assert len(tools) == 5
        names = {t.name for t in tools}
        assert "search_hotels" in names
        schema = tools[0].inputSchema
        assert "destination" in schema["properties"]
        assert "check_in" in schema["properties"]
        assert "check_out" in schema["properties"]

    async def test_call_tool_search_hotels(self) -> None:
        raw = [_raw_hotel(name="Test Hotel")]
        with patch(
            "travel_orchestrator.mcp_servers.hotels.server._fetch_hotels",
            new_callable=AsyncMock,
            return_value=raw,
        ):
            result = await call_tool(
                "search_hotels",
                {
                    "destination": "Istanbul",
                    "check_in": "2025-06-01",
                    "check_out": "2025-06-04",
                    "guests": 2,
                },
            )
        assert len(result) == 1
        assert result[0].type == "text"
        data = json.loads(result[0].text)
        assert isinstance(data, list)
        assert data[0]["name"] == "Test Hotel"
        assert "data_source" in data[0]

    async def test_call_tool_unknown_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown tool"):
            await call_tool("nonexistent", {})

    async def test_invalid_dates_raises(self) -> None:
        raw = [_raw_hotel()]
        with patch(
            "travel_orchestrator.mcp_servers.hotels.server._fetch_hotels",
            new_callable=AsyncMock,
            return_value=raw,
        ):
            with pytest.raises(ValueError, match="check_out must be after"):
                await call_tool(
                    "search_hotels",
                    {
                        "destination": "Istanbul",
                        "check_in": "2025-06-04",
                        "check_out": "2025-06-01",
                    },
                )


# ===================================================================
# Input validation (Pydantic)
# ===================================================================


class TestInputValidation:
    def test_valid_input(self) -> None:
        inp = HotelSearchInput(
            destination="Paris",
            check_in="2025-07-01",
            check_out="2025-07-05",
            guests=2,
            amenities=["wifi"],
        )
        assert inp.destination == "Paris"
        assert inp.guests == 2

    def test_empty_destination_rejected(self) -> None:
        with pytest.raises(Exception):
            HotelSearchInput(
                destination="",
                check_in="2025-07-01",
                check_out="2025-07-05",
            )

    def test_guests_bounds(self) -> None:
        with pytest.raises(Exception):
            HotelSearchInput(
                destination="Paris",
                check_in="2025-07-01",
                check_out="2025-07-05",
                guests=0,
            )

    def test_location_centrality_bounds(self) -> None:
        with pytest.raises(Exception):
            HotelSearchInput(
                destination="Paris",
                check_in="2025-07-01",
                check_out="2025-07-05",
                location_centrality=1.5,
            )
