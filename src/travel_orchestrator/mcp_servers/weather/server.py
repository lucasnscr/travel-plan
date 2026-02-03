"""MCP tool server for weather forecasts.

Exposes two tools — ``get_weather_forecast`` and ``get_weather_alerts``
— via the Model Context Protocol.  When an OpenWeatherMap API key is
configured the server fetches live data; otherwise it falls back to
a deterministic mock provider.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from travel_orchestrator.mcp_servers.weather.mock_provider import (
    generate_alerts,
    generate_forecast,
)
from travel_orchestrator.utils.logging import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# MCP server instance
# ---------------------------------------------------------------------------

app = Server("weather-server")


def _try_get_owm_key() -> str | None:
    """Return the OpenWeatherMap key from settings, or None."""
    try:
        from travel_orchestrator.config.settings import get_settings

        key = getattr(get_settings(), "openweathermap_api_key", None)
        return key if key else None
    except Exception:  # noqa: BLE001
        return None


# ---------------------------------------------------------------------------
# Live provider (OpenWeatherMap)
# ---------------------------------------------------------------------------


async def _fetch_live_forecast(
    destination: str,
    start_date: str,
    end_date: str,
    api_key: str,
) -> list[dict[str, Any]]:
    """Fetch forecast from OpenWeatherMap Geocoding + One Call API.

    This is a simplified implementation that geocodes the destination
    and queries the 8-day forecast endpoint.
    """
    import datetime

    import httpx

    async with httpx.AsyncClient(timeout=10) as client:
        # 1. Geocode destination → lat/lon
        geo_resp = await client.get(
            "https://api.openweathermap.org/geo/1.0/direct",
            params={"q": destination, "limit": 1, "appid": api_key},
        )
        geo_resp.raise_for_status()
        geo_data = geo_resp.json()
        if not geo_data:
            logger.warning("geocoding_empty", destination=destination)
            return _fallback_to_mock(destination, start_date, end_date)

        lat, lon = geo_data[0]["lat"], geo_data[0]["lon"]

        # 2. Get forecast (One Call 3.0 — 8-day daily)
        forecast_resp = await client.get(
            "https://api.openweathermap.org/data/3.0/onecall",
            params={
                "lat": lat,
                "lon": lon,
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
            results.append(
                {
                    "date": dt.isoformat(),
                    "condition": day["weather"][0]["main"].lower(),
                    "temp_max": round(day["temp"]["max"], 1),
                    "temp_min": round(day["temp"]["min"], 1),
                    "rain_chance": round(rain_pop, 0),
                    "rain_start": None,
                    "wind_speed": round(day.get("wind_speed", 0) * 3.6, 1),
                }
            )

    return results


def _fallback_to_mock(
    destination: str,
    start_date: str,
    end_date: str,
) -> list[dict[str, Any]]:
    """Convert mock WeatherForecast TypedDicts to plain dicts."""
    return [dict(f) for f in generate_forecast(destination, start_date, end_date)]


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------


async def _get_weather_forecast_impl(
    destination: str,
    start_date: str,
    end_date: str,
) -> list[dict[str, Any]]:
    """Core implementation dispatching to live or mock provider."""
    api_key = _try_get_owm_key()

    if api_key:
        logger.info("using_live_provider", destination=destination)
        try:
            return await _fetch_live_forecast(destination, start_date, end_date, api_key)
        except Exception:
            logger.exception("live_provider_failed_falling_back_to_mock")
            return _fallback_to_mock(destination, start_date, end_date)

    logger.info("using_mock_provider", destination=destination)
    return _fallback_to_mock(destination, start_date, end_date)


async def _get_weather_alerts_impl(
    destination: str,
) -> list[dict[str, str]]:
    """Return weather alerts (always mock for now)."""
    return generate_alerts(destination)


# ---------------------------------------------------------------------------
# MCP handlers
# ---------------------------------------------------------------------------


@app.list_tools()
async def list_tools() -> list[Tool]:
    """Advertise available weather tools."""
    return [
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
