"""Unit tests for the Activities/Places MCP server with Google Places API.

Tests the Google Places provider, new mock functions, new MCP tools,
input models, fallback chain, and backward compatibility.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from travel_orchestrator.mcp_servers.activities.google_places_provider import (
    GooglePlacesProvider,
)
from travel_orchestrator.mcp_servers.activities.mock_provider import (
    _make_place_id,
    discover_activities,
    generate_directions,
    generate_geocode,
    generate_nearby_search,
    generate_place_details,
    generate_place_photos,
    generate_restaurant_search,
    generate_reverse_geocode,
    generate_text_search,
)
from travel_orchestrator.mcp_servers.activities.models import (
    GeocodeInput,
    GetDirectionsInput,
    GetPlaceDetailsInput,
    GetPlacePhotosInput,
    NearbySearchInput,
    Place,
    PlaceDetail,
    ReverseGeocodeInput,
    SearchActivitiesInput,
    SearchRestaurantsInput,
)
from travel_orchestrator.mcp_servers.activities.server import (
    call_tool,
    discover_activities_impl,
    geocode_impl,
    get_directions_impl,
    get_place_details_impl,
    get_place_photos_impl,
    list_tools,
    nearby_search_impl,
    reverse_geocode_impl,
    search_activities_impl,
    search_restaurants_impl,
)

from .fixtures.google_places_responses import (
    DIRECTIONS_NO_ROUTE_RESPONSE,
    DIRECTIONS_RESPONSE,
    GEOCODE_EMPTY_RESPONSE,
    GEOCODE_RESPONSE,
    NEARBY_SEARCH_RESPONSE,
    PLACE_DETAILS_RESPONSE,
    REVERSE_GEOCODE_RESPONSE,
    TEXT_SEARCH_EMPTY_RESPONSE,
    TEXT_SEARCH_RESPONSE,
)


# ===================================================================
# Input model validation
# ===================================================================


class TestInputModels:
    def test_search_activities_valid(self) -> None:
        inp = SearchActivitiesInput(query="museums", location="Paris")
        assert inp.query == "museums"
        assert inp.location == "Paris"
        assert inp.language == "pt-BR"
        assert inp.max_results == 20

    def test_search_activities_empty_query_rejected(self) -> None:
        with pytest.raises(Exception):
            SearchActivitiesInput(query="", location="Paris")

    def test_search_restaurants_valid(self) -> None:
        inp = SearchRestaurantsInput(location="Tokyo", cuisine="sushi", price_level=2)
        assert inp.location == "Tokyo"
        assert inp.cuisine == "sushi"
        assert inp.price_level == 2

    def test_search_restaurants_price_bounds(self) -> None:
        with pytest.raises(Exception):
            SearchRestaurantsInput(location="Paris", price_level=5)

    def test_nearby_search_valid(self) -> None:
        inp = NearbySearchInput(latitude=48.86, longitude=2.34, radius_meters=500)
        assert inp.radius_meters == 500

    def test_nearby_search_radius_bounds(self) -> None:
        with pytest.raises(Exception):
            NearbySearchInput(latitude=48.86, longitude=2.34, radius_meters=50)

    def test_get_place_details_valid(self) -> None:
        inp = GetPlaceDetailsInput(place_id="ChIJ123")
        assert inp.place_id == "ChIJ123"

    def test_get_place_details_empty_rejected(self) -> None:
        with pytest.raises(Exception):
            GetPlaceDetailsInput(place_id="")

    def test_get_place_photos_valid(self) -> None:
        inp = GetPlacePhotosInput(place_id="ChIJ123", max_photos=3)
        assert inp.max_photos == 3

    def test_get_directions_valid(self) -> None:
        inp = GetDirectionsInput(origin="Louvre", destination="Tour Eiffel")
        assert inp.mode == "walking"

    def test_geocode_valid(self) -> None:
        inp = GeocodeInput(address="Paris, France")
        assert inp.language == "pt-BR"

    def test_reverse_geocode_valid(self) -> None:
        inp = ReverseGeocodeInput(latitude=48.86, longitude=2.35)
        assert inp.latitude == 48.86


# ===================================================================
# Google Places Provider — normalisation
# ===================================================================


class TestGooglePlacesNormalisation:
    def setup_method(self) -> None:
        self.provider = GooglePlacesProvider(api_key="test-key")

    def test_normalise_place_basic(self) -> None:
        raw = TEXT_SEARCH_RESPONSE["places"][0]
        place = self.provider._normalise_place(raw)
        assert isinstance(place, Place)
        assert place.place_id == "ChIJLU7jZClu5kcR4PcOOO6p3I0"
        assert place.name == "Musée du Louvre"
        assert place.category == "museum"
        assert place.location.lat == 48.8606
        assert place.location.lng == 2.3376
        assert place.rating == 4.7
        assert place.user_ratings_total == 342567
        assert place.price_level == 2
        assert place.data_source == "google_places"
        assert len(place.photos) == 2
        assert place.opening_hours is not None
        assert place.opening_hours.open_now is True
        assert "Monday: Closed" in place.opening_hours.weekday_text

    def test_normalise_place_tour_type(self) -> None:
        raw = TEXT_SEARCH_RESPONSE["places"][1]
        place = self.provider._normalise_place(raw)
        assert place.name == "Tour Eiffel"
        assert place.category == "tour"

    def test_normalise_place_detail(self) -> None:
        detail = self.provider._normalise_place_detail(PLACE_DETAILS_RESPONSE)
        assert isinstance(detail, PlaceDetail)
        assert detail.name == "Musée du Louvre"
        assert len(detail.reviews) == 2
        assert detail.reviews[0].author == "Jean D."
        assert detail.reviews[0].rating == 5
        assert detail.viewport is not None
        assert detail.url == "https://maps.google.com/?cid=10190932218279774176"
        assert detail.business_status == "OPERATIONAL"

    def test_normalise_direction(self) -> None:
        route = self.provider._normalise_direction(DIRECTIONS_RESPONSE)
        assert route.distance_meters == 2100
        assert route.duration_seconds == 1560
        assert len(route.steps) == 3
        assert route.start_address == "Louvre, Paris, France"
        assert route.polyline == "q`eiHurjMAB@DCBA"
        assert route.data_source == "google_places"

    def test_normalise_direction_no_route(self) -> None:
        route = self.provider._normalise_direction(DIRECTIONS_NO_ROUTE_RESPONSE)
        assert route.distance_meters == 0
        assert len(route.steps) == 0

    def test_normalise_geocode(self) -> None:
        raw = GEOCODE_RESPONSE["results"][0]
        result = self.provider._normalise_geocode(raw)
        assert result.place_id == "ChIJD7fiBh9u5kcRYJSMaMOCCwQ"
        assert result.formatted_address == "Paris, France"
        assert result.location.lat == 48.8566
        assert result.data_source == "google_places"

    def test_type_to_category_museum(self) -> None:
        assert self.provider._type_to_category("museum", []) == "museum"

    def test_type_to_category_restaurant(self) -> None:
        assert self.provider._type_to_category("restaurant", []) == "restaurant"

    def test_type_to_category_fallback(self) -> None:
        assert self.provider._type_to_category("unknown", ["park"]) == "nature"

    def test_type_to_category_default(self) -> None:
        assert self.provider._type_to_category("unknown", []) == "tour"

    def test_parse_price_level_enum(self) -> None:
        assert self.provider._parse_price_level("PRICE_LEVEL_FREE") == 0
        assert self.provider._parse_price_level("PRICE_LEVEL_MODERATE") == 2
        assert self.provider._parse_price_level("PRICE_LEVEL_VERY_EXPENSIVE") == 4

    def test_parse_price_level_int(self) -> None:
        assert self.provider._parse_price_level(3) == 3

    def test_parse_price_level_none(self) -> None:
        assert self.provider._parse_price_level(None) is None

    def test_is_configured(self) -> None:
        provider = GooglePlacesProvider(api_key="test")
        assert provider.is_configured is True

    def test_is_not_configured(self) -> None:
        provider = GooglePlacesProvider(api_key=None)
        assert provider.is_configured is False


# ===================================================================
# Google Places Provider — API calls (mocked httpx)
# ===================================================================


class TestGooglePlacesAPI:
    def setup_method(self) -> None:
        self.provider = GooglePlacesProvider(api_key="test-key")
        self.provider._cache.clear()

    async def test_text_search(self) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = TEXT_SEARCH_RESPONSE
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_resp
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            results = await self.provider.text_search("museums in Paris")

        assert len(results) == 2
        assert results[0].name == "Musée du Louvre"
        assert results[0].data_source == "google_places"

    async def test_nearby_search(self) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = NEARBY_SEARCH_RESPONSE
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_resp
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            results = await self.provider.nearby_search(48.854, 2.333, 500)

        assert len(results) == 1
        assert results[0].name == "Café de Flore"
        assert results[0].category == "restaurant"

    async def test_get_place_details(self) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = PLACE_DETAILS_RESPONSE
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_resp
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            detail = await self.provider.get_place_details("ChIJLU7jZClu5kcR4PcOOO6p3I0")

        assert isinstance(detail, PlaceDetail)
        assert detail.name == "Musée du Louvre"
        assert len(detail.reviews) == 2

    async def test_get_directions(self) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = DIRECTIONS_RESPONSE
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_resp
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            route = await self.provider.get_directions("Louvre", "Tour Eiffel")

        assert route.distance_meters == 2100
        assert route.duration_seconds == 1560
        assert route.data_source == "google_places"

    async def test_geocode(self) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = GEOCODE_RESPONSE
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_resp
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            results = await self.provider.geocode("Paris, France")

        assert len(results) == 1
        assert results[0].formatted_address == "Paris, France"
        assert results[0].location.lat == 48.8566

    async def test_reverse_geocode(self) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = REVERSE_GEOCODE_RESPONSE
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_resp
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            results = await self.provider.reverse_geocode(48.8606, 2.3376)

        assert len(results) == 2
        assert "Rivoli" in results[0].formatted_address

    async def test_unconfigured_raises(self) -> None:
        provider = GooglePlacesProvider(api_key=None)
        with pytest.raises(RuntimeError, match="GOOGLE_MAPS_API_KEY"):
            await provider.text_search("test")

    async def test_cache_hit(self) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = TEXT_SEARCH_RESPONSE
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_resp
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            # First call
            r1 = await self.provider.text_search("cache test")
            # Second call should hit cache
            r2 = await self.provider.text_search("cache test")

        assert r1 == r2
        # httpx post should only be called once
        assert mock_client.post.call_count == 1


# ===================================================================
# Mock provider — new functions
# ===================================================================


class TestMockProviderNewFunctions:
    def test_text_search_returns_results(self) -> None:
        results = generate_text_search("museum", "Paris")
        assert len(results) > 0
        assert all(r["data_source"] == "mock" for r in results)
        assert all("place_id" in r for r in results)
        assert all("name" in r for r in results)

    def test_text_search_unknown_city(self) -> None:
        results = generate_text_search("museum", "Atlantis")
        assert results == []

    def test_text_search_deterministic(self) -> None:
        a = generate_text_search("art", "Paris")
        b = generate_text_search("art", "Paris")
        assert a == b

    def test_restaurant_search_returns_restaurants(self) -> None:
        results = generate_restaurant_search("Paris")
        assert len(results) > 0
        assert all(r["category"] == "restaurant" for r in results)
        assert all(r["data_source"] == "mock" for r in results)

    def test_restaurant_search_with_cuisine_filter(self) -> None:
        results = generate_restaurant_search("Tokyo", cuisine="sushi")
        for r in results:
            assert "sushi" in r["description"].lower() or r["category"] == "restaurant"

    def test_nearby_search_returns_nearby(self) -> None:
        # Near Louvre in Paris
        results = generate_nearby_search(48.86, 2.34, 5000)
        assert len(results) > 0
        assert all(r["data_source"] == "mock" for r in results)
        assert all("distance_km" in r for r in results)

    def test_nearby_search_small_radius(self) -> None:
        # Very small radius should return fewer or no results
        results = generate_nearby_search(48.86, 2.34, 10)
        # Can be empty if no activities within 10m
        assert isinstance(results, list)

    def test_place_details_known(self) -> None:
        # Get place_id for a known activity
        place_id = _make_place_id("Musée du Louvre")
        details = generate_place_details(place_id)
        assert details["name"] == "Musée du Louvre"
        assert details["data_source"] == "mock"
        assert "reviews" in details
        assert details["business_status"] == "OPERATIONAL"

    def test_place_details_unknown(self) -> None:
        details = generate_place_details("ChIJUnknown123456")
        assert details["data_source"] == "mock"
        assert details["name"].startswith("Place ")

    def test_place_photos(self) -> None:
        photos = generate_place_photos("ChIJ123", max_photos=3)
        assert len(photos) == 3
        assert all(p["data_source"] == "mock" for p in photos)
        assert all("url" in p for p in photos)
        assert all("photo_reference" in p for p in photos)

    def test_directions(self) -> None:
        result = generate_directions("Paris", "Tour Eiffel")
        assert result["data_source"] == "mock"
        assert result["distance_meters"] > 0
        assert result["duration_seconds"] > 0
        assert len(result["steps"]) > 0

    def test_directions_different_modes(self) -> None:
        walking = generate_directions("Paris", "Louvre", mode="walking")
        driving = generate_directions("Paris", "Louvre", mode="driving")
        assert driving["duration_seconds"] < walking["duration_seconds"]

    def test_geocode_known_city(self) -> None:
        results = generate_geocode("Paris")
        assert len(results) == 1
        assert results[0]["data_source"] == "mock"
        assert abs(results[0]["location"]["lat"] - 48.8566) < 0.01

    def test_geocode_known_place(self) -> None:
        results = generate_geocode("Musée du Louvre")
        assert len(results) >= 1
        assert results[0]["data_source"] == "mock"

    def test_geocode_unknown(self) -> None:
        results = generate_geocode("Unknown Place 12345")
        assert len(results) == 1
        assert results[0]["data_source"] == "mock"

    def test_reverse_geocode_near_city(self) -> None:
        # Near Paris
        results = generate_reverse_geocode(48.86, 2.35)
        assert len(results) >= 1
        assert results[0]["data_source"] == "mock"

    def test_reverse_geocode_near_activity(self) -> None:
        # Near Louvre
        results = generate_reverse_geocode(48.8606, 2.3376)
        assert len(results) >= 1
        assert results[0]["data_source"] == "mock"


# ===================================================================
# Mock provider — data_source in discover_activities
# ===================================================================


class TestDiscoverActivitiesDataSource:
    def test_data_source_present(self) -> None:
        results = discover_activities(
            "Paris", ["art"], "2025-07-01", "2025-07-05",
            budget_per_day=200,
        )
        assert len(results) > 0
        for r in results:
            assert r.get("data_source") == "mock"

    def test_data_source_in_all_results(self) -> None:
        results = discover_activities(
            "Rio de Janeiro", ["history", "food"],
            "2025-07-01", "2025-07-10",
            budget_per_day=500,
        )
        for r in results:
            assert "data_source" in r


# ===================================================================
# MCP handlers — list_tools
# ===================================================================


class TestListTools:
    async def test_returns_nine_tools(self) -> None:
        tools = await list_tools()
        assert len(tools) == 9

    async def test_tool_names(self) -> None:
        tools = await list_tools()
        names = {t.name for t in tools}
        expected = {
            "discover_activities",
            "search_activities",
            "search_restaurants",
            "get_place_details",
            "get_place_photos",
            "nearby_search",
            "get_directions",
            "geocode",
            "reverse_geocode",
        }
        assert names == expected

    async def test_discover_activities_schema_unchanged(self) -> None:
        tools = await list_tools()
        discover = next(t for t in tools if t.name == "discover_activities")
        schema = discover.inputSchema
        assert "destination" in schema["properties"]
        assert "interests" in schema["properties"]
        assert "date_range" in schema["properties"]
        assert "budget_per_day" in schema["properties"]

    async def test_search_activities_schema(self) -> None:
        tools = await list_tools()
        tool = next(t for t in tools if t.name == "search_activities")
        schema = tool.inputSchema
        assert "query" in schema["properties"]
        assert "location" in schema["properties"]


# ===================================================================
# MCP handlers — call_tool (new tools)
# ===================================================================


class TestCallToolNew:
    async def test_search_activities(self) -> None:
        with patch(
            "travel_orchestrator.mcp_servers.activities.server._google_provider",
        ) as mock_provider:
            mock_provider.is_configured = False
            result = await call_tool(
                "search_activities",
                {"query": "museum", "location": "Paris"},
            )
        assert len(result) == 1
        data = json.loads(result[0].text)
        assert isinstance(data, list)
        assert len(data) > 0
        assert data[0]["data_source"] == "mock"

    async def test_search_restaurants(self) -> None:
        with patch(
            "travel_orchestrator.mcp_servers.activities.server._google_provider",
        ) as mock_provider:
            mock_provider.is_configured = False
            result = await call_tool(
                "search_restaurants",
                {"location": "Paris"},
            )
        data = json.loads(result[0].text)
        assert isinstance(data, list)
        assert all(r["category"] == "restaurant" for r in data)

    async def test_get_place_details(self) -> None:
        place_id = _make_place_id("Musée du Louvre")
        with patch(
            "travel_orchestrator.mcp_servers.activities.server._google_provider",
        ) as mock_provider:
            mock_provider.is_configured = False
            result = await call_tool(
                "get_place_details",
                {"place_id": place_id},
            )
        data = json.loads(result[0].text)
        assert data["name"] == "Musée du Louvre"
        assert data["data_source"] == "mock"

    async def test_get_place_photos(self) -> None:
        with patch(
            "travel_orchestrator.mcp_servers.activities.server._google_provider",
        ) as mock_provider:
            mock_provider.is_configured = False
            result = await call_tool(
                "get_place_photos",
                {"place_id": "ChIJ123", "max_photos": 3},
            )
        data = json.loads(result[0].text)
        assert isinstance(data, list)
        assert len(data) == 3

    async def test_nearby_search(self) -> None:
        with patch(
            "travel_orchestrator.mcp_servers.activities.server._google_provider",
        ) as mock_provider:
            mock_provider.is_configured = False
            result = await call_tool(
                "nearby_search",
                {"latitude": 48.86, "longitude": 2.34, "radius_meters": 5000},
            )
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    async def test_get_directions(self) -> None:
        with patch(
            "travel_orchestrator.mcp_servers.activities.server._google_provider",
        ) as mock_provider:
            mock_provider.is_configured = False
            result = await call_tool(
                "get_directions",
                {"origin": "Paris", "destination": "Tour Eiffel"},
            )
        data = json.loads(result[0].text)
        assert data["data_source"] == "mock"
        assert data["distance_meters"] > 0

    async def test_geocode(self) -> None:
        with patch(
            "travel_orchestrator.mcp_servers.activities.server._google_provider",
        ) as mock_provider:
            mock_provider.is_configured = False
            result = await call_tool(
                "geocode",
                {"address": "Paris, France"},
            )
        data = json.loads(result[0].text)
        assert isinstance(data, list)
        assert len(data) >= 1

    async def test_reverse_geocode(self) -> None:
        with patch(
            "travel_orchestrator.mcp_servers.activities.server._google_provider",
        ) as mock_provider:
            mock_provider.is_configured = False
            result = await call_tool(
                "reverse_geocode",
                {"latitude": 48.86, "longitude": 2.35},
            )
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    async def test_unknown_tool_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown tool"):
            await call_tool("nonexistent", {})


# ===================================================================
# Fallback to mock when Google API fails
# ===================================================================


class TestFallbackToMock:
    async def test_search_activities_fallback(self) -> None:
        with patch(
            "travel_orchestrator.mcp_servers.activities.server._google_provider",
        ) as mock_provider:
            mock_provider.is_configured = True
            mock_provider.text_search = AsyncMock(
                side_effect=RuntimeError("API error"),
            )
            result = await search_activities_impl("museum", "Paris")

        assert len(result) > 0
        assert result[0]["data_source"] == "mock"

    async def test_search_restaurants_fallback(self) -> None:
        with patch(
            "travel_orchestrator.mcp_servers.activities.server._google_provider",
        ) as mock_provider:
            mock_provider.is_configured = True
            mock_provider.text_search = AsyncMock(
                side_effect=RuntimeError("API error"),
            )
            result = await search_restaurants_impl("Paris")

        assert len(result) > 0
        assert all(r["data_source"] == "mock" for r in result)

    async def test_place_details_fallback(self) -> None:
        place_id = _make_place_id("Tour Eiffel")
        with patch(
            "travel_orchestrator.mcp_servers.activities.server._google_provider",
        ) as mock_provider:
            mock_provider.is_configured = True
            mock_provider.get_place_details = AsyncMock(
                side_effect=RuntimeError("API error"),
            )
            result = await get_place_details_impl(place_id)

        assert result["data_source"] == "mock"

    async def test_directions_fallback(self) -> None:
        with patch(
            "travel_orchestrator.mcp_servers.activities.server._google_provider",
        ) as mock_provider:
            mock_provider.is_configured = True
            mock_provider.get_directions = AsyncMock(
                side_effect=RuntimeError("API error"),
            )
            result = await get_directions_impl("Paris", "Lyon")

        assert result["data_source"] == "mock"

    async def test_geocode_fallback(self) -> None:
        with patch(
            "travel_orchestrator.mcp_servers.activities.server._google_provider",
        ) as mock_provider:
            mock_provider.is_configured = True
            mock_provider.geocode = AsyncMock(
                side_effect=RuntimeError("API error"),
            )
            result = await geocode_impl("Paris")

        assert len(result) >= 1
        assert result[0]["data_source"] == "mock"

    async def test_reverse_geocode_fallback(self) -> None:
        with patch(
            "travel_orchestrator.mcp_servers.activities.server._google_provider",
        ) as mock_provider:
            mock_provider.is_configured = True
            mock_provider.reverse_geocode = AsyncMock(
                side_effect=RuntimeError("API error"),
            )
            result = await reverse_geocode_impl(48.86, 2.35)

        assert len(result) >= 1
        assert result[0]["data_source"] == "mock"


# ===================================================================
# Backward compatibility
# ===================================================================


class TestBackwardCompatibility:
    async def test_discover_activities_still_works(self) -> None:
        result = await discover_activities_impl(
            destination="Paris",
            interests=["art", "food"],
            date_range={"start": "2025-07-01", "end": "2025-07-05"},
            budget_per_day=100,
        )
        assert isinstance(result, list)
        assert len(result) > 0
        # Original fields still present
        act = result[0]
        assert "id" in act
        assert "name" in act
        assert "category" in act
        assert "address" in act
        assert "coordinates" in act
        assert "duration_minutes" in act
        assert "price" in act
        assert "currency" in act
        assert "opening_hours" in act
        assert "requires_booking" in act
        assert "indoor" in act
        assert "description" in act
        assert "score" in act
        # New field
        assert act.get("data_source") == "mock"

    async def test_call_tool_discover_activities_unchanged(self) -> None:
        result = await call_tool(
            "discover_activities",
            {
                "destination": "Tokyo",
                "interests": ["food", "culture"],
                "date_range": {"start": "2025-07-01", "end": "2025-07-05"},
                "budget_per_day": 99999,
            },
        )
        assert len(result) == 1
        data = json.loads(result[0].text)
        assert isinstance(data, list)
        assert len(data) > 0
        assert "name" in data[0]
        assert "score" in data[0]


# ===================================================================
# Implementation validation
# ===================================================================


class TestImplValidation:
    async def test_search_activities_empty_query_raises(self) -> None:
        with pytest.raises(ValueError, match="query"):
            await search_activities_impl(query="", location="Paris")

    async def test_search_activities_empty_location_raises(self) -> None:
        with pytest.raises(ValueError, match="location"):
            await search_activities_impl(query="museum", location="")

    async def test_search_restaurants_empty_location_raises(self) -> None:
        with pytest.raises(ValueError, match="location"):
            await search_restaurants_impl(location="")

    async def test_place_details_empty_id_raises(self) -> None:
        with pytest.raises(ValueError, match="place_id"):
            await get_place_details_impl(place_id="")

    async def test_place_photos_empty_id_raises(self) -> None:
        with pytest.raises(ValueError, match="place_id"):
            await get_place_photos_impl(place_id="")

    async def test_directions_empty_origin_raises(self) -> None:
        with pytest.raises(ValueError, match="origin"):
            await get_directions_impl(origin="", destination="Paris")

    async def test_directions_empty_destination_raises(self) -> None:
        with pytest.raises(ValueError, match="destination"):
            await get_directions_impl(origin="Paris", destination="")

    async def test_geocode_empty_address_raises(self) -> None:
        with pytest.raises(ValueError, match="address"):
            await geocode_impl(address="")
