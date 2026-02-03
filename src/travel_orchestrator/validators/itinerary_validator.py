"""Deterministic validation of travel itineraries.

Checks geographic coherence, timing conflicts, budget constraints,
and activity-count limits — all without LLM calls.
"""

from __future__ import annotations

import math

from travel_orchestrator.config.constants import (
    MAX_ACTIVITIES_PER_DAY,
    MAX_DAILY_TRAVEL_TIME_MINUTES,
    MIN_ACTIVITY_DURATION_MINUTES,
)
from travel_orchestrator.state.models import (
    Activity,
    HotelOption,
    TravelPlannerCore,
    ValidationResult,
)

# Average urban speed used to estimate travel time from distances.
_AVERAGE_URBAN_SPEED_KMH = 30.0

# Safety margin percentage applied to budget checks.
_BUDGET_SAFETY_MARGIN = 0.10


class ItineraryValidator:
    """Deterministic itinerary validation.

    All methods are stateless and side-effect free — they receive data
    and return a :class:`ValidationResult`.
    """

    @staticmethod
    def validate_geographic_coherence(
        activities: list[Activity],
        hotel: HotelOption,
        max_travel_time_minutes: int = MAX_DAILY_TRAVEL_TIME_MINUTES,
    ) -> ValidationResult:
        """Check whether a day's activities are geographically feasible.

        Estimates total travel time using haversine distances and an
        assumed average urban speed.  Flags the day when estimated
        commute exceeds *max_travel_time_minutes*.
        """
        if not activities:
            return ValidationResult(
                is_valid=True,
                issues=[],
                severity="info",
                suggested_fixes=[],
            )

        issues: list[str] = []
        fixes: list[str] = []

        total_distance_km = 0.0

        # Hotel → first activity
        prev_lat = hotel["coordinates"]["lat"]
        prev_lng = hotel["coordinates"]["lng"]

        for activity in activities:
            act_lat = activity["coordinates"]["lat"]
            act_lng = activity["coordinates"]["lng"]
            total_distance_km += _haversine_distance(prev_lat, prev_lng, act_lat, act_lng)
            prev_lat, prev_lng = act_lat, act_lng

        # Last activity → hotel (return trip)
        total_distance_km += _haversine_distance(
            prev_lat,
            prev_lng,
            hotel["coordinates"]["lat"],
            hotel["coordinates"]["lng"],
        )

        estimated_travel_minutes = (total_distance_km / _AVERAGE_URBAN_SPEED_KMH) * 60

        if estimated_travel_minutes > max_travel_time_minutes:
            issues.append(
                f"Tempo de deslocamento estimado ({estimated_travel_minutes:.0f}min) "
                f"excede limite de {max_travel_time_minutes}min"
            )
            fixes.append("Reagrupar atividades por proximidade geográfica")

        return ValidationResult(
            is_valid=len(issues) == 0,
            issues=issues,
            severity="error" if issues else "info",
            suggested_fixes=fixes,
        )

    @staticmethod
    def validate_timing_conflicts(
        activities: list[Activity],
        date: str,
    ) -> ValidationResult:
        """Check for scheduling problems in a single day.

        Validates:
        - Too many activities for the day.
        - Activities shorter than the minimum duration.
        - Activities scheduled outside their opening hours for *date*.
        """
        issues: list[str] = []
        fixes: list[str] = []

        if len(activities) > MAX_ACTIVITIES_PER_DAY:
            issues.append(
                f"Número de atividades ({len(activities)}) excede "
                f"o limite diário de {MAX_ACTIVITIES_PER_DAY}"
            )
            fixes.append("Redistribuir atividades entre dias ou remover as de menor score")

        day_name = _iso_to_weekday(date)

        for activity in activities:
            if activity["duration_minutes"] < MIN_ACTIVITY_DURATION_MINUTES:
                issues.append(
                    f"Atividade '{activity['name']}' tem duração de "
                    f"{activity['duration_minutes']}min (mínimo: {MIN_ACTIVITY_DURATION_MINUTES}min)"
                )

            hours = activity.get("opening_hours", {})
            if day_name in hours and hours[day_name].lower() == "closed":
                issues.append(
                    f"Atividade '{activity['name']}' está fechada em {day_name}"
                )
                fixes.append(f"Mover '{activity['name']}' para outro dia")

        severity: str
        if any("excede" in i or "fechada" in i for i in issues):
            severity = "error"
        elif issues:
            severity = "warning"
        else:
            severity = "info"

        return ValidationResult(
            is_valid=len(issues) == 0,
            issues=issues,
            severity=severity,
            suggested_fixes=fixes,
        )

    @staticmethod
    def validate_budget_constraints(
        state: TravelPlannerCore,
    ) -> ValidationResult:
        """Check whether the current plan fits inside the traveler's budget.

        Flags:
        - Hard error when ``current_cost`` exceeds ``budget.total``.
        - Warning when the remaining margin is below 10 %.
        """
        budget_total = float(state["budget"]["total"])
        current_cost = state["current_cost"]

        issues: list[str] = []
        fixes: list[str] = []

        over_budget = current_cost > budget_total

        if over_budget:
            overage = current_cost - budget_total
            percentage = (overage / budget_total) * 100
            issues.append(
                f"Custo ({current_cost:.2f}) excede budget ({budget_total:.2f}) "
                f"em {percentage:.1f}%"
            )
            fixes.append("Selecionar opções mais econômicas de voo ou hotel")

        margin = budget_total * _BUDGET_SAFETY_MARGIN
        if not over_budget and current_cost > (budget_total - margin):
            issues.append("Custo muito próximo do limite (margem < 10%)")
            fixes.append("Considerar reduzir custos para ter margem de segurança")

        return ValidationResult(
            is_valid=not over_budget,
            issues=issues,
            severity="error" if over_budget else ("warning" if issues else "info"),
            suggested_fixes=fixes,
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _haversine_distance(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
) -> float:
    """Return the great-circle distance in km between two points."""
    r = 6371.0  # Earth radius in km

    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
    )
    c = 2 * math.asin(math.sqrt(a))

    return r * c


def _iso_to_weekday(iso_date: str) -> str:
    """Convert ``'2025-04-07'`` → ``'monday'``."""
    import datetime

    dt = datetime.date.fromisoformat(iso_date)
    return dt.strftime("%A").lower()
