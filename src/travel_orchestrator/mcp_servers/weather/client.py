"""Client helper for fetching weather data from the weather provider.

In the current architecture the weather server and the graph run in the
same process, so the client calls the server implementation functions
directly -- no MCP transport overhead.

When the system moves to a separate weather-server process, swap this
implementation for one that connects via ``streamablehttp_client``.
"""

from __future__ import annotations

from typing import Any

from travel_orchestrator.mcp_servers.weather.server import (
    _get_air_quality_impl,
    _get_current_weather_impl,
    _get_forecast_impl,
    _get_hourly_forecast_impl,
    _get_weather_alerts_impl,
    _get_weather_forecast_impl,
)
from travel_orchestrator.utils.logging import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Legacy client functions (backward-compatible)
# ---------------------------------------------------------------------------


async def get_weather_forecast(
    destination: str,
    start_date: str,
    end_date: str,
) -> list[dict[str, Any]]:
    """Return daily weather forecasts for *destination* over the date range.

    Dispatches to the live or mock provider depending on configuration.
    """
    logger.info(
        "fetching_weather_forecast",
        destination=destination,
        start_date=start_date,
        end_date=end_date,
    )
    return await _get_weather_forecast_impl(destination, start_date, end_date)


async def get_weather_alerts(destination: str) -> list[dict[str, str]]:
    """Return active severe weather alerts for *destination*."""
    logger.info("fetching_weather_alerts", destination=destination)
    return await _get_weather_alerts_impl(destination)


# ---------------------------------------------------------------------------
# New client functions (coordinate-based)
# ---------------------------------------------------------------------------


async def get_current_weather(
    latitude: float, longitude: float,
) -> dict[str, Any]:
    """Return current weather conditions at the given coordinates."""
    logger.info(
        "fetching_current_weather",
        latitude=latitude,
        longitude=longitude,
    )
    return await _get_current_weather_impl(latitude, longitude)


async def get_forecast(
    latitude: float,
    longitude: float,
    days: int = 7,
) -> list[dict[str, Any]]:
    """Return daily forecast at coordinates for *days* days."""
    logger.info(
        "fetching_forecast",
        latitude=latitude,
        longitude=longitude,
        days=days,
    )
    return await _get_forecast_impl(latitude, longitude, days=days)


async def get_hourly_forecast(
    latitude: float,
    longitude: float,
    date: str,
) -> list[dict[str, Any]]:
    """Return hour-by-hour forecast at coordinates for a specific date."""
    logger.info(
        "fetching_hourly_forecast",
        latitude=latitude,
        longitude=longitude,
        date=date,
    )
    return await _get_hourly_forecast_impl(latitude, longitude, date)


async def get_air_quality(
    latitude: float, longitude: float,
) -> dict[str, Any]:
    """Return current air quality index at coordinates."""
    logger.info(
        "fetching_air_quality",
        latitude=latitude,
        longitude=longitude,
    )
    return await _get_air_quality_impl(latitude, longitude)
