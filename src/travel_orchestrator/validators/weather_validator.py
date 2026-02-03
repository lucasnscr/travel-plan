"""Weather-aware validation for outdoor activities.

Cross-references the weather forecast with planned activities to flag
rain/wind risks and suggest indoor alternatives.
"""

from __future__ import annotations

from travel_orchestrator.state.models import (
    Activity,
    ValidationResult,
    WeatherForecast,
)

# Thresholds
_HIGH_RAIN_CHANCE = 60.0  # percentage
_DANGEROUS_WIND_SPEED = 50.0  # km/h
_EXTREME_HEAT = 38.0  # °C
_EXTREME_COLD = 0.0  # °C


class WeatherValidator:
    """Validates planned activities against weather forecasts.

    All methods are stateless — they receive forecast + activity data
    and return a :class:`ValidationResult`.
    """

    @staticmethod
    def validate_outdoor_activities(
        activities: list[Activity],
        forecast: WeatherForecast,
    ) -> ValidationResult:
        """Flag outdoor activities that conflict with the day's forecast.

        Checks:
        - Rain chance above threshold for outdoor activities.
        - Dangerous wind speeds.
        - Extreme temperatures (heat or cold).
        """
        issues: list[str] = []
        fixes: list[str] = []

        outdoor = [a for a in activities if not a["indoor"]]
        if not outdoor:
            return ValidationResult(
                is_valid=True,
                issues=[],
                severity="info",
                suggested_fixes=[],
            )

        outdoor_names = [a["name"] for a in outdoor]

        # --- Rain ---------------------------------------------------------
        if forecast["rain_chance"] >= _HIGH_RAIN_CHANCE:
            rain_detail = (
                f" (previsão de início às {forecast['rain_start']})"
                if forecast.get("rain_start")
                else ""
            )
            issues.append(
                f"Chance de chuva {forecast['rain_chance']:.0f}%{rain_detail} "
                f"afeta atividades outdoor: {', '.join(outdoor_names)}"
            )
            fixes.append("Substituir atividades outdoor por opções indoor")
            fixes.append("Mover atividades outdoor para dia com melhor previsão")

        # --- Wind ---------------------------------------------------------
        if forecast["wind_speed"] >= _DANGEROUS_WIND_SPEED:
            issues.append(
                f"Vento forte ({forecast['wind_speed']:.0f} km/h) "
                f"torna arriscadas atividades ao ar livre"
            )
            fixes.append("Reagendar atividades outdoor para dia com menos vento")

        # --- Extreme temperatures -----------------------------------------
        if forecast["temp_max"] >= _EXTREME_HEAT:
            issues.append(
                f"Temperatura máxima muito alta ({forecast['temp_max']:.0f}°C) — "
                f"risco para atividades outdoor prolongadas"
            )
            fixes.append("Agendar atividades outdoor para manhã cedo ou final de tarde")

        if forecast["temp_min"] <= _EXTREME_COLD:
            issues.append(
                f"Temperatura mínima muito baixa ({forecast['temp_min']:.0f}°C) — "
                f"considerar atividades indoor"
            )
            fixes.append("Substituir atividades outdoor por opções indoor")

        has_errors = any(
            "arriscadas" in i or "muito alta" in i or "muito baixa" in i
            for i in issues
        )

        return ValidationResult(
            is_valid=len(issues) == 0,
            issues=issues,
            severity="error" if has_errors else ("warning" if issues else "info"),
            suggested_fixes=fixes,
        )

    @staticmethod
    def validate_weather_suitability(
        forecast: WeatherForecast,
    ) -> ValidationResult:
        """General weather suitability check for the travel day.

        Returns warnings for poor conditions regardless of specific
        activities.
        """
        issues: list[str] = []
        fixes: list[str] = []

        if forecast["condition"].lower() in ("storm", "thunderstorm", "hurricane", "typhoon"):
            issues.append(
                f"Condição climática severa prevista: {forecast['condition']}"
            )
            fixes.append("Considerar alterar datas da viagem se possível")

        if forecast["wind_speed"] >= _DANGEROUS_WIND_SPEED:
            issues.append(
                f"Ventos fortes previstos ({forecast['wind_speed']:.0f} km/h) — "
                f"possíveis cancelamentos de voos e atrações"
            )

        return ValidationResult(
            is_valid=len(issues) == 0,
            issues=issues,
            severity="error" if issues else "info",
            suggested_fixes=fixes,
        )
