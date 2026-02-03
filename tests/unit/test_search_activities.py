"""Unit tests for the search_activities graph node."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from travel_orchestrator.graph.nodes.search_activities import (
    _ACTIVITY_BUDGET_RATIO,
    _MAX_ACTIVITIES,
    _TARGET_ACTIVITIES,
    _compute_indoor_ratio,
    _select_activities,
    _to_activity,
    _trim_to_budget,
    search_activities_node,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _base_state(**overrides: Any) -> dict[str, Any]:
    """Return a minimal valid state as produced by earlier nodes."""
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
        "selected_activity_ids": [],
        "current_cost": 1500.0,  # from flight + hotel
        "revision_count": 0,
        "approval_status": "pending",
        "risk_flags": [],
        "alternative_plans": {},
        "destination_analysis": None,
        "hotel_options": [],
        "activity_options": [],
    }
    state.update(overrides)
    return state


def _mock_activity(
    *,
    id: str = "act-par-000",
    name: str = "Test Activity",
    category: str = "tour",
    price: float = 25.0,
    currency: str = "EUR",
    indoor: bool = False,
    score: float = 0.85,
    duration_minutes: int = 120,
) -> dict[str, Any]:
    """Build a single activity result as returned by the MCP server."""
    return {
        "id": id,
        "name": name,
        "category": category,
        "address": "Test Address",
        "coordinates": {"lat": 48.856, "lng": 2.352},
        "duration_minutes": duration_minutes,
        "price": price,
        "currency": currency,
        "opening_hours": {"monday": "09:00-18:00"},
        "requires_booking": False,
        "indoor": indoor,
        "description": "A test activity",
        "score": score,
    }


def _mock_activities_list(
    count: int = 10,
    indoor_ratio: float = 0.3,
) -> list[dict[str, Any]]:
    """Build a list of mock activities with mixed indoor/outdoor."""
    categories = ["tour", "museum", "restaurant", "nature", "shopping", "nightlife"]
    activities = []
    for i in range(count):
        is_indoor = i < int(count * indoor_ratio)
        activities.append(
            _mock_activity(
                id=f"act-par-{i:03d}",
                name=f"Activity {chr(65 + i)}",
                category=categories[i % len(categories)],
                price=10.0 + i * 5,
                indoor=is_indoor,
                score=round(0.95 - i * 0.03, 2),
            )
        )
    return activities


def _forecast_rainy(days: int = 9) -> dict[str, Any]:
    """Build a destination_analysis with rainy forecast."""
    forecast = []
    for i in range(days):
        forecast.append({
            "date": f"2025-07-{i + 1:02d}",
            "condition": "rain" if i % 2 == 0 else "cloudy",
            "temp_max": 22.0,
            "temp_min": 15.0,
            "rain_chance": 70.0 if i % 2 == 0 else 30.0,
            "rain_start": "14:00" if i % 2 == 0 else None,
            "wind_speed": 15.0,
        })
    return {
        "forecast": forecast,
        "alerts": [],
        "weather_summary": {
            "avg_temp_max": 22.0,
            "avg_temp_min": 15.0,
            "avg_rain_chance": 50.0,
            "dominant_condition": "rain",
            "severe_weather_days": 0,
            "packing_suggestions": ["umbrella"],
        },
        "seasonal_events": [],
        "travel_advisories": [],
        "analysis_timestamp": "2025-06-15T10:00:00Z",
    }


def _forecast_sunny(days: int = 9) -> dict[str, Any]:
    """Build a destination_analysis with sunny forecast."""
    forecast = []
    for i in range(days):
        forecast.append({
            "date": f"2025-07-{i + 1:02d}",
            "condition": "sunny",
            "temp_max": 30.0,
            "temp_min": 20.0,
            "rain_chance": 10.0,
            "rain_start": None,
            "wind_speed": 8.0,
        })
    return {
        "forecast": forecast,
        "alerts": [],
        "weather_summary": {
            "avg_temp_max": 30.0,
            "avg_temp_min": 20.0,
            "avg_rain_chance": 10.0,
            "dominant_condition": "sunny",
            "severe_weather_days": 0,
            "packing_suggestions": ["sunscreen"],
        },
        "seasonal_events": [],
        "travel_advisories": [],
        "analysis_timestamp": "2025-06-15T10:00:00Z",
    }


# ===================================================================
# Budget computation
# ===================================================================


class TestBudgetComputation:
    async def test_activity_budget_is_20_percent(self) -> None:
        activities = [_mock_activity(price=10.0)]
        state = _base_state(
            budget={"total": 10000.0, "currency": "EUR", "flexibility": 0.1}
        )
        with patch(
            "travel_orchestrator.graph.nodes.search_activities.discover_activities",
            new_callable=AsyncMock,
            return_value=activities,
        ):
            result = await search_activities_node(state)
        # 10000 * 0.20 = 2000, 10.0 fits within
        assert len(result["activity_options"]) == 1

    async def test_over_budget_activities_trimmed(self) -> None:
        """Activities exceeding 120% of budget get trimmed."""
        # Budget: 5000 total, 20% = 1000, 120% = 1200
        expensive = [
            _mock_activity(id=f"act-{i}", price=200.0, score=0.9 - i * 0.1)
            for i in range(10)
        ]
        state = _base_state()
        with patch(
            "travel_orchestrator.graph.nodes.search_activities.discover_activities",
            new_callable=AsyncMock,
            return_value=expensive,
        ):
            result = await search_activities_node(state)
        total_cost = sum(a["price"] for a in result["activity_options"])
        # Should be trimmed to <= 1200 (activity_budget * 1.2)
        assert total_cost <= 1000.0 * 1.2


# ===================================================================
# Indoor/outdoor weather balance
# ===================================================================


class TestIndoorOutdoorBalance:
    def test_rainy_forecast_high_indoor_ratio(self) -> None:
        state = _base_state(destination_analysis=_forecast_rainy())
        ratio = _compute_indoor_ratio(state)
        # 5 out of 9 days rainy → ~0.56
        assert ratio > 0.4

    def test_sunny_forecast_low_indoor_ratio(self) -> None:
        state = _base_state(destination_analysis=_forecast_sunny())
        ratio = _compute_indoor_ratio(state)
        # 0 rainy days → 0.0, clamped to MIN_INDOOR_RATIO = 0.20
        assert ratio == pytest.approx(0.20)

    def test_no_forecast_balanced(self) -> None:
        state = _base_state(destination_analysis=None)
        ratio = _compute_indoor_ratio(state)
        assert ratio == 0.5

    def test_empty_forecast_balanced(self) -> None:
        state = _base_state(
            destination_analysis={
                "forecast": [],
                "alerts": [],
                "weather_summary": {},
                "seasonal_events": [],
                "travel_advisories": [],
                "analysis_timestamp": "",
            }
        )
        ratio = _compute_indoor_ratio(state)
        assert ratio == 0.5

    def test_ratio_clamped_high(self) -> None:
        """Even if all days are rainy, ratio is clamped to 0.80 max."""
        all_rainy = _forecast_rainy()
        for day in all_rainy["forecast"]:
            day["rain_chance"] = 90.0
        state = _base_state(destination_analysis=all_rainy)
        ratio = _compute_indoor_ratio(state)
        assert ratio <= 0.80

    def test_ratio_clamped_low(self) -> None:
        """Even if all days are sunny, ratio is at least 0.20."""
        state = _base_state(destination_analysis=_forecast_sunny())
        ratio = _compute_indoor_ratio(state)
        assert ratio >= 0.20


# ===================================================================
# Activity selection & diversity
# ===================================================================


class TestActivitySelection:
    def test_selects_up_to_target(self) -> None:
        activities = _mock_activities_list(count=20)
        selected = _select_activities(activities, 15, 0.5, 200.0)
        assert len(selected) <= 15

    def test_indoor_outdoor_balance(self) -> None:
        activities = _mock_activities_list(count=20, indoor_ratio=0.5)
        selected = _select_activities(activities, 10, 0.6, 200.0)
        indoor = [a for a in selected if a["indoor"]]
        outdoor = [a for a in selected if not a["indoor"]]
        # With 0.6 indoor ratio and 10 target, should get ~6 indoor, ~4 outdoor
        assert len(indoor) >= 1
        assert len(outdoor) >= 1

    def test_category_diversity(self) -> None:
        # All same category
        same_cat = [
            _mock_activity(id=f"act-{i}", category="museum", score=0.9 - i * 0.01)
            for i in range(20)
        ]
        selected = _select_activities(same_cat, 10, 0.5, 200.0)
        # max_per_category = max(10 // 3, 2) = 3
        assert len(selected) <= 10

    def test_empty_input(self) -> None:
        selected = _select_activities([], 15, 0.5, 200.0)
        assert selected == []


# ===================================================================
# _to_activity helper
# ===================================================================


class TestToActivity:
    def test_maps_all_fields(self) -> None:
        raw = _mock_activity(
            name="Grand Tour",
            category="tour",
            price=50.0,
            currency="EUR",
            indoor=False,
            score=0.92,
        )
        activity = _to_activity(raw)
        assert activity["id"] == "act-par-000"
        assert activity["name"] == "Grand Tour"
        assert activity["category"] == "tour"
        assert activity["price"] == 50.0
        assert activity["currency"] == "EUR"
        assert activity["indoor"] is False
        assert activity["score"] == 0.92

    def test_handles_missing_fields(self) -> None:
        raw: dict[str, Any] = {"name": "Minimal", "score": 0.5}
        activity = _to_activity(raw)
        assert activity["id"] == "act-unknown"
        assert activity["name"] == "Minimal"
        assert activity["price"] == 0.0
        assert activity["category"] == "other"


# ===================================================================
# _trim_to_budget helper
# ===================================================================


class TestTrimToBudget:
    def test_trims_cheapest_by_score(self) -> None:
        activities = [
            _to_activity(_mock_activity(id=f"act-{i}", price=100.0, score=0.5 + i * 0.1))
            for i in range(5)
        ]
        # Total = 500, max = 300
        trimmed, cost = _trim_to_budget(activities, 300.0)
        assert cost <= 300.0
        # Should keep higher-scored ones
        assert all(a["score"] >= 0.7 for a in trimmed)

    def test_no_trim_needed(self) -> None:
        activities = [
            _to_activity(_mock_activity(id=f"act-{i}", price=10.0))
            for i in range(3)
        ]
        trimmed, cost = _trim_to_budget(activities, 1000.0)
        assert len(trimmed) == 3
        assert cost == 30.0

    def test_empty_list(self) -> None:
        trimmed, cost = _trim_to_budget([], 100.0)
        assert trimmed == []
        assert cost == 0.0


# ===================================================================
# Node integration (mocked server)
# ===================================================================


class TestNodeIntegration:
    async def test_full_flow(self) -> None:
        activities = _mock_activities_list(count=20)
        state = _base_state(destination_analysis=_forecast_sunny())
        with patch(
            "travel_orchestrator.graph.nodes.search_activities.discover_activities",
            new_callable=AsyncMock,
            return_value=activities,
        ):
            result = await search_activities_node(state)
        assert len(result["activity_options"]) > 0
        assert len(result["selected_activity_ids"]) == len(result["activity_options"])
        assert result["current_cost"] >= 1500.0  # includes prior cost

    async def test_no_results_preserves_state(self) -> None:
        state = _base_state(current_cost=1500.0)
        with patch(
            "travel_orchestrator.graph.nodes.search_activities.discover_activities",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await search_activities_node(state)
        assert result["activity_options"] == []
        assert result["selected_activity_ids"] == []
        assert result["current_cost"] == 1500.0

    async def test_search_failure_graceful(self) -> None:
        state = _base_state()
        with patch(
            "travel_orchestrator.graph.nodes.search_activities.discover_activities",
            new_callable=AsyncMock,
            side_effect=RuntimeError("upstream down"),
        ):
            result = await search_activities_node(state)
        assert result["activity_options"] == []
        assert result["selected_activity_ids"] == []

    async def test_preserves_existing_state(self) -> None:
        activities = [_mock_activity()]
        state = _base_state(plan_id="plan_keep", approval_status="pending")
        with patch(
            "travel_orchestrator.graph.nodes.search_activities.discover_activities",
            new_callable=AsyncMock,
            return_value=activities,
        ):
            result = await search_activities_node(state)
        assert result["plan_id"] == "plan_keep"
        assert result["approval_status"] == "pending"

    async def test_interests_from_profile(self) -> None:
        state = _base_state(
            traveler_profile={
                "interests": ["history", "art"],
                "pace": "fast",
                "group_size": 1,
                "accommodation_type": "hotel",
            }
        )
        with patch(
            "travel_orchestrator.graph.nodes.search_activities.discover_activities",
            new_callable=AsyncMock,
            return_value=[],
        ) as mock_discover:
            await search_activities_node(state)
        _, kwargs = mock_discover.call_args
        assert kwargs["interests"] == ["history", "art"]

    async def test_default_interests_when_empty(self) -> None:
        state = _base_state(
            traveler_profile={
                "interests": [],
                "pace": "moderate",
                "group_size": 1,
                "accommodation_type": "hotel",
            }
        )
        with patch(
            "travel_orchestrator.graph.nodes.search_activities.discover_activities",
            new_callable=AsyncMock,
            return_value=[],
        ) as mock_discover:
            await search_activities_node(state)
        _, kwargs = mock_discover.call_args
        assert kwargs["interests"] == ["culture", "food"]


# ===================================================================
# Constants sanity checks
# ===================================================================


class TestConstants:
    def test_budget_ratio(self) -> None:
        assert _ACTIVITY_BUDGET_RATIO == 0.20

    def test_target_activities(self) -> None:
        assert _TARGET_ACTIVITIES == 15

    def test_max_activities(self) -> None:
        assert _MAX_ACTIVITIES == 20


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
        }
        config = {"configurable": {"thread_id": "test-search-activities"}}
        result = await compiled.ainvoke(initial_state, config=config)

        assert "activity_options" in result
        assert isinstance(result["activity_options"], list)
        assert len(result["activity_options"]) > 0
        assert len(result["selected_activity_ids"]) > 0
        assert result["current_cost"] > 0.0
