"""Tests for the Open-Meteo weather provider, cache, weather codes, and new MCP tools.

All API calls are mocked — no real network requests are made.
"""

from __future__ import annotations

import json
import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from travel_orchestrator.mcp_servers.weather.cache import TTLCache
from travel_orchestrator.mcp_servers.weather.open_meteo_provider import (
    OpenMeteoProvider,
    _aqi_category,
)
from travel_orchestrator.mcp_servers.weather.weather_codes import (
    WMO_CODES,
    code_to_condition,
    code_to_description,
    code_to_icon,
    is_rainy,
)

from tests.unit.mcp_servers.fixtures.open_meteo_responses import (
    AIR_QUALITY_RESPONSE,
    CURRENT_WEATHER_RESPONSE,
    FORECAST_RESPONSE,
    GEOCODING_EMPTY_RESPONSE,
    GEOCODING_RESPONSE,
    HOURLY_RESPONSE,
)


# ===================================================================
# Weather Codes
# ===================================================================


class TestWeatherCodes:
    def test_clear_sky_code(self) -> None:
        assert code_to_condition(0) == "sunny"

    def test_rain_codes(self) -> None:
        for code in (61, 63, 65, 80, 81, 82):
            assert code_to_condition(code) == "rain"

    def test_thunderstorm_codes(self) -> None:
        for code in (95, 96, 99):
            assert code_to_condition(code) == "thunderstorm"

    def test_snow_codes(self) -> None:
        for code in (71, 73, 75, 77, 85, 86):
            assert code_to_condition(code) == "snow"

    def test_unknown_code_returns_unknown(self) -> None:
        assert code_to_condition(999) == "unknown"

    def test_description_english(self) -> None:
        assert code_to_description(0) == "Clear sky"

    def test_description_portuguese(self) -> None:
        assert code_to_description(0, lang="pt") == "Ceu limpo"

    def test_description_unknown_lang_falls_back_to_en(self) -> None:
        desc = code_to_description(0, lang="xx")
        assert desc == "Clear sky"

    def test_icon_returns_emoji(self) -> None:
        icon = code_to_icon(0)
        assert icon == "☀️"

    def test_icon_for_thunderstorm(self) -> None:
        assert code_to_icon(95) == "⛈️"

    def test_is_rainy_true(self) -> None:
        assert is_rainy(61) is True
        assert is_rainy(95) is True  # thunderstorm

    def test_is_rainy_false(self) -> None:
        assert is_rainy(0) is False
        assert is_rainy(3) is False  # overcast

    def test_all_codes_have_required_keys(self) -> None:
        for code, entry in WMO_CODES.items():
            assert "condition" in entry, f"Code {code} missing 'condition'"
            assert "description_en" in entry, f"Code {code} missing 'description_en'"
            assert "description_pt" in entry, f"Code {code} missing 'description_pt'"
            assert "icon" in entry, f"Code {code} missing 'icon'"


# ===================================================================
# TTL Cache
# ===================================================================


class TestTTLCache:
    def test_set_and_get(self) -> None:
        cache = TTLCache(default_ttl_seconds=60)
        cache.set("key1", {"data": "value"})
        assert cache.get("key1") == {"data": "value"}

    def test_get_missing_returns_none(self) -> None:
        cache = TTLCache()
        assert cache.get("nonexistent") is None

    def test_expired_entry_returns_none(self) -> None:
        cache = TTLCache(default_ttl_seconds=0)
        cache.set("key1", "val", ttl=0)
        # monotonic time will have advanced
        time.sleep(0.01)
        assert cache.get("key1") is None

    def test_custom_ttl_per_entry(self) -> None:
        cache = TTLCache(default_ttl_seconds=0)
        cache.set("key1", "val", ttl=3600)
        assert cache.get("key1") == "val"

    def test_clear(self) -> None:
        cache = TTLCache()
        cache.set("a", 1)
        cache.set("b", 2)
        assert cache.size == 2
        cache.clear()
        assert cache.size == 0
        assert cache.get("a") is None

    def test_make_key_deterministic(self) -> None:
        k1 = TTLCache.make_key("forecast", 48.86, 2.35, 7)
        k2 = TTLCache.make_key("forecast", 48.86, 2.35, 7)
        assert k1 == k2

    def test_make_key_different_args(self) -> None:
        k1 = TTLCache.make_key("forecast", 48.86, 2.35)
        k2 = TTLCache.make_key("forecast", 35.68, 139.69)
        assert k1 != k2


# ===================================================================
# OpenMeteoProvider — Geocoding
# ===================================================================


def _mock_response(data: dict, status_code: int = 200) -> httpx.Response:
    """Build a mock httpx.Response."""
    return httpx.Response(
        status_code=status_code,
        json=data,
        request=httpx.Request("GET", "https://test"),
    )


class TestOpenMeteoGeocode:
    async def test_geocode_paris(self) -> None:
        provider = OpenMeteoProvider(cache=TTLCache())

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=_mock_response(GEOCODING_RESPONSE))

        with patch("httpx.AsyncClient", return_value=mock_client):
            lat, lon = await provider.geocode("Paris")

        assert lat == pytest.approx(48.8534)
        assert lon == pytest.approx(2.3488)

    async def test_geocode_unknown_raises(self) -> None:
        provider = OpenMeteoProvider(cache=TTLCache())

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=_mock_response(GEOCODING_EMPTY_RESPONSE))

        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(ValueError, match="Could not geocode"):
                await provider.geocode("Atlantis_XYZ_Nonexistent")

    async def test_geocode_caches_result(self) -> None:
        cache = TTLCache()
        provider = OpenMeteoProvider(cache=cache)

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=_mock_response(GEOCODING_RESPONSE))

        with patch("httpx.AsyncClient", return_value=mock_client):
            await provider.geocode("Paris")
            await provider.geocode("Paris")  # should be cached

        # Only one HTTP call
        assert mock_client.get.call_count == 1


# ===================================================================
# OpenMeteoProvider — Current Weather
# ===================================================================


class TestOpenMeteoCurrentWeather:
    async def test_current_weather(self) -> None:
        provider = OpenMeteoProvider(cache=TTLCache())

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=_mock_response(CURRENT_WEATHER_RESPONSE))

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await provider.get_current_weather(48.86, 2.34)

        assert result["temperature"] == 26.3
        assert result["humidity"] == 55
        assert result["condition"] == "partly_cloudy"
        assert result["data_source"] == "open_meteo"
        assert "icon" in result


# ===================================================================
# OpenMeteoProvider — Daily Forecast
# ===================================================================


class TestOpenMeteoForecast:
    async def test_forecast_returns_days(self) -> None:
        provider = OpenMeteoProvider(cache=TTLCache())

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=_mock_response(FORECAST_RESPONSE))

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await provider.get_forecast(48.86, 2.34, days=5)

        assert len(result) == 5
        assert result[0]["date"] == "2025-07-01"
        assert result[0]["temp_max"] == 28.5
        assert result[0]["temp_min"] == 18.2
        assert result[0]["condition"] == "sunny"
        assert result[0]["data_source"] == "open_meteo"

    async def test_forecast_rainy_day(self) -> None:
        provider = OpenMeteoProvider(cache=TTLCache())

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=_mock_response(FORECAST_RESPONSE))

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await provider.get_forecast(48.86, 2.34, days=5)

        # Day 3 (index 2) has weather_code 61 = rain
        assert result[2]["condition"] == "rain"
        assert result[2]["rain_chance"] == 75

    async def test_forecast_has_uv_and_wind(self) -> None:
        provider = OpenMeteoProvider(cache=TTLCache())

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=_mock_response(FORECAST_RESPONSE))

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await provider.get_forecast(48.86, 2.34, days=5)

        assert result[0]["uv_index"] == 8.5
        assert result[0]["wind_speed"] == 12.5


# ===================================================================
# OpenMeteoProvider — Hourly Forecast
# ===================================================================


class TestOpenMeteoHourly:
    async def test_hourly_returns_24_hours(self) -> None:
        provider = OpenMeteoProvider(cache=TTLCache())

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=_mock_response(HOURLY_RESPONSE))

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await provider.get_hourly_forecast(48.86, 2.34, "2025-07-01")

        assert len(result) == 24
        assert result[0]["hour"] == "00:00"
        assert result[13]["hour"] == "13:00"
        assert result[0]["data_source"] == "open_meteo"
        assert "temperature" in result[0]
        assert "condition" in result[0]


# ===================================================================
# OpenMeteoProvider — Air Quality
# ===================================================================


class TestOpenMeteoAirQuality:
    async def test_air_quality(self) -> None:
        provider = OpenMeteoProvider(cache=TTLCache())

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=_mock_response(AIR_QUALITY_RESPONSE))

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await provider.get_air_quality(48.86, 2.34)

        assert result["pm2_5"] == 8.5
        assert result["pm10"] == 15.2
        assert result["us_aqi"] == 35
        assert result["category"] == "good"
        assert result["data_source"] == "open_meteo"

    def test_aqi_categories(self) -> None:
        assert _aqi_category(25) == "good"
        assert _aqi_category(75) == "moderate"
        assert _aqi_category(125) == "unhealthy_for_sensitive"
        assert _aqi_category(175) == "unhealthy"
        assert _aqi_category(250) == "very_unhealthy"
        assert _aqi_category(350) == "hazardous"
        assert _aqi_category(None) == "unknown"


# ===================================================================
# OpenMeteoProvider — Backward-Compatible Destination Forecast
# ===================================================================


class TestBackwardCompatibility:
    async def test_destination_forecast_has_legacy_fields(self) -> None:
        """get_forecast_for_destination must return dicts compatible
        with the WeatherForecast TypedDict."""
        provider = OpenMeteoProvider(cache=TTLCache())

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        # First call = geocoding, second = forecast
        mock_client.get = AsyncMock(
            side_effect=[
                _mock_response(GEOCODING_RESPONSE),
                _mock_response(FORECAST_RESPONSE),
            ]
        )

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await provider.get_forecast_for_destination(
                "Paris", "2025-07-01", "2025-07-05"
            )

        assert len(result) == 5

        # Verify all WeatherForecast TypedDict fields are present
        required_fields = {
            "date", "condition", "temp_max", "temp_min",
            "rain_chance", "rain_start", "wind_speed",
        }
        for day in result:
            assert required_fields.issubset(day.keys()), (
                f"Missing fields: {required_fields - set(day.keys())}"
            )

        # Verify types
        assert isinstance(result[0]["temp_max"], float)
        assert isinstance(result[0]["temp_min"], float)
        assert isinstance(result[0]["rain_chance"], (int, float))
        assert isinstance(result[0]["wind_speed"], float)
        assert isinstance(result[0]["condition"], str)
        assert result[0]["data_source"] == "open_meteo"

    async def test_destination_forecast_rain_start_set_for_rainy_days(self) -> None:
        provider = OpenMeteoProvider(cache=TTLCache())

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        mock_client.get = AsyncMock(
            side_effect=[
                _mock_response(GEOCODING_RESPONSE),
                _mock_response(FORECAST_RESPONSE),
            ]
        )

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await provider.get_forecast_for_destination(
                "Paris", "2025-07-01", "2025-07-05"
            )

        # Day 3 has 75% rain chance → rain_start should be set
        rainy_day = result[2]
        assert rainy_day["rain_chance"] == 75
        assert rainy_day["rain_start"] is not None

        # Day 1 has 5% rain chance → rain_start should be None
        sunny_day = result[0]
        assert sunny_day["rain_chance"] == 5
        assert sunny_day["rain_start"] is None


# ===================================================================
# New MCP Tools — via server call_tool
# ===================================================================


class TestNewMCPTools:
    async def test_call_tool_get_current_weather(self) -> None:
        from travel_orchestrator.mcp_servers.weather.server import call_tool

        with patch(
            "travel_orchestrator.mcp_servers.weather.server._get_current_weather_impl",
            new_callable=AsyncMock,
            return_value={"temperature": 25.0, "condition": "sunny", "data_source": "mock"},
        ):
            result = await call_tool(
                "get_current_weather",
                {"latitude": 48.86, "longitude": 2.34},
            )

        assert len(result) == 1
        data = json.loads(result[0].text)
        assert data["temperature"] == 25.0

    async def test_call_tool_get_forecast(self) -> None:
        from travel_orchestrator.mcp_servers.weather.server import call_tool

        with patch(
            "travel_orchestrator.mcp_servers.weather.server._get_forecast_impl",
            new_callable=AsyncMock,
            return_value=[{"date": "2025-07-01", "condition": "sunny", "data_source": "mock"}],
        ):
            result = await call_tool(
                "get_forecast",
                {"latitude": 48.86, "longitude": 2.34, "days": 3},
            )

        data = json.loads(result[0].text)
        assert isinstance(data, list)
        assert data[0]["date"] == "2025-07-01"

    async def test_call_tool_get_hourly_forecast(self) -> None:
        from travel_orchestrator.mcp_servers.weather.server import call_tool

        with patch(
            "travel_orchestrator.mcp_servers.weather.server._get_hourly_forecast_impl",
            new_callable=AsyncMock,
            return_value=[{"hour": "00:00", "temperature": 18.0}],
        ):
            result = await call_tool(
                "get_hourly_forecast",
                {"latitude": 48.86, "longitude": 2.34, "date": "2025-07-01"},
            )

        data = json.loads(result[0].text)
        assert data[0]["hour"] == "00:00"

    async def test_call_tool_get_air_quality(self) -> None:
        from travel_orchestrator.mcp_servers.weather.server import call_tool

        with patch(
            "travel_orchestrator.mcp_servers.weather.server._get_air_quality_impl",
            new_callable=AsyncMock,
            return_value={"us_aqi": 42, "category": "good", "data_source": "mock"},
        ):
            result = await call_tool(
                "get_air_quality",
                {"latitude": 48.86, "longitude": 2.34},
            )

        data = json.loads(result[0].text)
        assert data["us_aqi"] == 42
        assert data["category"] == "good"


# ===================================================================
# Fallback to Mock
# ===================================================================


class TestFallbackToMock:
    async def test_forecast_falls_back_to_mock_on_error(self) -> None:
        """When Open-Meteo API fails, should fall back to mock data."""
        from travel_orchestrator.mcp_servers.weather.server import (
            _get_weather_forecast_impl,
        )

        with patch(
            "travel_orchestrator.mcp_servers.weather.server._provider",
        ) as mock_prov:
            mock_prov.get_forecast_for_destination = AsyncMock(
                side_effect=Exception("API down")
            )
            result = await _get_weather_forecast_impl(
                "Paris", "2025-07-01", "2025-07-03"
            )

        assert len(result) == 3
        assert all(r["data_source"] == "mock" for r in result)

    async def test_current_weather_falls_back_to_mock(self) -> None:
        from travel_orchestrator.mcp_servers.weather.server import (
            _get_current_weather_impl,
        )

        with patch(
            "travel_orchestrator.mcp_servers.weather.server._provider",
        ) as mock_prov:
            mock_prov.get_current_weather = AsyncMock(
                side_effect=Exception("API down")
            )
            result = await _get_current_weather_impl(48.86, 2.34)

        assert result["data_source"] == "mock"

    async def test_air_quality_falls_back_to_mock(self) -> None:
        from travel_orchestrator.mcp_servers.weather.server import (
            _get_air_quality_impl,
        )

        with patch(
            "travel_orchestrator.mcp_servers.weather.server._provider",
        ) as mock_prov:
            mock_prov.get_air_quality = AsyncMock(
                side_effect=Exception("API down")
            )
            result = await _get_air_quality_impl(48.86, 2.34)

        assert result["data_source"] == "mock"
        assert "us_aqi" in result
