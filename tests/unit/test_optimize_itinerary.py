"""Unit tests for the optimize_itinerary graph node."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from travel_orchestrator.graph.nodes.optimize_itinerary import (
    MAX_OPTIMIZATION_ITERATIONS,
    PACE_ACTIVITIES_PER_DAY,
    _assign_time_slots,
    _build_forecast_map,
    _build_initial_prompt,
    _build_repair_prompt,
    _collect_final_warnings,
    _compute_trip_dates,
    _deterministic_fallback,
    _infer_theme,
    _nearest_neighbor_sort,
    _parse_llm_response,
    _resolve_selected_activities,
    _resolve_selected_hotel,
    _validate_itinerary,
    optimize_itinerary_node,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_hotel(
    *,
    id: str = "htl-000",
    name: str = "Hotel Test",
    lat: float = 48.8566,
    lng: float = 2.3522,
) -> dict[str, Any]:
    return {
        "id": id,
        "name": name,
        "address": "Centre",
        "coordinates": {"lat": lat, "lng": lng},
        "stars": 4,
        "price_per_night": 150.0,
        "currency": "EUR",
        "amenities": ["wifi"],
        "reviews_score": 8.5,
        "distance_to_center_km": 0.5,
        "score": 0.9,
    }


def _mock_activity(
    *,
    id: str = "act-par-000",
    name: str = "Test Activity",
    category: str = "tour",
    lat: float = 48.860,
    lng: float = 2.337,
    duration_minutes: int = 120,
    price: float = 25.0,
    indoor: bool = False,
    score: float = 0.85,
    opening_hours: dict[str, str] | None = None,
) -> dict[str, Any]:
    return {
        "id": id,
        "name": name,
        "category": category,
        "address": "Test Address",
        "coordinates": {"lat": lat, "lng": lng},
        "duration_minutes": duration_minutes,
        "price": price,
        "currency": "EUR",
        "opening_hours": opening_hours or {
            "monday": "09:00-18:00",
            "tuesday": "09:00-18:00",
            "wednesday": "09:00-18:00",
            "thursday": "09:00-18:00",
            "friday": "09:00-18:00",
            "saturday": "09:00-18:00",
            "sunday": "09:00-18:00",
        },
        "requires_booking": False,
        "indoor": indoor,
        "description": "A test activity",
        "score": score,
    }


def _mock_activities(count: int = 6) -> list[dict[str, Any]]:
    """Diverse set of activities near central Paris."""
    cats = ["museum", "tour", "restaurant", "nature", "shopping", "nightlife"]
    locations = [
        (48.8606, 2.3376),  # Louvre area
        (48.8584, 2.2945),  # Eiffel area
        (48.8566, 2.3622),  # Marais
        (48.8462, 2.3372),  # Luxembourg
        (48.8735, 2.3322),  # Grands Boulevards
        (48.8842, 2.3323),  # Montmartre
    ]
    activities = []
    for i in range(count):
        lat, lng = locations[i % len(locations)]
        activities.append(
            _mock_activity(
                id=f"act-par-{i:03d}",
                name=f"Activity {chr(65 + i)}",
                category=cats[i % len(cats)],
                lat=lat,
                lng=lng,
                duration_minutes=90 + (i % 3) * 30,
                indoor=i % 2 == 0,
                score=round(0.95 - i * 0.05, 2),
            )
        )
    return activities


def _mock_forecast(date: str, rainy: bool = False) -> dict[str, Any]:
    return {
        "date": date,
        "condition": "rain" if rainy else "sunny",
        "temp_max": 22.0 if rainy else 28.0,
        "temp_min": 15.0 if rainy else 18.0,
        "rain_chance": 75.0 if rainy else 10.0,
        "rain_start": "14:00" if rainy else None,
        "wind_speed": 15.0,
    }


def _mock_destination_analysis(
    trip_dates: list[str],
    rainy_dates: set[str] | None = None,
) -> dict[str, Any]:
    rainy = rainy_dates or set()
    forecast = [_mock_forecast(d, d in rainy) for d in trip_dates]
    return {
        "forecast": forecast,
        "alerts": [],
        "weather_summary": {
            "avg_temp_max": 25.0,
            "avg_temp_min": 16.0,
            "avg_rain_chance": 30.0,
            "dominant_condition": "sunny",
            "severe_weather_days": 0,
            "packing_suggestions": [],
        },
        "seasonal_events": [],
        "travel_advisories": [],
        "analysis_timestamp": "2025-06-15T10:00:00Z",
    }


def _base_state(**overrides: Any) -> dict[str, Any]:
    activities = _mock_activities(6)
    trip_dates = [f"2025-07-{d:02d}" for d in range(1, 10)]
    state: dict[str, Any] = {
        "plan_id": "plan_test1234",
        "destination": "Paris",
        "dates": {"start_date": "2025-07-01", "end_date": "2025-07-10"},
        "budget": {"total": 5000.0, "currency": "EUR", "flexibility": 0.1},
        "traveler_profile": {
            "interests": ["culture", "food"],
            "pace": "moderate",
            "group_size": 2,
            "accommodation_type": "hotel",
        },
        "selected_flight_id": None,
        "selected_hotel_id": "htl-000",
        "selected_activity_ids": [a["id"] for a in activities],
        "current_cost": 2000.0,
        "revision_count": 0,
        "approval_status": "pending",
        "risk_flags": [],
        "alternative_plans": {},
        "destination_analysis": _mock_destination_analysis(trip_dates),
        "hotel_options": [_mock_hotel()],
        "activity_options": activities,
        "optimized_itinerary": None,
    }
    state.update(overrides)
    return state


def _valid_llm_response(activities: list[dict], trip_dates: list[str]) -> str:
    """Build a valid JSON response matching the expected itinerary schema."""
    days = []
    act_idx = 0
    for day_idx, date in enumerate(trip_dates):
        slots = []
        if act_idx < len(activities):
            act = activities[act_idx]
            slots.append({
                "activity_id": act["id"],
                "activity_name": act["name"],
                "start_time": "10:00",
                "end_time": "12:00",
                "travel_time_from_previous_minutes": 10,
                "notes": "",
            })
            act_idx += 1
        days.append({
            "date": date,
            "day_number": day_idx + 1,
            "theme": "Exploration",
            "slots": slots,
            "notes": "",
        })
    unscheduled = [a["id"] for a in activities[act_idx:]]
    return json.dumps({"days": days, "unscheduled_activity_ids": unscheduled})


def _mock_anthropic_client(response_text: str) -> AsyncMock:
    """Create a mock AsyncAnthropic returning the given text."""
    mock_content = MagicMock()
    mock_content.text = response_text

    mock_response = MagicMock()
    mock_response.content = [mock_content]

    mock_client = AsyncMock()
    mock_client.messages = MagicMock()
    mock_client.messages.create = AsyncMock(return_value=mock_response)
    return mock_client


# ===================================================================
# Resolve helpers
# ===================================================================


class TestResolveHelpers:
    def test_resolve_selected_activities_filters(self) -> None:
        state = _base_state(
            selected_activity_ids=["act-par-000", "act-par-002"],
        )
        result = _resolve_selected_activities(state)
        ids = [a["id"] for a in result]
        assert ids == ["act-par-000", "act-par-002"]

    def test_resolve_selected_activities_empty_ids_returns_all(self) -> None:
        state = _base_state(selected_activity_ids=[])
        result = _resolve_selected_activities(state)
        assert len(result) == 6

    def test_resolve_selected_hotel_found(self) -> None:
        state = _base_state()
        hotel = _resolve_selected_hotel(state)
        assert hotel is not None
        assert hotel["id"] == "htl-000"

    def test_resolve_selected_hotel_not_found(self) -> None:
        state = _base_state(selected_hotel_id="htl-999")
        hotel = _resolve_selected_hotel(state)
        assert hotel is None

    def test_resolve_selected_hotel_none_id(self) -> None:
        state = _base_state(selected_hotel_id=None)
        hotel = _resolve_selected_hotel(state)
        assert hotel is None

    def test_compute_trip_dates_multi_day(self) -> None:
        state = _base_state(dates={"start_date": "2025-07-01", "end_date": "2025-07-04"})
        dates = _compute_trip_dates(state)
        assert dates == ["2025-07-01", "2025-07-02", "2025-07-03"]

    def test_compute_trip_dates_same_day(self) -> None:
        state = _base_state(dates={"start_date": "2025-07-01", "end_date": "2025-07-01"})
        dates = _compute_trip_dates(state)
        assert dates == ["2025-07-01"]

    def test_build_forecast_map_with_analysis(self) -> None:
        state = _base_state()
        fm = _build_forecast_map(state)
        assert "2025-07-01" in fm
        assert fm["2025-07-01"]["condition"] in ("sunny", "rain")

    def test_build_forecast_map_no_analysis(self) -> None:
        state = _base_state(destination_analysis=None)
        fm = _build_forecast_map(state)
        assert fm == {}


# ===================================================================
# Pace mapping
# ===================================================================


class TestPaceMapping:
    def test_fast_pace(self) -> None:
        assert PACE_ACTIVITIES_PER_DAY["fast"] == 5

    def test_moderate_pace(self) -> None:
        assert PACE_ACTIVITIES_PER_DAY["moderate"] == 3

    def test_slow_pace(self) -> None:
        assert PACE_ACTIVITIES_PER_DAY["slow"] == 2

    def test_unknown_defaults_to_3(self) -> None:
        assert PACE_ACTIVITIES_PER_DAY.get("unknown", 3) == 3


# ===================================================================
# Nearest-neighbor sort
# ===================================================================


class TestNearestNeighborSort:
    def test_orders_by_proximity(self) -> None:
        hotel = _mock_hotel(lat=48.856, lng=2.352)
        far = _mock_activity(id="far", lat=48.900, lng=2.400)
        near = _mock_activity(id="near", lat=48.857, lng=2.353)
        result = _nearest_neighbor_sort([far, near], hotel)
        assert result[0]["id"] == "near"
        assert result[1]["id"] == "far"

    def test_empty_list(self) -> None:
        hotel = _mock_hotel()
        assert _nearest_neighbor_sort([], hotel) == []

    def test_single_activity(self) -> None:
        hotel = _mock_hotel()
        act = _mock_activity()
        result = _nearest_neighbor_sort([act], hotel)
        assert len(result) == 1


# ===================================================================
# Infer theme
# ===================================================================


class TestInferTheme:
    def test_museum_theme(self) -> None:
        lookup = {"a1": _mock_activity(id="a1", category="museum")}
        slots = [{"activity_id": "a1", "activity_name": "X", "start_time": "10:00",
                  "end_time": "12:00", "travel_time_from_previous_minutes": 0, "notes": ""}]
        assert _infer_theme(slots, lookup) == "Art & Culture"

    def test_mixed_categories(self) -> None:
        lookup = {
            "a1": _mock_activity(id="a1", category="tour"),
            "a2": _mock_activity(id="a2", category="tour"),
            "a3": _mock_activity(id="a3", category="museum"),
        }
        slots = [
            {"activity_id": "a1", "activity_name": "X", "start_time": "10:00",
             "end_time": "12:00", "travel_time_from_previous_minutes": 0, "notes": ""},
            {"activity_id": "a2", "activity_name": "Y", "start_time": "13:00",
             "end_time": "15:00", "travel_time_from_previous_minutes": 0, "notes": ""},
            {"activity_id": "a3", "activity_name": "Z", "start_time": "16:00",
             "end_time": "18:00", "travel_time_from_previous_minutes": 0, "notes": ""},
        ]
        assert _infer_theme(slots, lookup) == "City Exploration"

    def test_empty_slots_free_day(self) -> None:
        assert _infer_theme([], {}) == "Free Day"


# ===================================================================
# LLM response parsing
# ===================================================================


class TestParseLLMResponse:
    def test_parses_valid_json(self) -> None:
        activities = _mock_activities(2)
        dates = ["2025-07-01", "2025-07-02"]
        raw = _valid_llm_response(activities, dates)
        days, unscheduled = _parse_llm_response(raw, activities, dates, {})
        assert len(days) == 2
        assert days[0]["date"] == "2025-07-01"
        assert len(days[0]["slots"]) == 1

    def test_strips_markdown_fences(self) -> None:
        activities = _mock_activities(1)
        dates = ["2025-07-01"]
        raw = "```json\n" + _valid_llm_response(activities, dates) + "\n```"
        days, _ = _parse_llm_response(raw, activities, dates, {})
        assert len(days) == 1

    def test_raises_on_malformed_json(self) -> None:
        with pytest.raises(json.JSONDecodeError):
            _parse_llm_response("not json", [], [], {})

    def test_maps_weather_condition(self) -> None:
        activities = _mock_activities(1)
        dates = ["2025-07-01"]
        fm = {"2025-07-01": _mock_forecast("2025-07-01", rainy=True)}
        raw = _valid_llm_response(activities, dates)
        days, _ = _parse_llm_response(raw, activities, dates, fm)
        assert days[0]["weather_condition"] == "rain"


# ===================================================================
# Validate itinerary
# ===================================================================


class TestValidateItinerary:
    def test_valid_returns_no_issues(self) -> None:
        hotel = _mock_hotel()
        act = _mock_activity(id="a1", duration_minutes=120)
        days = [{
            "date": "2025-07-01",
            "day_number": 1,
            "theme": "Test",
            "slots": [{"activity_id": "a1", "activity_name": "X",
                        "start_time": "10:00", "end_time": "12:00",
                        "travel_time_from_previous_minutes": 0, "notes": ""}],
            "weather_condition": "sunny",
            "notes": "",
        }]
        issues = _validate_itinerary(days, hotel, {}, [act])
        # No errors expected (1 activity, open Tuesday July 1, near hotel)
        errors = [i for i in issues if i["severity"] == "error"]
        assert len(errors) == 0

    def test_timing_issue_too_many_activities(self) -> None:
        hotel = _mock_hotel()
        acts = [_mock_activity(id=f"a{i}") for i in range(8)]
        slots = [{"activity_id": f"a{i}", "activity_name": f"X{i}",
                  "start_time": "10:00", "end_time": "12:00",
                  "travel_time_from_previous_minutes": 0, "notes": ""} for i in range(8)]
        days = [{
            "date": "2025-07-01",
            "day_number": 1,
            "theme": "Test",
            "slots": slots,
            "weather_condition": "sunny",
            "notes": "",
        }]
        issues = _validate_itinerary(days, hotel, {}, acts)
        assert any("excede" in i for result in issues for i in result["issues"])

    def test_closed_activity_flagged(self) -> None:
        hotel = _mock_hotel()
        # Monday closed museum
        act = _mock_activity(
            id="a1",
            opening_hours={"monday": "closed", "tuesday": "10:00-18:00",
                           "wednesday": "10:00-18:00", "thursday": "10:00-18:00",
                           "friday": "10:00-18:00", "saturday": "10:00-18:00",
                           "sunday": "10:00-18:00"},
        )
        # 2025-07-07 is a Monday
        days = [{
            "date": "2025-07-07",
            "day_number": 7,
            "theme": "Test",
            "slots": [{"activity_id": "a1", "activity_name": "X",
                        "start_time": "10:00", "end_time": "12:00",
                        "travel_time_from_previous_minutes": 0, "notes": ""}],
            "weather_condition": "sunny",
            "notes": "",
        }]
        issues = _validate_itinerary(days, hotel, {}, [act])
        assert any("fechada" in i for result in issues for i in result["issues"])


# ===================================================================
# Deterministic fallback
# ===================================================================


class TestDeterministicFallback:
    def test_activities_grouped_by_day(self) -> None:
        activities = _mock_activities(6)
        hotel = _mock_hotel()
        dates = ["2025-07-01", "2025-07-02", "2025-07-03"]
        fm = {d: _mock_forecast(d) for d in dates}
        days, unscheduled = _deterministic_fallback(
            activities=activities, hotel=hotel, trip_dates=dates,
            forecast_map=fm, target_per_day=3,
        )
        assert len(days) == 3
        total_scheduled = sum(len(d["slots"]) for d in days)
        assert total_scheduled + len(unscheduled) <= 6

    def test_indoor_preferred_on_rainy_days(self) -> None:
        # All indoor + all outdoor activities
        indoor = [_mock_activity(id=f"in-{i}", indoor=True, score=0.8) for i in range(3)]
        outdoor = [_mock_activity(id=f"out-{i}", indoor=False, score=0.9) for i in range(3)]
        activities = indoor + outdoor
        hotel = _mock_hotel()
        dates = ["2025-07-01"]
        fm = {"2025-07-01": _mock_forecast("2025-07-01", rainy=True)}
        days, _ = _deterministic_fallback(
            activities=activities, hotel=hotel, trip_dates=dates,
            forecast_map=fm, target_per_day=3,
        )
        # On a rainy day, indoor pool is preferred first
        if days[0]["slots"]:
            first_id = days[0]["slots"][0]["activity_id"]
            first_act = next(a for a in activities if a["id"] == first_id)
            assert first_act["indoor"] is True

    def test_respects_opening_hours(self) -> None:
        # Activity closed on Tuesday (2025-07-01 is a Tuesday)
        closed_tue = _mock_activity(
            id="closed-tue",
            opening_hours={"tuesday": "closed", "wednesday": "09:00-18:00",
                           "monday": "09:00-18:00", "thursday": "09:00-18:00",
                           "friday": "09:00-18:00", "saturday": "09:00-18:00",
                           "sunday": "09:00-18:00"},
            score=0.99,
        )
        hotel = _mock_hotel()
        days, _ = _deterministic_fallback(
            activities=[closed_tue], hotel=hotel,
            trip_dates=["2025-07-01"],
            forecast_map={}, target_per_day=3,
        )
        # Should not schedule on Tuesday
        assert len(days[0]["slots"]) == 0

    def test_capped_at_target_per_day(self) -> None:
        activities = _mock_activities(10)
        hotel = _mock_hotel()
        days, _ = _deterministic_fallback(
            activities=activities, hotel=hotel,
            trip_dates=["2025-07-01"],
            forecast_map={}, target_per_day=2,
        )
        assert len(days[0]["slots"]) <= 2

    def test_empty_activities(self) -> None:
        hotel = _mock_hotel()
        days, unscheduled = _deterministic_fallback(
            activities=[], hotel=hotel,
            trip_dates=["2025-07-01"],
            forecast_map={}, target_per_day=3,
        )
        assert len(days) == 1
        assert days[0]["slots"] == []
        assert unscheduled == []

    def test_single_day_trip(self) -> None:
        activities = _mock_activities(3)
        hotel = _mock_hotel()
        days, _ = _deterministic_fallback(
            activities=activities, hotel=hotel,
            trip_dates=["2025-07-01"],
            forecast_map={}, target_per_day=3,
        )
        assert len(days) == 1

    def test_unscheduled_returned(self) -> None:
        activities = _mock_activities(10)
        hotel = _mock_hotel()
        days, unscheduled = _deterministic_fallback(
            activities=activities, hotel=hotel,
            trip_dates=["2025-07-01"],
            forecast_map={}, target_per_day=2,
        )
        # Only 2 should be scheduled, rest unscheduled
        scheduled = sum(len(d["slots"]) for d in days)
        assert scheduled + len(unscheduled) == 10

    def test_day_theme_assigned(self) -> None:
        activities = _mock_activities(3)
        hotel = _mock_hotel()
        days, _ = _deterministic_fallback(
            activities=activities, hotel=hotel,
            trip_dates=["2025-07-01"],
            forecast_map={}, target_per_day=3,
        )
        assert days[0]["theme"] != ""


# ===================================================================
# Repair prompt
# ===================================================================


class TestRepairPrompt:
    def test_includes_issues(self) -> None:
        issues = [{
            "is_valid": False,
            "issues": ["Day 1: Too many activities"],
            "severity": "error",
            "suggested_fixes": ["Move activities to other days"],
        }]
        prompt = _build_repair_prompt(issues)
        assert "Too many activities" in prompt
        assert "Move activities" in prompt

    def test_includes_severity(self) -> None:
        issues = [{
            "is_valid": False,
            "issues": ["Some issue"],
            "severity": "warning",
            "suggested_fixes": [],
        }]
        prompt = _build_repair_prompt(issues)
        assert "[WARNING]" in prompt


# ===================================================================
# Node integration (mocked LLM)
# ===================================================================


class TestNodeIntegration:
    @patch("travel_orchestrator.graph.nodes.optimize_itinerary._get_anthropic_client")
    async def test_full_flow_with_llm(self, mock_get_client: MagicMock) -> None:
        state = _base_state()
        activities = state["activity_options"]
        trip_dates = _compute_trip_dates(state)
        response = _valid_llm_response(activities, trip_dates)
        mock_get_client.return_value = _mock_anthropic_client(response)

        result = await optimize_itinerary_node(state)
        itinerary = result["optimized_itinerary"]
        assert itinerary is not None
        assert itinerary["optimization_method"] == "llm"
        assert len(itinerary["days"]) > 0

    @patch("travel_orchestrator.graph.nodes.optimize_itinerary._get_anthropic_client")
    async def test_fallback_when_no_client(self, mock_get_client: MagicMock) -> None:
        mock_get_client.return_value = None
        state = _base_state()
        result = await optimize_itinerary_node(state)
        itinerary = result["optimized_itinerary"]
        assert itinerary is not None
        assert itinerary["optimization_method"] == "deterministic_fallback"

    @patch("travel_orchestrator.graph.nodes.optimize_itinerary._get_anthropic_client")
    async def test_fallback_when_llm_raises(self, mock_get_client: MagicMock) -> None:
        mock_client = AsyncMock()
        mock_client.messages = MagicMock()
        mock_client.messages.create = AsyncMock(side_effect=RuntimeError("API down"))
        mock_get_client.return_value = mock_client

        state = _base_state()
        result = await optimize_itinerary_node(state)
        itinerary = result["optimized_itinerary"]
        assert itinerary["optimization_method"] == "deterministic_fallback"

    @patch("travel_orchestrator.graph.nodes.optimize_itinerary._get_anthropic_client")
    async def test_no_activities_empty(self, mock_get_client: MagicMock) -> None:
        mock_get_client.return_value = None
        state = _base_state(activity_options=[], selected_activity_ids=[])
        result = await optimize_itinerary_node(state)
        assert result["optimized_itinerary"]["days"] == []
        assert result["optimized_itinerary"]["optimization_method"] == "none"

    @patch("travel_orchestrator.graph.nodes.optimize_itinerary._get_anthropic_client")
    async def test_no_hotel_empty(self, mock_get_client: MagicMock) -> None:
        mock_get_client.return_value = None
        state = _base_state(selected_hotel_id=None, hotel_options=[])
        result = await optimize_itinerary_node(state)
        assert result["optimized_itinerary"]["optimization_method"] == "none"

    @patch("travel_orchestrator.graph.nodes.optimize_itinerary._get_anthropic_client")
    async def test_preserves_existing_state(self, mock_get_client: MagicMock) -> None:
        mock_get_client.return_value = None
        state = _base_state(plan_id="plan_keep", approval_status="pending")
        result = await optimize_itinerary_node(state)
        assert result["plan_id"] == "plan_keep"
        assert result["approval_status"] == "pending"
        assert result["current_cost"] == 2000.0

    @patch("travel_orchestrator.graph.nodes.optimize_itinerary._get_anthropic_client")
    async def test_output_structure(self, mock_get_client: MagicMock) -> None:
        mock_get_client.return_value = None
        state = _base_state()
        result = await optimize_itinerary_node(state)
        itinerary = result["optimized_itinerary"]
        assert "days" in itinerary
        assert "unscheduled_activity_ids" in itinerary
        assert "optimization_method" in itinerary
        assert "validation_iterations" in itinerary
        assert "validation_warnings" in itinerary


# ===================================================================
# LLM loop (mocked)
# ===================================================================


class TestLLMLoop:
    @patch("travel_orchestrator.graph.nodes.optimize_itinerary._get_anthropic_client")
    @patch("travel_orchestrator.graph.nodes.optimize_itinerary._get_settings_safe")
    async def test_valid_on_first_attempt(
        self, mock_settings: MagicMock, mock_get_client: MagicMock,
    ) -> None:
        mock_settings.return_value = {"model_name": "test", "temperature": 0.3, "max_tokens": 4096}
        state = _base_state()
        activities = state["activity_options"]
        trip_dates = _compute_trip_dates(state)
        response = _valid_llm_response(activities, trip_dates)
        mock_get_client.return_value = _mock_anthropic_client(response)

        result = await optimize_itinerary_node(state)
        assert result["optimized_itinerary"]["optimization_method"] == "llm"
        assert result["optimized_itinerary"]["validation_iterations"] >= 1

    @patch("travel_orchestrator.graph.nodes.optimize_itinerary._get_anthropic_client")
    @patch("travel_orchestrator.graph.nodes.optimize_itinerary._get_settings_safe")
    async def test_max_iterations_exhausted(
        self, mock_settings: MagicMock, mock_get_client: MagicMock,
    ) -> None:
        """If LLM always returns invalid, max iterations reached, falls back or returns last."""
        mock_settings.return_value = {"model_name": "test", "temperature": 0.3, "max_tokens": 4096}
        # Return an itinerary with 8 activities on one day (triggers timing error)
        activities = [_mock_activity(id=f"a{i}") for i in range(8)]
        state = _base_state(
            activity_options=activities,
            selected_activity_ids=[f"a{i}" for i in range(8)],
        )
        trip_dates = _compute_trip_dates(state)

        # Build response that puts all 8 on day 1
        bad_day = {
            "date": trip_dates[0],
            "day_number": 1,
            "theme": "Packed",
            "slots": [
                {"activity_id": f"a{i}", "activity_name": f"Act {i}",
                 "start_time": "10:00", "end_time": "12:00",
                 "travel_time_from_previous_minutes": 0, "notes": ""}
                for i in range(8)
            ],
            "notes": "",
        }
        bad_response = json.dumps({"days": [bad_day], "unscheduled_activity_ids": []})
        mock_get_client.return_value = _mock_anthropic_client(bad_response)

        result = await optimize_itinerary_node(state)
        itinerary = result["optimized_itinerary"]
        assert itinerary["validation_iterations"] == MAX_OPTIMIZATION_ITERATIONS


# ===================================================================
# Collect warnings
# ===================================================================


class TestCollectWarnings:
    def test_empty_day_warned(self) -> None:
        days = [{"date": "2025-07-01", "day_number": 1, "theme": "Free",
                 "slots": [], "weather_condition": "sunny", "notes": ""}]
        warnings = _collect_final_warnings(days)
        assert len(warnings) == 1
        assert "no scheduled activities" in warnings[0]

    def test_no_warnings_for_filled_days(self) -> None:
        days = [{
            "date": "2025-07-01", "day_number": 1, "theme": "Test",
            "slots": [{"activity_id": "a1", "activity_name": "X",
                        "start_time": "10:00", "end_time": "12:00",
                        "travel_time_from_previous_minutes": 0, "notes": ""}],
            "weather_condition": "sunny", "notes": "",
        }]
        warnings = _collect_final_warnings(days)
        assert len(warnings) == 0


# ===================================================================
# Graph integration
# ===================================================================


class TestGraphIntegration:
    async def test_node_runs_inside_graph(self) -> None:
        """Verify the real node works when invoked via the compiled graph."""
        from travel_orchestrator.graph.planner_graph import compile_graph

        compiled = compile_graph()
        initial_state: dict[str, Any] = {
            "plan_id": "",
            "destination": "Paris",
            "dates": {"start_date": "2025-07-01", "end_date": "2025-07-10"},
            "budget": {"total": 5000.0, "currency": "EUR", "flexibility": 0.1},
            "traveler_profile": {},
            "selected_flight_id": None,
            "selected_hotel_id": None,
            "selected_activity_ids": [],
            "current_cost": 0.0,
            "revision_count": 0,
            "approval_status": "pending",
            "risk_flags": [],
            "alternative_plans": {},
            "destination_analysis": None,
            "hotel_options": [],
            "activity_options": [],
            "optimized_itinerary": None,
        }
        config = {"configurable": {"thread_id": "test-optimize-itinerary"}}
        result = await compiled.ainvoke(initial_state, config=config)

        assert "optimized_itinerary" in result
        itinerary = result["optimized_itinerary"]
        assert itinerary is not None
        assert isinstance(itinerary["days"], list)
