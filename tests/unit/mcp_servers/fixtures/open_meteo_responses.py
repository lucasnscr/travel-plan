"""Fixture data matching real Open-Meteo API response structures.

These responses are based on actual Open-Meteo API responses and are
used to test the OpenMeteoProvider without hitting the real API.
"""

GEOCODING_RESPONSE = {
    "results": [
        {
            "id": 2988507,
            "name": "Paris",
            "latitude": 48.8534,
            "longitude": 2.3488,
            "elevation": 42.0,
            "feature_code": "PPLC",
            "country_code": "FR",
            "country": "France",
            "timezone": "Europe/Paris",
            "population": 2138551,
        }
    ],
    "generationtime_ms": 0.5,
}

GEOCODING_EMPTY_RESPONSE: dict = {
    "generationtime_ms": 0.3,
}

FORECAST_RESPONSE = {
    "latitude": 48.86,
    "longitude": 2.34,
    "generationtime_ms": 0.8,
    "utc_offset_seconds": 3600,
    "timezone": "Europe/Paris",
    "daily_units": {
        "time": "iso8601",
        "temperature_2m_max": "°C",
        "temperature_2m_min": "°C",
        "precipitation_sum": "mm",
        "precipitation_probability_max": "%",
        "weather_code": "wmo code",
        "uv_index_max": "",
        "wind_speed_10m_max": "km/h",
        "wind_direction_10m_dominant": "°",
    },
    "daily": {
        "time": [
            "2025-07-01",
            "2025-07-02",
            "2025-07-03",
            "2025-07-04",
            "2025-07-05",
        ],
        "temperature_2m_max": [28.5, 30.1, 25.3, 22.8, 27.0],
        "temperature_2m_min": [18.2, 19.5, 16.7, 14.3, 17.8],
        "precipitation_sum": [0.0, 0.2, 8.5, 12.3, 0.0],
        "precipitation_probability_max": [5, 15, 75, 90, 10],
        "weather_code": [0, 1, 61, 63, 2],
        "uv_index_max": [8.5, 7.2, 3.1, 2.8, 6.5],
        "wind_speed_10m_max": [12.5, 15.3, 25.8, 35.2, 10.1],
        "wind_direction_10m_dominant": [180, 200, 270, 280, 150],
    },
}

CURRENT_WEATHER_RESPONSE = {
    "latitude": 48.86,
    "longitude": 2.34,
    "generationtime_ms": 0.3,
    "utc_offset_seconds": 3600,
    "timezone": "Europe/Paris",
    "current_units": {
        "time": "iso8601",
        "temperature_2m": "°C",
        "relative_humidity_2m": "%",
        "apparent_temperature": "°C",
        "precipitation": "mm",
        "weather_code": "wmo code",
        "wind_speed_10m": "km/h",
        "wind_direction_10m": "°",
    },
    "current": {
        "time": "2025-07-01T14:00",
        "temperature_2m": 26.3,
        "relative_humidity_2m": 55,
        "apparent_temperature": 28.1,
        "precipitation": 0.0,
        "weather_code": 1,
        "wind_speed_10m": 12.5,
        "wind_direction_10m": 180,
    },
}

HOURLY_RESPONSE = {
    "latitude": 48.86,
    "longitude": 2.34,
    "generationtime_ms": 0.5,
    "utc_offset_seconds": 3600,
    "timezone": "Europe/Paris",
    "hourly_units": {
        "time": "iso8601",
        "temperature_2m": "°C",
        "precipitation_probability": "%",
        "weather_code": "wmo code",
        "wind_speed_10m": "km/h",
        "relative_humidity_2m": "%",
    },
    "hourly": {
        "time": [
            f"2025-07-01T{h:02d}:00" for h in range(24)
        ],
        "temperature_2m": [
            18.2, 17.8, 17.5, 17.2, 17.0, 17.3, 18.0, 19.5,
            21.0, 22.5, 24.0, 25.3, 26.3, 27.0, 27.5, 27.2,
            26.5, 25.8, 24.5, 23.0, 21.5, 20.5, 19.8, 19.0,
        ],
        "precipitation_probability": [
            0, 0, 0, 0, 0, 0, 0, 5,
            10, 10, 15, 15, 10, 10, 5, 5,
            10, 15, 20, 15, 10, 5, 0, 0,
        ],
        "weather_code": [
            0, 0, 0, 0, 0, 0, 1, 1,
            2, 2, 2, 1, 0, 0, 1, 1,
            2, 2, 3, 3, 2, 1, 0, 0,
        ],
        "wind_speed_10m": [
            5.2, 4.8, 4.5, 4.2, 4.0, 4.3, 5.0, 6.5,
            8.0, 9.5, 11.0, 12.5, 13.0, 12.8, 12.5, 11.0,
            10.0, 9.0, 8.0, 7.0, 6.5, 6.0, 5.5, 5.2,
        ],
        "relative_humidity_2m": [
            75, 78, 80, 82, 83, 82, 78, 70,
            62, 55, 50, 48, 45, 43, 42, 44,
            48, 52, 58, 63, 68, 72, 74, 75,
        ],
    },
}

AIR_QUALITY_RESPONSE = {
    "latitude": 48.86,
    "longitude": 2.34,
    "generationtime_ms": 0.2,
    "current_units": {
        "time": "iso8601",
        "pm2_5": "μg/m³",
        "pm10": "μg/m³",
        "us_aqi": "",
    },
    "current": {
        "time": "2025-07-01T14:00",
        "pm2_5": 8.5,
        "pm10": 15.2,
        "us_aqi": 35,
    },
}
