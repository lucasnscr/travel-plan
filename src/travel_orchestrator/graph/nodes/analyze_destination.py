"""``analyze_destination`` graph node.

Second node in the travel-planning workflow.  Responsible for:

1. Fetching weather forecasts for the destination and travel dates.
2. Fetching weather alerts for the destination.
3. Gathering seasonal events that overlap with the travel dates.
4. Computing a weather summary for downstream nodes.
5. Producing travel advisories (mock for now).
6. Appending risk_flags for severe weather conditions.
7. Storing all intelligence in ``state["destination_analysis"]``.
"""

from __future__ import annotations

import datetime
from collections import Counter
from typing import Any

from travel_orchestrator.mcp_servers.activities.mock_provider import (
    get_seasonal_events,
)
from travel_orchestrator.mcp_servers.weather.client import (
    get_weather_alerts,
    get_weather_forecast,
)
from travel_orchestrator.state.models import TravelPlannerCore, WeatherSummary
from travel_orchestrator.utils.logging import get_logger, log_node_execution

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Thresholds (aligned with weather_validator.py)
# ---------------------------------------------------------------------------

_HIGH_RAIN_CHANCE = 60.0  # percentage
_DANGEROUS_WIND_SPEED = 50.0  # km/h
_EXTREME_HEAT = 38.0  # Celsius
_EXTREME_COLD = 0.0  # Celsius

_SEVERE_CONDITIONS = frozenset(
    {"thunderstorm", "storm", "blizzard", "hurricane", "typhoon"}
)


@log_node_execution("analyze_destination")
async def analyze_destination_node(
    state: TravelPlannerCore,
) -> TravelPlannerCore:
    """Research destination: weather, local events, safety advisories."""

    destination = state["destination"]
    dates = state["dates"]
    start_date = dates["start_date"]
    end_date = dates["end_date"]

    # -- 1. Fetch weather forecast (non-blocking) ----------------------------
    forecast: list[dict[str, Any]] = []
    try:
        forecast = await get_weather_forecast(destination, start_date, end_date)
        logger.info(
            "weather_forecast_fetched",
            destination=destination,
            days=len(forecast),
        )
    except Exception as exc:
        logger.warning("weather_forecast_failed", error=str(exc))

    # -- 2. Fetch weather alerts (non-blocking) ------------------------------
    alerts: list[dict[str, str]] = []
    try:
        alerts = await get_weather_alerts(destination)
        logger.info(
            "weather_alerts_fetched",
            destination=destination,
            count=len(alerts),
        )
    except Exception as exc:
        logger.warning("weather_alerts_failed", error=str(exc))

    # -- 3. Gather seasonal events (non-blocking) ---------------------------
    seasonal_events: list[dict[str, Any]] = []
    try:
        seasonal_events = get_seasonal_events(destination, start_date, end_date)
        logger.info(
            "seasonal_events_gathered",
            destination=destination,
            count=len(seasonal_events),
        )
    except Exception as exc:
        logger.warning("seasonal_events_failed", error=str(exc))

    # -- 4. Compute weather summary -----------------------------------------
    weather_summary = _compute_weather_summary(forecast)

    # -- 5. Produce travel advisories (mock) --------------------------------
    travel_advisories = _generate_advisories(
        weather_summary, alerts, seasonal_events
    )

    # -- 6. Compute risk flags from weather ---------------------------------
    new_risk_flags = _compute_risk_flags(forecast, alerts)
    existing_flags = list(state.get("risk_flags", []))
    combined_flags = existing_flags + new_risk_flags

    # -- 7. Build DestinationAnalysis and return ----------------------------
    analysis: dict[str, Any] = {
        "forecast": forecast,
        "alerts": alerts,
        "weather_summary": weather_summary,
        "seasonal_events": seasonal_events,
        "travel_advisories": travel_advisories,
        "analysis_timestamp": datetime.datetime.now(
            datetime.timezone.utc
        ).isoformat(),
    }

    logger.info(
        "destination_analysis_complete",
        destination=destination,
        forecast_days=len(forecast),
        alerts_count=len(alerts),
        events_count=len(seasonal_events),
        advisories_count=len(travel_advisories),
        risk_flags_added=len(new_risk_flags),
    )

    return {
        **state,
        "destination_analysis": analysis,
        "risk_flags": combined_flags,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _compute_weather_summary(
    forecast: list[dict[str, Any]],
) -> WeatherSummary:
    """Aggregate daily forecasts into a single weather summary."""
    if not forecast:
        return {
            "avg_temp_max": 0.0,
            "avg_temp_min": 0.0,
            "avg_rain_chance": 0.0,
            "dominant_condition": "unknown",
            "severe_weather_days": 0,
            "packing_suggestions": [],
        }

    n = len(forecast)
    avg_temp_max = round(sum(f["temp_max"] for f in forecast) / n, 1)
    avg_temp_min = round(sum(f["temp_min"] for f in forecast) / n, 1)
    avg_rain_chance = round(sum(f["rain_chance"] for f in forecast) / n, 1)

    conditions = Counter(f["condition"] for f in forecast)
    dominant_condition = conditions.most_common(1)[0][0]

    severe_weather_days = sum(
        1
        for f in forecast
        if f["condition"].lower() in _SEVERE_CONDITIONS
        or f["wind_speed"] >= _DANGEROUS_WIND_SPEED
    )

    packing_suggestions = _suggest_packing(
        avg_temp_max, avg_temp_min, avg_rain_chance
    )

    return {
        "avg_temp_max": avg_temp_max,
        "avg_temp_min": avg_temp_min,
        "avg_rain_chance": avg_rain_chance,
        "dominant_condition": dominant_condition,
        "severe_weather_days": severe_weather_days,
        "packing_suggestions": packing_suggestions,
    }


def _suggest_packing(
    avg_temp_max: float,
    avg_temp_min: float,
    avg_rain_chance: float,
) -> list[str]:
    """Derive packing suggestions from weather summary stats."""
    suggestions: list[str] = []
    if avg_rain_chance >= 40:
        suggestions.append("umbrella")
        suggestions.append("waterproof jacket")
    if avg_temp_max >= 28:
        suggestions.append("sunscreen")
        suggestions.append("light clothing")
    if avg_temp_min < 5:
        suggestions.append("warm layers")
        suggestions.append("thermal underwear")
    if avg_temp_max >= 20 and avg_temp_min >= 10:
        suggestions.append("comfortable walking shoes")
    if avg_temp_min < 15:
        suggestions.append("jacket")
    return suggestions


def _generate_advisories(
    summary: WeatherSummary,
    alerts: list[dict[str, str]],
    events: list[dict[str, Any]],
) -> list[str]:
    """Produce human-readable travel advisories."""
    advisories: list[str] = []

    # Weather-based advisories (skip when no forecast data)
    has_forecast = summary["dominant_condition"] != "unknown"
    if has_forecast and summary["severe_weather_days"] > 0:
        advisories.append(
            f"Severe weather expected on {summary['severe_weather_days']} day(s). "
            "Consider flexible bookings."
        )
    if has_forecast and summary["avg_rain_chance"] >= _HIGH_RAIN_CHANCE:
        advisories.append(
            "High average rain chance during your trip. "
            "Plan indoor alternatives for outdoor activities."
        )
    if has_forecast and summary["avg_temp_max"] >= _EXTREME_HEAT:
        advisories.append(
            "Extreme heat expected. Stay hydrated and avoid midday outdoor "
            "activities."
        )
    if has_forecast and summary["avg_temp_min"] <= _EXTREME_COLD:
        advisories.append(
            "Near-freezing temperatures expected. Pack warm clothing."
        )

    # Alert-based advisories
    for alert in alerts:
        advisories.append(
            f"Weather alert ({alert.get('severity', 'unknown')}): "
            f"{alert.get('message', '')}"
        )

    # Event-based advisories
    for event in events:
        advisories.append(
            f"Seasonal event: {event['name']} — {event['description']}. "
            "Book accommodations early and expect crowds."
        )

    return advisories


def _compute_risk_flags(
    forecast: list[dict[str, Any]],
    alerts: list[dict[str, str]],
) -> list[str]:
    """Derive risk flags from weather data for downstream routing."""
    flags: list[str] = []

    # Alert-based flags
    for alert in alerts:
        severity = alert.get("severity", "")
        alert_type = alert.get("type", "unknown")
        if severity in ("warning", "watch"):
            flags.append(f"weather:severe_alert:{alert_type}")

    if not forecast:
        return flags

    # Forecast-based flags
    any_extreme_temp = any(
        f["temp_max"] >= _EXTREME_HEAT or f["temp_min"] <= _EXTREME_COLD
        for f in forecast
    )
    if any_extreme_temp:
        flags.append("weather:extreme_temperature")

    avg_rain = sum(f["rain_chance"] for f in forecast) / len(forecast)
    if avg_rain >= _HIGH_RAIN_CHANCE:
        flags.append("weather:high_rain")

    any_dangerous_wind = any(
        f["wind_speed"] >= _DANGEROUS_WIND_SPEED for f in forecast
    )
    if any_dangerous_wind:
        flags.append("weather:dangerous_wind")

    return flags
