"""Open-Meteo API provider for real weather data.

Open-Meteo is free, requires no API key, and provides:
- Current weather conditions
- 16-day daily forecast
- Hourly forecast
- Air quality index
- Geocoding (city name → coordinates)

Reference: https://open-meteo.com/en/docs
"""

from __future__ import annotations

import datetime
from typing import Any

import httpx

from travel_orchestrator.mcp_servers.weather.cache import TTLCache
from travel_orchestrator.mcp_servers.weather.weather_codes import (
    code_to_condition,
    code_to_description,
    code_to_icon,
    is_rainy,
)
from travel_orchestrator.utils.logging import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Default URLs
# ---------------------------------------------------------------------------

_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
_AIR_QUALITY_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
_GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"

_DEFAULT_TIMEOUT = 10.0


class OpenMeteoProvider:
    """Async client for the Open-Meteo weather API."""

    def __init__(
        self,
        *,
        forecast_url: str = _FORECAST_URL,
        air_quality_url: str = _AIR_QUALITY_URL,
        geocoding_url: str = _GEOCODING_URL,
        timeout: float = _DEFAULT_TIMEOUT,
        cache: TTLCache | None = None,
    ) -> None:
        self._forecast_url = forecast_url
        self._air_quality_url = air_quality_url
        self._geocoding_url = geocoding_url
        self._timeout = timeout
        self._cache = cache or TTLCache(default_ttl_seconds=1800)

    # ------------------------------------------------------------------
    # Geocoding
    # ------------------------------------------------------------------

    async def geocode(self, destination: str) -> tuple[float, float]:
        """Resolve a city name to ``(latitude, longitude)``.

        Uses the Open-Meteo Geocoding API.  Returns the first match.
        Raises ``ValueError`` if no results are found.
        """
        cache_key = TTLCache.make_key("geocode", destination.lower().strip())
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(
                self._geocoding_url,
                params={"name": destination, "count": 1, "language": "en"},
            )
            resp.raise_for_status()
            data = resp.json()

        results = data.get("results")
        if not results:
            raise ValueError(f"Could not geocode destination: {destination!r}")

        lat = float(results[0]["latitude"])
        lon = float(results[0]["longitude"])

        self._cache.set(cache_key, (lat, lon), ttl=86400)  # 24h for geocoding
        logger.info(
            "geocoded_destination",
            destination=destination,
            lat=lat,
            lon=lon,
            name=results[0].get("name"),
            country=results[0].get("country"),
        )
        return lat, lon

    # ------------------------------------------------------------------
    # Current weather
    # ------------------------------------------------------------------

    async def get_current_weather(
        self, lat: float, lon: float,
    ) -> dict[str, Any]:
        """Fetch current weather conditions for a coordinate pair."""
        cache_key = TTLCache.make_key("current", round(lat, 2), round(lon, 2))
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        params = {
            "latitude": lat,
            "longitude": lon,
            "current": (
                "temperature_2m,relative_humidity_2m,apparent_temperature,"
                "precipitation,weather_code,wind_speed_10m,wind_direction_10m"
            ),
            "timezone": "auto",
        }

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(self._forecast_url, params=params)
            resp.raise_for_status()
            data = resp.json()

        current = data.get("current", {})
        wmo_code = int(current.get("weather_code", 0))

        result: dict[str, Any] = {
            "temperature": current.get("temperature_2m"),
            "apparent_temperature": current.get("apparent_temperature"),
            "humidity": current.get("relative_humidity_2m"),
            "precipitation_mm": current.get("precipitation"),
            "wind_speed_kmh": current.get("wind_speed_10m"),
            "wind_direction": current.get("wind_direction_10m"),
            "weather_code": wmo_code,
            "condition": code_to_condition(wmo_code),
            "description": code_to_description(wmo_code),
            "description_pt": code_to_description(wmo_code, lang="pt"),
            "icon": code_to_icon(wmo_code),
            "data_source": "open_meteo",
        }

        self._cache.set(cache_key, result, ttl=600)  # 10 min for current
        return result

    # ------------------------------------------------------------------
    # Daily forecast
    # ------------------------------------------------------------------

    async def get_forecast(
        self, lat: float, lon: float, days: int = 7,
    ) -> list[dict[str, Any]]:
        """Fetch daily forecast for up to 16 days."""
        days = min(max(days, 1), 16)

        cache_key = TTLCache.make_key("forecast", round(lat, 2), round(lon, 2), days)
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        params = {
            "latitude": lat,
            "longitude": lon,
            "daily": (
                "temperature_2m_max,temperature_2m_min,"
                "precipitation_sum,precipitation_probability_max,"
                "weather_code,uv_index_max,"
                "wind_speed_10m_max,wind_direction_10m_dominant"
            ),
            "timezone": "auto",
            "forecast_days": days,
        }

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(self._forecast_url, params=params)
            resp.raise_for_status()
            data = resp.json()

        daily = data.get("daily", {})
        dates = daily.get("time", [])

        results: list[dict[str, Any]] = []
        for i, date_str in enumerate(dates):
            wmo_code = int((daily.get("weather_code") or [0])[i] if i < len(daily.get("weather_code", [])) else 0)
            rain_prob = (daily.get("precipitation_probability_max") or [0])[i] if i < len(daily.get("precipitation_probability_max", [])) else 0

            results.append({
                "date": date_str,
                "temp_max": _safe_float(daily, "temperature_2m_max", i),
                "temp_min": _safe_float(daily, "temperature_2m_min", i),
                "precipitation_sum_mm": _safe_float(daily, "precipitation_sum", i),
                "rain_chance": float(rain_prob or 0),
                "weather_code": wmo_code,
                "condition": code_to_condition(wmo_code),
                "description": code_to_description(wmo_code),
                "description_pt": code_to_description(wmo_code, lang="pt"),
                "icon": code_to_icon(wmo_code),
                "uv_index": _safe_float(daily, "uv_index_max", i),
                "wind_speed": _safe_float(daily, "wind_speed_10m_max", i),
                "wind_direction": _safe_float(daily, "wind_direction_10m_dominant", i),
                "data_source": "open_meteo",
            })

        self._cache.set(cache_key, results)
        return results

    # ------------------------------------------------------------------
    # Hourly forecast
    # ------------------------------------------------------------------

    async def get_hourly_forecast(
        self, lat: float, lon: float, date: str,
    ) -> list[dict[str, Any]]:
        """Fetch hourly forecast for a specific date."""
        cache_key = TTLCache.make_key("hourly", round(lat, 2), round(lon, 2), date)
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        params = {
            "latitude": lat,
            "longitude": lon,
            "hourly": (
                "temperature_2m,precipitation_probability,"
                "weather_code,wind_speed_10m,relative_humidity_2m"
            ),
            "timezone": "auto",
            "start_date": date,
            "end_date": date,
        }

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(self._forecast_url, params=params)
            resp.raise_for_status()
            data = resp.json()

        hourly = data.get("hourly", {})
        times = hourly.get("time", [])

        results: list[dict[str, Any]] = []
        for i, time_str in enumerate(times):
            wmo_code = int((hourly.get("weather_code") or [0])[i] if i < len(hourly.get("weather_code", [])) else 0)

            results.append({
                "time": time_str,
                "hour": time_str.split("T")[1] if "T" in time_str else time_str,
                "temperature": _safe_float(hourly, "temperature_2m", i),
                "precipitation_probability": _safe_float(hourly, "precipitation_probability", i),
                "humidity": _safe_float(hourly, "relative_humidity_2m", i),
                "wind_speed_kmh": _safe_float(hourly, "wind_speed_10m", i),
                "weather_code": wmo_code,
                "condition": code_to_condition(wmo_code),
                "icon": code_to_icon(wmo_code),
                "data_source": "open_meteo",
            })

        self._cache.set(cache_key, results)
        return results

    # ------------------------------------------------------------------
    # Air quality
    # ------------------------------------------------------------------

    async def get_air_quality(
        self, lat: float, lon: float,
    ) -> dict[str, Any]:
        """Fetch current air quality index."""
        cache_key = TTLCache.make_key("airquality", round(lat, 2), round(lon, 2))
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        params = {
            "latitude": lat,
            "longitude": lon,
            "current": "pm2_5,pm10,us_aqi",
        }

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(self._air_quality_url, params=params)
            resp.raise_for_status()
            data = resp.json()

        current = data.get("current", {})
        us_aqi = current.get("us_aqi")

        result: dict[str, Any] = {
            "pm2_5": current.get("pm2_5"),
            "pm10": current.get("pm10"),
            "us_aqi": us_aqi,
            "category": _aqi_category(us_aqi),
            "data_source": "open_meteo",
        }

        self._cache.set(cache_key, result, ttl=1800)  # 30 min
        return result

    # ------------------------------------------------------------------
    # Convenience: backward-compatible destination-based forecast
    # ------------------------------------------------------------------

    async def get_forecast_for_destination(
        self,
        destination: str,
        start_date: str,
        end_date: str,
    ) -> list[dict[str, Any]]:
        """Geocode *destination* and return daily forecasts in the legacy format.

        Returns dicts compatible with :class:`WeatherForecast` TypedDict:
        ``date``, ``condition``, ``temp_max``, ``temp_min``, ``rain_chance``,
        ``rain_start``, ``wind_speed``, plus bonus fields ``uv_index`` and
        ``data_source``.
        """
        lat, lon = await self.geocode(destination)

        start = datetime.date.fromisoformat(start_date)
        end = datetime.date.fromisoformat(end_date)
        total_days = (end - start).days + 1

        if total_days <= 0:
            return []

        # Open-Meteo returns forecast from today; we filter to the date range
        raw_forecast = await self.get_forecast(lat, lon, days=16)

        # Convert to backward-compatible format
        results: list[dict[str, Any]] = []
        for day in raw_forecast:
            day_date = day["date"]
            try:
                d = datetime.date.fromisoformat(day_date)
            except ValueError:
                continue
            if start <= d <= end:
                # Estimate rain_start from condition
                rain_start: str | None = None
                if day["rain_chance"] >= 50:
                    rain_start = "14:00"  # default estimate for daily data

                results.append({
                    "date": day_date,
                    "condition": day["condition"],
                    "temp_max": day["temp_max"],
                    "temp_min": day["temp_min"],
                    "rain_chance": day["rain_chance"],
                    "rain_start": rain_start,
                    "wind_speed": day["wind_speed"],
                    # Bonus fields
                    "uv_index": day.get("uv_index"),
                    "icon": day.get("icon"),
                    "description": day.get("description"),
                    "data_source": "open_meteo",
                })

        return results


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _safe_float(
    data: dict[str, Any], key: str, index: int, default: float = 0.0,
) -> float:
    """Safely extract a float from a nested list in the API response."""
    values = data.get(key)
    if values is None or index >= len(values):
        return default
    val = values[index]
    if val is None:
        return default
    return float(val)


def _aqi_category(aqi: int | float | None) -> str:
    """Map US AQI value to a human-readable category."""
    if aqi is None:
        return "unknown"
    aqi_val = float(aqi)
    if aqi_val <= 50:
        return "good"
    if aqi_val <= 100:
        return "moderate"
    if aqi_val <= 150:
        return "unhealthy_for_sensitive"
    if aqi_val <= 200:
        return "unhealthy"
    if aqi_val <= 300:
        return "very_unhealthy"
    return "hazardous"
