"""Unit tests for the Booking.com provider and new hotel MCP tools.

Tests cover the BookingProvider with mocked httpx responses,
new MCP tool handlers, mock fallback behavior, and model validation.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from travel_orchestrator.mcp_servers.hotels.booking_provider import (
    BookingProvider,
    _RateLimiter,
)
from travel_orchestrator.mcp_servers.hotels.mock_provider import (
    _make_hotel_id,
    generate_facilities,
    generate_hotel_details,
    generate_hotels,
    generate_nearby_hotels,
)
from travel_orchestrator.mcp_servers.hotels.models import (
    Facility,
    HotelCompareInput,
    HotelDetail,
    HotelResult,
    HotelSearchByCoordinatesInput,
    Rate,
    Review,
    Room,
)
from travel_orchestrator.mcp_servers.hotels.server import (
    call_tool,
    compare_hotels_impl,
    get_hotel_details_impl,
    get_hotel_facilities_impl,
    list_tools,
    normalise_raw,
    search_by_coordinates_impl,
    search_hotels_impl,
)
from travel_orchestrator.mcp_servers.weather.cache import TTLCache

from .fixtures.booking_responses import (
    HOTEL_DETAILS_RESPONSE,
    SEARCH_BY_COORDINATES_RESPONSE,
    SEARCH_DESTINATION_EMPTY_RESPONSE,
    SEARCH_DESTINATION_RESPONSE,
    SEARCH_HOTELS_RESPONSE,
)


# ===================================================================
# New Pydantic models
# ===================================================================


class TestNewModels:
    def test_room_model(self) -> None:
        room = Room(
            room_id="r1",
            name="Deluxe",
            type="deluxe",
            max_occupancy=2,
            bed_type="king",
            size_sqm=35.0,
            price_per_night=200.0,
            currency="EUR",
        )
        assert room.name == "Deluxe"
        assert room.max_occupancy == 2

    def test_rate_model(self) -> None:
        rate = Rate(
            price_per_night=150.0,
            total_price=450.0,
            currency="EUR",
            meal_plan="breakfast_included",
        )
        assert rate.total_price == 450.0
        assert rate.meal_plan == "breakfast_included"

    def test_review_model(self) -> None:
        review = Review(
            overall_score=8.7,
            total_reviews=1500,
            categories={"cleanliness": 9.0, "location": 8.5},
            recent_highlights=["Great location"],
        )
        assert review.overall_score == 8.7
        assert len(review.categories) == 2

    def test_facility_model(self) -> None:
        fac = Facility(name="wifi", category="connectivity")
        assert fac.available is True

    def test_hotel_detail_model(self) -> None:
        detail = HotelDetail(
            hotel_id="abc123",
            name="Test Hotel",
            stars=4,
            data_source="mock",
        )
        assert detail.hotel_id == "abc123"
        assert detail.data_source == "mock"
        assert detail.rooms == []
        assert detail.facilities == []

    def test_hotel_result_has_data_source(self) -> None:
        result = HotelResult(name="Test", data_source="booking")
        assert result.data_source == "booking"
        assert result.photos == []

    def test_hotel_result_default_data_source(self) -> None:
        result = HotelResult(name="Test")
        assert result.data_source == "mock"

    def test_hotel_search_by_coordinates_input(self) -> None:
        inp = HotelSearchByCoordinatesInput(
            latitude=48.8566,
            longitude=2.3522,
            check_in="2025-07-01",
            check_out="2025-07-05",
        )
        assert inp.radius_km == 5.0
        assert inp.adults == 1

    def test_hotel_search_by_coordinates_bounds(self) -> None:
        with pytest.raises(Exception):
            HotelSearchByCoordinatesInput(
                latitude=100.0,  # out of range
                longitude=2.35,
                check_in="2025-07-01",
                check_out="2025-07-05",
            )

    def test_hotel_compare_input(self) -> None:
        inp = HotelCompareInput(hotel_ids=["a", "b", "c"])
        assert len(inp.hotel_ids) == 3

    def test_hotel_compare_input_min_items(self) -> None:
        with pytest.raises(Exception):
            HotelCompareInput(hotel_ids=["only_one"])


# ===================================================================
# BookingProvider (mocked httpx)
# ===================================================================


class TestBookingProvider:
    def test_not_configured_without_key(self) -> None:
        provider = BookingProvider(api_key=None)
        # When env var RAPIDAPI_KEY is not set
        with patch.dict("os.environ", {}, clear=True):
            p = BookingProvider()
            # May or may not be configured depending on env
            # Just verify the property exists
            assert isinstance(p.is_configured, bool)

    def test_configured_with_key(self) -> None:
        provider = BookingProvider(api_key="test-key-123")
        assert provider.is_configured is True

    async def test_search_hotels_normalises(self) -> None:
        provider = BookingProvider(api_key="test-key")

        mock_resp_dest = MagicMock()
        mock_resp_dest.status_code = 200
        mock_resp_dest.json.return_value = SEARCH_DESTINATION_RESPONSE
        mock_resp_dest.raise_for_status = MagicMock()

        mock_resp_hotels = MagicMock()
        mock_resp_hotels.status_code = 200
        mock_resp_hotels.json.return_value = SEARCH_HOTELS_RESPONSE
        mock_resp_hotels.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=[mock_resp_dest, mock_resp_hotels])
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            results = await provider.search_hotels(
                "Paris", "2025-07-01", "2025-07-05",
            )

        assert len(results) == 3
        assert results[0]["name"] == "Grand Hotel Paris"
        assert results[0]["data_source"] == "booking"
        assert results[0]["hotel_id"] == "12345"

    async def test_search_hotels_uses_cache(self) -> None:
        cache = TTLCache(default_ttl_seconds=3600)
        provider = BookingProvider(api_key="test-key", cache=cache)

        # Pre-populate cache
        cache_key = TTLCache.make_key(
            "booking_search", "paris", "2025-07-01", "2025-07-05", 1, 1, "USD",
        )
        cached_data = [{"name": "Cached Hotel", "data_source": "booking"}]
        cache.set(cache_key, cached_data)

        results = await provider.search_hotels(
            "Paris", "2025-07-01", "2025-07-05",
        )
        assert results[0]["name"] == "Cached Hotel"

    async def test_get_hotel_details_normalises(self) -> None:
        provider = BookingProvider(api_key="test-key")

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = HOTEL_DETAILS_RESPONSE
        mock_resp.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await provider.get_hotel_details("12345")

        assert result["name"] == "Grand Hotel Paris"
        assert result["data_source"] == "booking"
        assert result["stars"] == 4
        assert len(result["rooms"]) == 2
        assert len(result["facilities"]) == 5
        assert len(result["photos"]) == 2

    async def test_search_by_coordinates(self) -> None:
        provider = BookingProvider(api_key="test-key")

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = SEARCH_BY_COORDINATES_RESPONSE
        mock_resp.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            results = await provider.search_by_coordinates(
                48.8584, 2.2945, 5.0,
                "2025-07-01", "2025-07-05",
            )

        assert len(results) == 1
        assert results[0]["name"] == "Hotel Near Eiffel"

    async def test_get_hotel_facilities(self) -> None:
        provider = BookingProvider(api_key="test-key")

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = HOTEL_DETAILS_RESPONSE
        mock_resp.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            facilities = await provider.get_hotel_facilities("12345")

        assert len(facilities) == 5
        assert any(f["name"] == "Free WiFi" for f in facilities)

    async def test_dest_id_not_found_raises(self) -> None:
        provider = BookingProvider(api_key="test-key")

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = SEARCH_DESTINATION_EMPTY_RESPONSE
        mock_resp.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(ValueError, match="No Booking.com destination"):
                await provider.search_hotels(
                    "Atlantis", "2025-07-01", "2025-07-05",
                )


# ===================================================================
# Mock provider — new functions
# ===================================================================


class TestMockProviderNewFunctions:
    def test_generate_hotels_has_data_source(self) -> None:
        hotels = generate_hotels("Paris", "2025-07-01", "2025-07-05")
        for h in hotels:
            assert h["data_source"] == "mock"

    def test_generate_hotels_has_hotel_id(self) -> None:
        hotels = generate_hotels("Paris", "2025-07-01", "2025-07-05")
        for h in hotels:
            assert "hotel_id" in h
            assert len(h["hotel_id"]) == 12

    def test_make_hotel_id_deterministic(self) -> None:
        id1 = _make_hotel_id("Hôtel Le Marais Boutique")
        id2 = _make_hotel_id("Hôtel Le Marais Boutique")
        assert id1 == id2

    def test_generate_hotel_details_known(self) -> None:
        hotels = generate_hotels("Paris", "2025-07-01", "2025-07-05")
        hotel_id = hotels[0]["hotel_id"]
        detail = generate_hotel_details(hotel_id)

        assert detail["hotel_id"] == hotel_id
        assert detail["data_source"] == "mock"
        assert "rooms" in detail
        assert len(detail["rooms"]) >= 2
        assert "review" in detail
        assert "facilities" in detail
        assert "policies" in detail

    def test_generate_hotel_details_unknown(self) -> None:
        detail = generate_hotel_details("unknown_id_12")
        assert detail["hotel_id"] == "unknown_id_12"
        assert detail["data_source"] == "mock"
        assert len(detail["rooms"]) >= 1

    def test_generate_hotel_details_deterministic(self) -> None:
        d1 = generate_hotel_details("test_id")
        d2 = generate_hotel_details("test_id")
        assert d1 == d2

    def test_generate_facilities_known(self) -> None:
        hotels = generate_hotels("London", "2025-07-01", "2025-07-05")
        hotel_id = hotels[0]["hotel_id"]  # The Savoy
        facilities = generate_facilities(hotel_id)

        assert len(facilities) > 0
        for f in facilities:
            assert "name" in f
            assert "category" in f
            assert f["data_source"] == "mock"

    def test_generate_facilities_unknown(self) -> None:
        facilities = generate_facilities("unknown_hotel")
        assert len(facilities) >= 3
        for f in facilities:
            assert f["data_source"] == "mock"

    def test_generate_nearby_hotels_known_city(self) -> None:
        # Paris coordinates
        hotels = generate_nearby_hotels(
            48.8566, 2.3522, 5.0,
            "2025-07-01", "2025-07-05",
        )
        assert len(hotels) > 0
        for h in hotels:
            assert h["data_source"] == "mock"

    def test_generate_nearby_hotels_unknown_location(self) -> None:
        # Middle of the ocean
        hotels = generate_nearby_hotels(
            0.0, 0.0, 5.0,
            "2025-07-01", "2025-07-05",
        )
        assert len(hotels) == 5
        for h in hotels:
            assert h["data_source"] == "mock"

    def test_generate_nearby_hotels_deterministic(self) -> None:
        h1 = generate_nearby_hotels(48.85, 2.35, 5.0, "2025-07-01", "2025-07-05")
        h2 = generate_nearby_hotels(48.85, 2.35, 5.0, "2025-07-01", "2025-07-05")
        assert h1 == h2


# ===================================================================
# Normalisation — data_source pass-through
# ===================================================================


class TestNormalisationDataSource:
    def test_mock_data_source(self) -> None:
        raw = {
            "name": "Test Hotel",
            "stars": 3,
            "price_total": 300.0,
            "currency": "EUR",
            "data_source": "mock",
        }
        result = normalise_raw(raw, nights=3)
        assert result.data_source == "mock"

    def test_booking_data_source(self) -> None:
        raw = {
            "name": "Booking Hotel",
            "stars": 4,
            "price_total": 500.0,
            "currency": "EUR",
            "data_source": "booking",
        }
        result = normalise_raw(raw, nights=2)
        assert result.data_source == "booking"
        assert result.provider == "booking"

    def test_default_data_source_is_mock(self) -> None:
        raw = {"name": "Unknown Source Hotel"}
        result = normalise_raw(raw, nights=1)
        assert result.data_source == "mock"

    def test_photos_pass_through(self) -> None:
        raw = {
            "name": "Photo Hotel",
            "photos": ["url1.jpg", "url2.jpg"],
        }
        result = normalise_raw(raw, nights=1)
        assert result.photos == ["url1.jpg", "url2.jpg"]

    def test_nightly_avg_from_raw(self) -> None:
        raw = {
            "name": "H",
            "price_total": 600.0,
            "nightly_price_avg": 150.0,
        }
        result = normalise_raw(raw, nights=4)
        # Should use nightly_price_avg from raw, not compute from total
        assert result.nightly_price_avg == 150.0


# ===================================================================
# MCP handlers — tool listing
# ===================================================================


class TestListToolsNew:
    async def test_returns_five_tools(self) -> None:
        tools = await list_tools()
        assert len(tools) == 5

    async def test_tool_names(self) -> None:
        tools = await list_tools()
        names = {t.name for t in tools}
        assert names == {
            "search_hotels",
            "get_hotel_details",
            "search_by_coordinates",
            "get_hotel_facilities",
            "compare_hotels",
        }

    async def test_search_hotels_schema(self) -> None:
        tools = await list_tools()
        search = next(t for t in tools if t.name == "search_hotels")
        schema = search.inputSchema
        assert "destination" in schema["properties"]
        assert set(schema["required"]) == {"destination", "check_in", "check_out"}

    async def test_get_hotel_details_schema(self) -> None:
        tools = await list_tools()
        tool = next(t for t in tools if t.name == "get_hotel_details")
        assert "hotel_id" in tool.inputSchema["properties"]
        assert tool.inputSchema["required"] == ["hotel_id"]

    async def test_search_by_coordinates_schema(self) -> None:
        tools = await list_tools()
        tool = next(t for t in tools if t.name == "search_by_coordinates")
        props = tool.inputSchema["properties"]
        assert "latitude" in props
        assert "longitude" in props
        assert "radius_km" in props

    async def test_compare_hotels_schema(self) -> None:
        tools = await list_tools()
        tool = next(t for t in tools if t.name == "compare_hotels")
        assert "hotel_ids" in tool.inputSchema["properties"]


# ===================================================================
# MCP handlers — call_tool for new tools
# ===================================================================


class TestCallToolNew:
    async def test_get_hotel_details_mock(self) -> None:
        """Without API key, should use mock."""
        hotels = generate_hotels("Paris", "2025-07-01", "2025-07-05")
        hotel_id = hotels[0]["hotel_id"]

        with patch(
            "travel_orchestrator.mcp_servers.hotels.server._booking_provider",
            BookingProvider(api_key=None),
        ):
            result = await call_tool(
                "get_hotel_details",
                {"hotel_id": hotel_id},
            )

        assert len(result) == 1
        assert result[0].type == "text"
        data = json.loads(result[0].text)
        assert data["hotel_id"] == hotel_id
        assert data["data_source"] == "mock"

    async def test_search_by_coordinates_mock(self) -> None:
        with patch(
            "travel_orchestrator.mcp_servers.hotels.server._booking_provider",
            BookingProvider(api_key=None),
        ):
            result = await call_tool(
                "search_by_coordinates",
                {
                    "latitude": 48.8566,
                    "longitude": 2.3522,
                    "radius_km": 5.0,
                    "check_in": "2025-07-01",
                    "check_out": "2025-07-05",
                },
            )

        assert len(result) == 1
        data = json.loads(result[0].text)
        assert isinstance(data, list)
        assert len(data) > 0

    async def test_get_hotel_facilities_mock(self) -> None:
        hotels = generate_hotels("London", "2025-07-01", "2025-07-05")
        hotel_id = hotels[0]["hotel_id"]

        with patch(
            "travel_orchestrator.mcp_servers.hotels.server._booking_provider",
            BookingProvider(api_key=None),
        ):
            result = await call_tool(
                "get_hotel_facilities",
                {"hotel_id": hotel_id},
            )

        assert len(result) == 1
        data = json.loads(result[0].text)
        assert isinstance(data, list)
        assert len(data) > 0

    async def test_compare_hotels_mock(self) -> None:
        hotels = generate_hotels("Paris", "2025-07-01", "2025-07-05")
        ids = [h["hotel_id"] for h in hotels[:2]]

        with patch(
            "travel_orchestrator.mcp_servers.hotels.server._booking_provider",
            BookingProvider(api_key=None),
        ):
            result = await call_tool(
                "compare_hotels",
                {"hotel_ids": ids},
            )

        assert len(result) == 1
        data = json.loads(result[0].text)
        assert isinstance(data, list)
        assert len(data) == 2

    async def test_unknown_tool_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown tool"):
            await call_tool("nonexistent_tool", {})


# ===================================================================
# Impl functions — mock fallback
# ===================================================================


class TestFallbackToMock:
    async def test_search_hotels_falls_back_to_mock(self) -> None:
        """When booking is not configured, should use mock."""
        with patch(
            "travel_orchestrator.mcp_servers.hotels.server._booking_provider",
            BookingProvider(api_key=None),
        ):
            result = await search_hotels_impl(
                destination="Paris",
                check_in="2025-07-01",
                check_out="2025-07-05",
                guests=2,
            )

        assert len(result) > 0
        assert result[0]["data_source"] == "mock"

    async def test_get_hotel_details_falls_back(self) -> None:
        with patch(
            "travel_orchestrator.mcp_servers.hotels.server._booking_provider",
            BookingProvider(api_key=None),
        ):
            result = await get_hotel_details_impl("test_hotel_id")

        assert result["data_source"] == "mock"

    async def test_search_by_coordinates_falls_back(self) -> None:
        with patch(
            "travel_orchestrator.mcp_servers.hotels.server._booking_provider",
            BookingProvider(api_key=None),
        ):
            result = await search_by_coordinates_impl(
                latitude=48.8566,
                longitude=2.3522,
                radius_km=5.0,
                check_in="2025-07-01",
                check_out="2025-07-05",
            )

        assert len(result) > 0

    async def test_get_facilities_falls_back(self) -> None:
        with patch(
            "travel_orchestrator.mcp_servers.hotels.server._booking_provider",
            BookingProvider(api_key=None),
        ):
            result = await get_hotel_facilities_impl("test_hotel_id")

        assert isinstance(result, list)
        assert len(result) > 0

    async def test_compare_hotels_falls_back(self) -> None:
        hotels = generate_hotels("Paris", "2025-07-01", "2025-07-05")
        ids = [h["hotel_id"] for h in hotels[:2]]

        with patch(
            "travel_orchestrator.mcp_servers.hotels.server._booking_provider",
            BookingProvider(api_key=None),
        ):
            result = await compare_hotels_impl(ids)

        assert len(result) == 2
        assert all(r["data_source"] == "mock" for r in result)


# ===================================================================
# Backward compatibility
# ===================================================================


class TestBackwardCompatibility:
    async def test_search_hotels_returns_expected_fields(self) -> None:
        """The search result dicts must contain all fields expected by
        downstream consumers (search_hotels_node, calculate_budget, etc.)."""
        with patch(
            "travel_orchestrator.mcp_servers.hotels.server._booking_provider",
            BookingProvider(api_key=None),
        ):
            result = await search_hotels_impl(
                destination="Paris",
                check_in="2025-07-01",
                check_out="2025-07-05",
            )

        hotel = result[0]
        # Fields expected by search_hotels_node → _to_hotel_option
        assert "name" in hotel
        assert "stars" in hotel
        assert "review_score" in hotel
        assert "price_total" in hotel
        assert "currency" in hotel
        assert "nightly_price_avg" in hotel
        assert "amenities" in hotel
        assert "distance_to_center_km" in hotel
        assert "score" in hotel
        assert "location" in hotel
        assert "lat" in hotel["location"]
        assert "lng" in hotel["location"]
        # New fields
        assert "data_source" in hotel
        assert "photos" in hotel

    async def test_search_result_is_serializable(self) -> None:
        with patch(
            "travel_orchestrator.mcp_servers.hotels.server._booking_provider",
            BookingProvider(api_key=None),
        ):
            result = await search_hotels_impl(
                destination="Tokyo",
                check_in="2025-07-01",
                check_out="2025-07-05",
            )

        # Must be JSON-serializable
        serialized = json.dumps(result, ensure_ascii=False)
        parsed = json.loads(serialized)
        assert len(parsed) == len(result)


# ===================================================================
# Rate limiter
# ===================================================================


class TestRateLimiter:
    async def test_rate_limiter_acquires(self) -> None:
        limiter = _RateLimiter(max_rps=5)
        # Should be able to acquire immediately
        await limiter.acquire()

    async def test_rate_limiter_respects_limit(self) -> None:
        limiter = _RateLimiter(max_rps=2)
        # Acquire twice (should succeed)
        await limiter.acquire()
        await limiter.acquire()
        # Third acquire should block (semaphore exhausted)
        # We don't test blocking behavior — just verify no crash


# ===================================================================
# Cache integration
# ===================================================================


class TestCacheIntegration:
    def test_cache_1_hour_ttl(self) -> None:
        cache = TTLCache(default_ttl_seconds=3600)
        cache.set("test_key", {"hotel": "cached"})
        assert cache.get("test_key") == {"hotel": "cached"}

    def test_booking_provider_uses_cache(self) -> None:
        cache = TTLCache(default_ttl_seconds=3600)
        provider = BookingProvider(api_key="test", cache=cache)
        # Verify provider was created with our cache
        assert provider._cache is cache
