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
    _get_weather_alerts_impl,
    _get_weather_forecast_impl,
)
from travel_orchestrator.utils.logging import get_logger

logger = get_logger(__name__)


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
