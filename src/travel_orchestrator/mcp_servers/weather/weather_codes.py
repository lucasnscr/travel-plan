"""WMO weather interpretation codes mapping.

Maps WMO weather codes (used by Open-Meteo API) to human-readable
conditions, descriptions in English and Portuguese, and emoji icons.

Reference: https://open-meteo.com/en/docs#weathervariables
WMO Code Table 4677.
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# WMO weather code → metadata mapping
# ---------------------------------------------------------------------------

WMO_CODES: dict[int, dict[str, str]] = {
    0: {
        "condition": "sunny",
        "description_en": "Clear sky",
        "description_pt": "Ceu limpo",
        "icon": "☀️",
    },
    1: {
        "condition": "partly_cloudy",
        "description_en": "Mainly clear",
        "description_pt": "Predominantemente limpo",
        "icon": "🌤️",
    },
    2: {
        "condition": "partly_cloudy",
        "description_en": "Partly cloudy",
        "description_pt": "Parcialmente nublado",
        "icon": "⛅",
    },
    3: {
        "condition": "cloudy",
        "description_en": "Overcast",
        "description_pt": "Nublado",
        "icon": "☁️",
    },
    45: {
        "condition": "fog",
        "description_en": "Fog",
        "description_pt": "Nevoeiro",
        "icon": "🌫️",
    },
    48: {
        "condition": "fog",
        "description_en": "Depositing rime fog",
        "description_pt": "Nevoeiro com geada",
        "icon": "🌫️",
    },
    51: {
        "condition": "drizzle",
        "description_en": "Light drizzle",
        "description_pt": "Garoa leve",
        "icon": "🌦️",
    },
    53: {
        "condition": "drizzle",
        "description_en": "Moderate drizzle",
        "description_pt": "Garoa moderada",
        "icon": "🌦️",
    },
    55: {
        "condition": "drizzle",
        "description_en": "Dense drizzle",
        "description_pt": "Garoa intensa",
        "icon": "🌧️",
    },
    56: {
        "condition": "freezing_drizzle",
        "description_en": "Light freezing drizzle",
        "description_pt": "Garoa congelante leve",
        "icon": "🌧️",
    },
    57: {
        "condition": "freezing_drizzle",
        "description_en": "Dense freezing drizzle",
        "description_pt": "Garoa congelante intensa",
        "icon": "🌧️",
    },
    61: {
        "condition": "rain",
        "description_en": "Slight rain",
        "description_pt": "Chuva leve",
        "icon": "🌧️",
    },
    63: {
        "condition": "rain",
        "description_en": "Moderate rain",
        "description_pt": "Chuva moderada",
        "icon": "🌧️",
    },
    65: {
        "condition": "rain",
        "description_en": "Heavy rain",
        "description_pt": "Chuva forte",
        "icon": "🌧️",
    },
    66: {
        "condition": "freezing_rain",
        "description_en": "Light freezing rain",
        "description_pt": "Chuva congelante leve",
        "icon": "🌨️",
    },
    67: {
        "condition": "freezing_rain",
        "description_en": "Heavy freezing rain",
        "description_pt": "Chuva congelante forte",
        "icon": "🌨️",
    },
    71: {
        "condition": "snow",
        "description_en": "Slight snow fall",
        "description_pt": "Neve leve",
        "icon": "❄️",
    },
    73: {
        "condition": "snow",
        "description_en": "Moderate snow fall",
        "description_pt": "Neve moderada",
        "icon": "🌨️",
    },
    75: {
        "condition": "snow",
        "description_en": "Heavy snow fall",
        "description_pt": "Neve forte",
        "icon": "🌨️",
    },
    77: {
        "condition": "snow",
        "description_en": "Snow grains",
        "description_pt": "Graos de neve",
        "icon": "🌨️",
    },
    80: {
        "condition": "rain",
        "description_en": "Slight rain showers",
        "description_pt": "Pancadas leves de chuva",
        "icon": "🌦️",
    },
    81: {
        "condition": "rain",
        "description_en": "Moderate rain showers",
        "description_pt": "Pancadas moderadas de chuva",
        "icon": "🌧️",
    },
    82: {
        "condition": "rain",
        "description_en": "Violent rain showers",
        "description_pt": "Pancadas violentas de chuva",
        "icon": "🌧️",
    },
    85: {
        "condition": "snow",
        "description_en": "Slight snow showers",
        "description_pt": "Pancadas leves de neve",
        "icon": "🌨️",
    },
    86: {
        "condition": "snow",
        "description_en": "Heavy snow showers",
        "description_pt": "Pancadas fortes de neve",
        "icon": "🌨️",
    },
    95: {
        "condition": "thunderstorm",
        "description_en": "Thunderstorm",
        "description_pt": "Tempestade com trovoadas",
        "icon": "⛈️",
    },
    96: {
        "condition": "thunderstorm",
        "description_en": "Thunderstorm with slight hail",
        "description_pt": "Tempestade com granizo leve",
        "icon": "⛈️",
    },
    99: {
        "condition": "thunderstorm",
        "description_en": "Thunderstorm with heavy hail",
        "description_pt": "Tempestade com granizo forte",
        "icon": "⛈️",
    },
}

_UNKNOWN: dict[str, str] = {
    "condition": "unknown",
    "description_en": "Unknown",
    "description_pt": "Desconhecido",
    "icon": "❓",
}


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def code_to_condition(wmo_code: int) -> str:
    """Return the condition string for a WMO weather code.

    Examples: ``"sunny"``, ``"rain"``, ``"thunderstorm"``, ``"snow"``.
    Returns ``"unknown"`` for unrecognised codes.
    """
    return WMO_CODES.get(wmo_code, _UNKNOWN)["condition"]


def code_to_description(wmo_code: int, lang: str = "en") -> str:
    """Return a human-readable description for a WMO weather code.

    Args:
        wmo_code: WMO weather interpretation code.
        lang: ``"en"`` for English, ``"pt"`` for Portuguese.
    """
    entry = WMO_CODES.get(wmo_code, _UNKNOWN)
    key = f"description_{lang}" if f"description_{lang}" in entry else "description_en"
    return entry[key]


def code_to_icon(wmo_code: int) -> str:
    """Return an emoji icon for a WMO weather code."""
    return WMO_CODES.get(wmo_code, _UNKNOWN)["icon"]


def is_rainy(wmo_code: int) -> bool:
    """Return True if the WMO code indicates any form of precipitation."""
    condition = code_to_condition(wmo_code)
    return condition in (
        "drizzle",
        "freezing_drizzle",
        "rain",
        "freezing_rain",
        "snow",
        "thunderstorm",
    )
