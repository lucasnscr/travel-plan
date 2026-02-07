"""MCP tool server for weather data.

Exposes six tools via the Model Context Protocol:

**Legacy (backward-compatible):**
- ``get_weather_forecast`` — daily forecast by destination name + date range
- ``get_weather_alerts`` — severe weather alerts by destination name

**New (coordinate-based):**
- ``get_current_weather`` — current conditions at lat/lon
- ``get_forecast`` — daily forecast at lat/lon for N days
- ``get_hourly_forecast`` — hour-by-hour forecast for one day
- ``get_air_quality`` — air quality index at lat/lon

Primary provider: **Open-Meteo** (free, no API key).
Fallback chain: Open-Meteo → OpenWeatherMap (if key set) → Mock.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from travel_orchestrator.mcp_servers.weather.cache import TTLCache
from travel_orchestrator.mcp_servers.weather.mock_provider import (
    generate_air_quality,
    generate_alerts,
    generate_current_weather,
    generate_forecast,
    generate_hourly_forecast,
)
from travel_orchestrator.mcp_servers.weather.open_meteo_provider import (
    OpenMeteoProvider,
)
from travel_orchestrator.utils.logging import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# MCP server instance
# ---------------------------------------------------------------------------

app = Server("weather-server")

# Shared cache and provider (module-level singletons)
_cache = TTLCache(default_ttl_seconds=1800)
_provider = OpenMeteoProvider(cache=_cache)


# ---------------------------------------------------------------------------
# Legacy OWM key check (kept for backward compat fallback chain)
# ---------------------------------------------------------------------------


def _try_get_owm_key() -> str | None:
    """Return the OpenWeatherMap key from settings, or None."""
    try:
        from travel_orchestrator.config.settings import get_settings

        key = getattr(get_settings(), "openweathermap_api_key", None)
        return key if key else None
    except Exception:  # noqa: BLE001
        return None


# ---------------------------------------------------------------------------
# Legacy OWM live provider (kept as middle fallback)
# ---------------------------------------------------------------------------


async def _fetch_live_forecast_owm(
    destination: str,
    start_date: str,
    end_date: str,
    api_key: str,
) -> list[dict[str, Any]]:
    """Fetch forecast from OpenWeatherMap (legacy fallback)."""
    import datetime

    import httpx

    async with httpx.AsyncClient(timeout=10) as client:
        geo_resp = await client.get(
            "https://api.openweathermap.org/geo/1.0/direct",
            params={"q": destination, "limit": 1, "appid": api_key},
        )
        geo_resp.raise_for_status()
        geo_data = geo_resp.json()
        if not geo_data:
            return _fallback_to_mock(destination, start_date, end_date)

        lat, lon = geo_data[0]["lat"], geo_data[0]["lon"]

        forecast_resp = await client.get(
            "https://api.openweathermap.org/data/3.0/onecall",
            params={
                "lat": lat, "lon": lon,
                "exclude": "minutely,hourly",
                "units": "metric",
                "appid": api_key,
            },
        )
        forecast_resp.raise_for_status()
        data = forecast_resp.json()

    start = datetime.date.fromisoformat(start_date)
    end = datetime.date.fromisoformat(end_date)

    results: list[dict[str, Any]] = []
    for day in data.get("daily", []):
        dt = datetime.date.fromtimestamp(day["dt"])
        if start <= dt <= end:
            rain_pop = day.get("pop", 0) * 100
            results.append({
                "date": dt.isoformat(),
                "condition": day["weather"][0]["main"].lower(),
                "temp_max": round(day["temp"]["max"], 1),
                "temp_min": round(day["temp"]["min"], 1),
                "rain_chance": round(rain_pop, 0),
                "rain_start": None,
                "wind_speed": round(day.get("wind_speed", 0) * 3.6, 1),
                "data_source": "openweathermap",
            })

    return results


def _fallback_to_mock(
    destination: str, start_date: str, end_date: str,
) -> list[dict[str, Any]]:
    """Convert mock WeatherForecast TypedDicts to plain dicts."""
    results = [dict(f) for f in generate_forecast(destination, start_date, end_date)]
    for r in results:
        r["data_source"] = "mock"
    return results


# ---------------------------------------------------------------------------
# Implementation functions — legacy tools
# ---------------------------------------------------------------------------


async def _get_weather_forecast_impl(
    destination: str,
    start_date: str,
    end_date: str,
) -> list[dict[str, Any]]:
    """Core implementation: Open-Meteo → OWM → mock fallback chain."""
    # 1. Try Open-Meteo (primary — no key required)
    try:
        result = await _provider.get_forecast_for_destination(
            destination, start_date, end_date,
        )
        if result:
            logger.info("using_open_meteo_provider", destination=destination)
            return result
    except Exception:
        logger.exception("open_meteo_provider_failed")

    # 2. Try OpenWeatherMap (if key configured)
    api_key = _try_get_owm_key()
    if api_key:
        logger.info("trying_owm_fallback", destination=destination)
        try:
            return await _fetch_live_forecast_owm(
                destination, start_date, end_date, api_key,
            )
        except Exception:
            logger.exception("owm_fallback_failed")

    # 3. Mock fallback
    logger.info("using_mock_provider", destination=destination)
    return _fallback_to_mock(destination, start_date, end_date)


async def _get_weather_alerts_impl(
    destination: str,
) -> list[dict[str, str]]:
    """Return weather alerts (mock — Open-Meteo doesn't provide alerts)."""
    return generate_alerts(destination)


# ---------------------------------------------------------------------------
# Implementation functions — new tools
# ---------------------------------------------------------------------------


async def _get_current_weather_impl(
    latitude: float, longitude: float,
) -> dict[str, Any]:
    """Get current weather at coordinates."""
    try:
        return await _provider.get_current_weather(latitude, longitude)
    except Exception:
        logger.exception("current_weather_failed_using_mock")
        return generate_current_weather(latitude, longitude)


async def _get_forecast_impl(
    latitude: float, longitude: float, days: int = 7,
) -> list[dict[str, Any]]:
    """Get daily forecast at coordinates."""
    try:
        return await _provider.get_forecast(latitude, longitude, days=days)
    except Exception:
        logger.exception("forecast_failed_using_mock")
        # Generate mock using a synthetic destination name
        import datetime
        today = datetime.date.today()
        end = today + datetime.timedelta(days=days - 1)
        results = _fallback_to_mock(
            f"{latitude:.2f},{longitude:.2f}",
            today.isoformat(),
            end.isoformat(),
        )
        return results


async def _get_hourly_forecast_impl(
    latitude: float, longitude: float, date: str,
) -> list[dict[str, Any]]:
    """Get hourly forecast at coordinates for a specific date."""
    try:
        return await _provider.get_hourly_forecast(latitude, longitude, date)
    except Exception:
        logger.exception("hourly_forecast_failed_using_mock")
        return generate_hourly_forecast(latitude, longitude, date)


async def _get_air_quality_impl(
    latitude: float, longitude: float,
) -> dict[str, Any]:
    """Get air quality at coordinates."""
    try:
        return await _provider.get_air_quality(latitude, longitude)
    except Exception:
        logger.exception("air_quality_failed_using_mock")
        return generate_air_quality(latitude, longitude)


# ---------------------------------------------------------------------------
# MCP handlers
# ---------------------------------------------------------------------------


@app.list_tools()
async def list_tools() -> list[Tool]:
    """Advertise available weather tools."""
    return [
        # --- Legacy tools (backward-compatible) ---
        Tool(
            name="get_weather_forecast",
            description=(
                "Get a daily weather forecast for a destination over a date range. "
                "Returns temperature, rain chance, wind speed, and condition per day."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "destination": {
                        "type": "string",
                        "description": "City name (e.g. 'Paris', 'Tokyo')",
                    },
                    "start_date": {
                        "type": "string",
                        "format": "date",
                        "description": "Start date in ISO 8601 format (YYYY-MM-DD)",
                    },
                    "end_date": {
                        "type": "string",
                        "format": "date",
                        "description": "End date in ISO 8601 format (YYYY-MM-DD), inclusive",
                    },
                },
                "required": ["destination", "start_date", "end_date"],
            },
        ),
        Tool(
            name="get_weather_alerts",
            description=(
                "Get active severe weather alerts for a destination. "
                "Returns alert type, severity, and description."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "destination": {
                        "type": "string",
                        "description": "City name (e.g. 'Paris', 'Tokyo')",
                    },
                },
                "required": ["destination"],
            },
        ),
        # --- New tools ---
        Tool(
            name="get_current_weather",
            description=(
                "Get current weather conditions at a geographic coordinate. "
                "Returns temperature, humidity, wind, condition, and icon."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "latitude": {
                        "type": "number",
                        "description": "Latitude (-90 to 90)",
                    },
                    "longitude": {
                        "type": "number",
                        "description": "Longitude (-180 to 180)",
                    },
                },
                "required": ["latitude", "longitude"],
            },
        ),
        Tool(
            name="get_forecast",
            description=(
                "Get daily weather forecast at coordinates for up to 16 days. "
                "Returns max/min temperature, precipitation, UV index, and wind."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "latitude": {
                        "type": "number",
                        "description": "Latitude (-90 to 90)",
                    },
                    "longitude": {
                        "type": "number",
                        "description": "Longitude (-180 to 180)",
                    },
                    "days": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 16,
                        "default": 7,
                        "description": "Number of forecast days (1-16)",
                    },
                },
                "required": ["latitude", "longitude"],
            },
        ),
        Tool(
            name="get_hourly_forecast",
            description=(
                "Get hour-by-hour weather forecast for a specific date at "
                "coordinates. Useful for planning daily activities."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "latitude": {
                        "type": "number",
                        "description": "Latitude (-90 to 90)",
                    },
                    "longitude": {
                        "type": "number",
                        "description": "Longitude (-180 to 180)",
                    },
                    "date": {
                        "type": "string",
                        "format": "date",
                        "description": "Date in ISO 8601 format (YYYY-MM-DD)",
                    },
                },
                "required": ["latitude", "longitude", "date"],
            },
        ),
        Tool(
            name="get_air_quality",
            description=(
                "Get current air quality index at coordinates. "
                "Returns PM2.5, PM10, US AQI, and health category."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "latitude": {
                        "type": "number",
                        "description": "Latitude (-90 to 90)",
                    },
                    "longitude": {
                        "type": "number",
                        "description": "Longitude (-180 to 180)",
                    },
                },
                "required": ["latitude", "longitude"],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Dispatch tool call to the appropriate implementation."""
    if name == "get_weather_forecast":
        result = await _get_weather_forecast_impl(
            destination=arguments["destination"],
            start_date=arguments["start_date"],
            end_date=arguments["end_date"],
        )
        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False))]

    if name == "get_weather_alerts":
        result = await _get_weather_alerts_impl(
            destination=arguments["destination"],
        )
        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False))]

    if name == "get_current_weather":
        result = await _get_current_weather_impl(
            latitude=float(arguments["latitude"]),
            longitude=float(arguments["longitude"]),
        )
        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False))]

    if name == "get_forecast":
        result = await _get_forecast_impl(
            latitude=float(arguments["latitude"]),
            longitude=float(arguments["longitude"]),
            days=int(arguments.get("days", 7)),
        )
        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False))]

    if name == "get_hourly_forecast":
        result = await _get_hourly_forecast_impl(
            latitude=float(arguments["latitude"]),
            longitude=float(arguments["longitude"]),
            date=arguments["date"],
        )
        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False))]

    if name == "get_air_quality":
        result = await _get_air_quality_impl(
            latitude=float(arguments["latitude"]),
            longitude=float(arguments["longitude"]),
        )
        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False))]

    raise ValueError(f"Unknown tool: {name}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


async def run_server() -> None:
    """Start the MCP server over stdio transport."""
    logger.info("weather_server_starting")
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options(),
        )


def main() -> None:
    """CLI entry point."""
    asyncio.run(run_server())


if __name__ == "__main__":
    main()
