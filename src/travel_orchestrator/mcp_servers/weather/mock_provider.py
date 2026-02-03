"""Deterministic mock weather provider.

Generates realistic forecasts based on destination coordinates, month,
and a seeded RNG so that identical inputs always produce identical
outputs — useful for testing and offline development.
"""

from __future__ import annotations

import datetime
import hashlib
import random

from travel_orchestrator.state.models import WeatherForecast

# ---------------------------------------------------------------------------
# Destination → approximate coordinates lookup.
# Extend as needed; unknown cities fall back to temperate defaults.
# ---------------------------------------------------------------------------

_CITY_COORDS: dict[str, tuple[float, float]] = {
    "tokyo": (35.68, 139.69),
    "paris": (48.86, 2.35),
    "london": (51.51, -0.13),
    "new york": (40.71, -74.01),
    "rio de janeiro": (-22.91, -43.17),
    "sydney": (-33.87, 151.21),
    "cape town": (-33.93, 18.42),
    "dubai": (25.20, 55.27),
    "bangkok": (13.76, 100.50),
    "reykjavik": (64.15, -21.94),
    "cancun": (21.16, -86.85),
    "rome": (41.90, 12.50),
    "berlin": (52.52, 13.40),
    "singapore": (1.35, 103.82),
    "são paulo": (-23.55, -46.63),
    "lisbon": (38.72, -9.14),
    "mumbai": (19.08, 72.88),
    "cairo": (30.04, 31.24),
    "mexico city": (19.43, -99.13),
    "amsterdam": (52.37, 4.90),
}

# Condition pools by climate band
_TROPICAL_CONDITIONS = ["sunny", "partly_cloudy", "rain", "thunderstorm", "cloudy"]
_TEMPERATE_CONDITIONS = ["sunny", "partly_cloudy", "cloudy", "rain", "overcast"]
_POLAR_CONDITIONS = ["overcast", "snow", "cloudy", "partly_cloudy", "blizzard"]
_ARID_CONDITIONS = ["sunny", "sunny", "partly_cloudy", "dust", "clear"]


def _seed_for(destination: str, date: str) -> int:
    """Return a deterministic integer seed from destination + date."""
    raw = f"{destination.lower().strip()}:{date}"
    return int(hashlib.sha256(raw.encode()).hexdigest()[:8], 16)


def _classify_climate(lat: float) -> str:
    """Rough climate zone from latitude."""
    abs_lat = abs(lat)
    if abs_lat < 23.5:
        return "tropical"
    if abs_lat < 55:
        return "temperate"
    return "polar"


def _is_summer(month: int, lat: float) -> bool:
    """Return True if *month* is a summer month for the given hemisphere."""
    if lat >= 0:
        return month in (6, 7, 8)
    return month in (12, 1, 2)


def _base_temps(climate: str, summer: bool) -> tuple[float, float]:
    """Return (temp_min, temp_max) base values."""
    if climate == "tropical":
        return (24.0, 33.0) if summer else (22.0, 30.0)
    if climate == "temperate":
        return (14.0, 26.0) if summer else (0.0, 8.0)
    # polar
    return (2.0, 12.0) if summer else (-15.0, -2.0)


def generate_forecast(
    destination: str,
    start_date: str,
    end_date: str,
) -> list[WeatherForecast]:
    """Generate deterministic weather forecasts for each day in the range.

    Args:
        destination: City name (case-insensitive).
        start_date: ISO date string (``YYYY-MM-DD``).
        end_date: ISO date string (``YYYY-MM-DD``), inclusive.

    Returns:
        One :class:`WeatherForecast` per day.
    """
    start = datetime.date.fromisoformat(start_date)
    end = datetime.date.fromisoformat(end_date)

    lat, _lng = _CITY_COORDS.get(destination.lower().strip(), (45.0, 0.0))
    climate = _classify_climate(lat)

    conditions: list[str]
    if climate == "tropical":
        conditions = _TROPICAL_CONDITIONS
    elif climate == "polar":
        conditions = _POLAR_CONDITIONS
    else:
        # Check for arid — crude heuristic: latitude 20-35 and known arid cities
        if destination.lower().strip() in ("dubai", "cairo"):
            conditions = _ARID_CONDITIONS
        else:
            conditions = _TEMPERATE_CONDITIONS

    forecasts: list[WeatherForecast] = []
    current = start

    while current <= end:
        rng = random.Random(_seed_for(destination, current.isoformat()))
        summer = _is_summer(current.month, lat)
        base_min, base_max = _base_temps(climate, summer)

        temp_min = round(base_min + rng.uniform(-3, 3), 1)
        temp_max = round(base_max + rng.uniform(-3, 3), 1)
        if temp_max <= temp_min:
            temp_max = temp_min + 2.0

        condition = rng.choice(conditions)
        rain_chance = round(rng.uniform(60, 95), 0) if "rain" in condition or "thunder" in condition else round(rng.uniform(0, 30), 0)
        rain_start: str | None = None
        if rain_chance >= 50:
            hour = rng.randint(8, 18)
            rain_start = f"{hour:02d}:00"

        wind_speed = round(rng.uniform(5, 25), 1)
        if condition in ("thunderstorm", "blizzard", "storm"):
            wind_speed = round(rng.uniform(40, 70), 1)

        forecasts.append(
            WeatherForecast(
                date=current.isoformat(),
                condition=condition,
                temp_max=temp_max,
                temp_min=temp_min,
                rain_chance=rain_chance,
                rain_start=rain_start,
                wind_speed=wind_speed,
            )
        )
        current += datetime.timedelta(days=1)

    return forecasts


def generate_alerts(destination: str) -> list[dict[str, str]]:
    """Return mock severe weather alerts for *destination*.

    Uses a seeded RNG keyed on the destination name so results are
    deterministic.  Most destinations return an empty list.
    """
    rng = random.Random(_seed_for(destination, "alerts"))
    if rng.random() > 0.3:
        return []

    alert_pool = [
        {
            "type": "heat_wave",
            "severity": "warning",
            "message": f"Onda de calor prevista para {destination} nos próximos dias",
        },
        {
            "type": "storm",
            "severity": "watch",
            "message": f"Tempestade tropical se aproximando de {destination}",
        },
        {
            "type": "flood",
            "severity": "advisory",
            "message": f"Risco de enchentes em áreas baixas de {destination}",
        },
    ]
    return [rng.choice(alert_pool)]
