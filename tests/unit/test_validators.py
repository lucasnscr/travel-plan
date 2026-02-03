"""Unit tests for itinerary and weather validators."""

from __future__ import annotations

import pytest

from travel_orchestrator.state.models import (
    Activity,
    HotelOption,
    TravelPlannerCore,
    WeatherForecast,
)
from travel_orchestrator.validators.itinerary_validator import (
    ItineraryValidator,
    _haversine_distance,
)
from travel_orchestrator.validators.weather_validator import WeatherValidator


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_hotel(*, lat: float = 48.8566, lng: float = 2.3522) -> HotelOption:
    """Hotel near central Paris by default."""
    return HotelOption(
        id="h-1",
        name="Hotel Central",
        address="1 Rue de Rivoli",
        coordinates={"lat": lat, "lng": lng},
        stars=4,
        price_per_night=200.0,
        currency="EUR",
        amenities=["wifi", "breakfast"],
        reviews_score=8.5,
        distance_to_center_km=0.5,
        score=0.85,
    )


def _make_activity(
    *,
    name: str = "Louvre Museum",
    lat: float = 48.8606,
    lng: float = 2.3376,
    duration_minutes: int = 120,
    indoor: bool = True,
    opening_hours: dict[str, str] | None = None,
) -> Activity:
    return Activity(
        id=f"a-{name[:4].lower()}",
        name=name,
        category="culture",
        address="Somewhere in Paris",
        coordinates={"lat": lat, "lng": lng},
        duration_minutes=duration_minutes,
        price=20.0,
        currency="EUR",
        opening_hours=opening_hours or {"monday": "09:00-18:00", "tuesday": "09:00-18:00"},
        requires_booking=False,
        indoor=indoor,
        description="A nice activity",
        score=0.9,
    )


def _make_state(
    *,
    budget_total: float = 5000.0,
    current_cost: float = 3000.0,
) -> TravelPlannerCore:
    return TravelPlannerCore(
        plan_id="test-plan",
        destination="Paris",
        dates={"start_date": "2025-04-07", "end_date": "2025-04-14"},
        budget={"total": budget_total, "currency": "EUR", "flexibility": 0.1},
        traveler_profile={"interests": ["culture"], "pace": "moderate", "group_size": 2},
        selected_flight_id=None,
        selected_hotel_id=None,
        selected_activity_ids=[],
        current_cost=current_cost,
        revision_count=0,
        approval_status="pending",
        risk_flags=[],
        alternative_plans={},
    )


def _make_forecast(
    *,
    rain_chance: float = 10.0,
    rain_start: str | None = None,
    wind_speed: float = 10.0,
    temp_max: float = 22.0,
    temp_min: float = 12.0,
    condition: str = "sunny",
) -> WeatherForecast:
    return WeatherForecast(
        date="2025-04-07",
        condition=condition,
        temp_max=temp_max,
        temp_min=temp_min,
        rain_chance=rain_chance,
        rain_start=rain_start,
        wind_speed=wind_speed,
    )


# ===================================================================
# Haversine
# ===================================================================


class TestHaversine:
    def test_same_point_returns_zero(self) -> None:
        assert _haversine_distance(0.0, 0.0, 0.0, 0.0) == 0.0

    def test_known_distance(self) -> None:
        # Paris → London ≈ 344 km
        dist = _haversine_distance(48.8566, 2.3522, 51.5074, -0.1278)
        assert 340.0 < dist < 350.0

    def test_symmetry(self) -> None:
        d1 = _haversine_distance(48.8566, 2.3522, 35.6762, 139.6503)
        d2 = _haversine_distance(35.6762, 139.6503, 48.8566, 2.3522)
        assert abs(d1 - d2) < 0.01


# ===================================================================
# ItineraryValidator — geographic coherence
# ===================================================================


class TestGeographicCoherence:
    def test_nearby_activities_pass(self) -> None:
        hotel = _make_hotel()
        activities = [
            _make_activity(name="Louvre", lat=48.8606, lng=2.3376),
            _make_activity(name="Tuileries", lat=48.8634, lng=2.3275),
        ]
        result = ItineraryValidator.validate_geographic_coherence(activities, hotel)
        assert result["is_valid"] is True
        assert result["severity"] == "info"
        assert result["issues"] == []

    def test_far_activities_fail(self) -> None:
        hotel = _make_hotel()
        # Activity in Versailles (~17 km from central Paris)
        activities = [
            _make_activity(name="Versailles", lat=48.8049, lng=2.1204),
            _make_activity(name="CDG Airport", lat=49.0097, lng=2.5479),
        ]
        result = ItineraryValidator.validate_geographic_coherence(
            activities, hotel, max_travel_time_minutes=10
        )
        assert result["is_valid"] is False
        assert result["severity"] == "error"
        assert any("excede" in i for i in result["issues"])
        assert len(result["suggested_fixes"]) > 0

    def test_empty_activities_pass(self) -> None:
        hotel = _make_hotel()
        result = ItineraryValidator.validate_geographic_coherence([], hotel)
        assert result["is_valid"] is True


# ===================================================================
# ItineraryValidator — timing conflicts
# ===================================================================


class TestTimingConflicts:
    def test_normal_day_passes(self) -> None:
        activities = [
            _make_activity(name="A1"),
            _make_activity(name="A2"),
        ]
        result = ItineraryValidator.validate_timing_conflicts(activities, "2025-04-07")
        assert result["is_valid"] is True

    def test_too_many_activities(self) -> None:
        activities = [_make_activity(name=f"A{i}") for i in range(8)]
        result = ItineraryValidator.validate_timing_conflicts(activities, "2025-04-07")
        assert result["is_valid"] is False
        assert any("excede" in i for i in result["issues"])

    def test_short_activity_flagged(self) -> None:
        activities = [_make_activity(name="Quick stop", duration_minutes=10)]
        result = ItineraryValidator.validate_timing_conflicts(activities, "2025-04-07")
        assert result["is_valid"] is False
        assert any("duração" in i for i in result["issues"])

    def test_closed_day_flagged(self) -> None:
        # 2025-04-07 is a Monday
        activities = [
            _make_activity(
                name="Musée Closed",
                opening_hours={"monday": "closed", "tuesday": "09:00-18:00"},
            ),
        ]
        result = ItineraryValidator.validate_timing_conflicts(activities, "2025-04-07")
        assert result["is_valid"] is False
        assert any("fechada" in i for i in result["issues"])


# ===================================================================
# ItineraryValidator — budget constraints
# ===================================================================


class TestBudgetConstraints:
    def test_within_budget(self) -> None:
        state = _make_state(budget_total=5000.0, current_cost=3000.0)
        result = ItineraryValidator.validate_budget_constraints(state)
        assert result["is_valid"] is True
        assert result["severity"] == "info"

    def test_over_budget(self) -> None:
        state = _make_state(budget_total=5000.0, current_cost=6000.0)
        result = ItineraryValidator.validate_budget_constraints(state)
        assert result["is_valid"] is False
        assert result["severity"] == "error"
        assert any("excede" in i for i in result["issues"])

    def test_near_budget_warns(self) -> None:
        # 4600 is within 5000 but past the 90% mark (4500)
        state = _make_state(budget_total=5000.0, current_cost=4600.0)
        result = ItineraryValidator.validate_budget_constraints(state)
        assert result["is_valid"] is True
        assert result["severity"] == "warning"
        assert any("margem" in i for i in result["issues"])

    def test_exactly_at_limit(self) -> None:
        state = _make_state(budget_total=5000.0, current_cost=5000.0)
        result = ItineraryValidator.validate_budget_constraints(state)
        # At the limit the margin warning fires but it's not over budget
        assert result["is_valid"] is True
        assert result["severity"] == "warning"


# ===================================================================
# WeatherValidator — outdoor activities
# ===================================================================


class TestWeatherOutdoor:
    def test_sunny_day_passes(self) -> None:
        forecast = _make_forecast(rain_chance=5.0, wind_speed=10.0)
        activities = [_make_activity(name="Park Walk", indoor=False)]
        result = WeatherValidator.validate_outdoor_activities(activities, forecast)
        assert result["is_valid"] is True

    def test_high_rain_flags_outdoor(self) -> None:
        forecast = _make_forecast(rain_chance=80.0, rain_start="14:00")
        activities = [_make_activity(name="Park Walk", indoor=False)]
        result = WeatherValidator.validate_outdoor_activities(activities, forecast)
        assert result["is_valid"] is False
        assert any("chuva" in i.lower() for i in result["issues"])
        assert any("14:00" in i for i in result["issues"])

    def test_indoor_only_ignores_rain(self) -> None:
        forecast = _make_forecast(rain_chance=90.0)
        activities = [_make_activity(name="Museum", indoor=True)]
        result = WeatherValidator.validate_outdoor_activities(activities, forecast)
        assert result["is_valid"] is True

    def test_strong_wind_flagged(self) -> None:
        forecast = _make_forecast(wind_speed=60.0)
        activities = [_make_activity(name="Boat Tour", indoor=False)]
        result = WeatherValidator.validate_outdoor_activities(activities, forecast)
        assert result["is_valid"] is False
        assert any("vento" in i.lower() for i in result["issues"])

    def test_extreme_heat_flagged(self) -> None:
        forecast = _make_forecast(temp_max=42.0)
        activities = [_make_activity(name="Desert Walk", indoor=False)]
        result = WeatherValidator.validate_outdoor_activities(activities, forecast)
        assert result["is_valid"] is False
        assert any("alta" in i for i in result["issues"])

    def test_extreme_cold_flagged(self) -> None:
        forecast = _make_forecast(temp_min=-5.0)
        activities = [_make_activity(name="Ski Trip", indoor=False)]
        result = WeatherValidator.validate_outdoor_activities(activities, forecast)
        assert result["is_valid"] is False
        assert any("baixa" in i for i in result["issues"])

    def test_no_activities_passes(self) -> None:
        forecast = _make_forecast(rain_chance=90.0)
        result = WeatherValidator.validate_outdoor_activities([], forecast)
        assert result["is_valid"] is True


# ===================================================================
# WeatherValidator — general suitability
# ===================================================================


class TestWeatherSuitability:
    def test_normal_weather_ok(self) -> None:
        forecast = _make_forecast(condition="sunny", wind_speed=10.0)
        result = WeatherValidator.validate_weather_suitability(forecast)
        assert result["is_valid"] is True
        assert result["severity"] == "info"

    def test_storm_flagged(self) -> None:
        forecast = _make_forecast(condition="storm", wind_speed=20.0)
        result = WeatherValidator.validate_weather_suitability(forecast)
        assert result["is_valid"] is False
        assert any("severa" in i for i in result["issues"])

    def test_typhoon_flagged(self) -> None:
        forecast = _make_forecast(condition="typhoon", wind_speed=80.0)
        result = WeatherValidator.validate_weather_suitability(forecast)
        assert result["is_valid"] is False
        assert len(result["issues"]) == 2  # condition + wind
