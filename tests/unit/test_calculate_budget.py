"""Unit tests for the calculate_budget graph node."""

from __future__ import annotations

from typing import Any

import pytest

from travel_orchestrator.graph.nodes.calculate_budget import (
    _compute_activity_cost,
    _compute_flight_cost,
    _compute_hotel_cost,
    _compute_nights,
    calculate_budget_node,
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
    state.update(overrides)
    return state


def _hotel(
    *,
    id: str = "htl-000",
    price_per_night: float = 150.0,
    **kwargs: Any,
) -> dict[str, Any]:
    """Build a HotelOption dict."""
    return {
        "id": id,
        "name": kwargs.get("name", "Hotel Test"),
        "address": "Centre",
        "coordinates": {"lat": 48.856, "lng": 2.352},
        "stars": 4,
        "price_per_night": price_per_night,
        "currency": "EUR",
        "amenities": ["wifi"],
        "reviews_score": 8.5,
        "distance_to_center_km": 1.0,
        "score": 0.85,
    }


def _activity(
    *,
    id: str = "act-001",
    price: float = 25.0,
    **kwargs: Any,
) -> dict[str, Any]:
    """Build an Activity dict."""
    return {
        "id": id,
        "name": kwargs.get("name", "Museum Visit"),
        "category": "culture",
        "address": "Rue de Rivoli",
        "coordinates": {"lat": 48.86, "lng": 2.34},
        "duration_minutes": 120,
        "price": price,
        "currency": "EUR",
        "opening_hours": {},
        "requires_booking": False,
        "indoor": True,
        "description": "A museum",
        "score": 0.8,
    }


def _flight(
    *,
    id: str = "flt-001",
    price: float = 350.0,
) -> dict[str, Any]:
    """Build a FlightOption dict."""
    return {
        "id": id,
        "airline": "Air France",
        "departure_time": "2025-07-01T08:00",
        "arrival_time": "2025-07-01T10:00",
        "duration_minutes": 120,
        "price": price,
        "currency": "EUR",
        "stops": 0,
        "booking_class": "economy",
        "carbon_footprint_kg": 150.0,
        "score": 0.9,
    }


# ===================================================================
# _compute_nights
# ===================================================================


class TestComputeNights:
    def test_multi_day_trip(self) -> None:
        state = _base_state(dates={"start_date": "2025-07-01", "end_date": "2025-07-10"})
        assert _compute_nights(state) == 9

    def test_single_day_trip(self) -> None:
        state = _base_state(dates={"start_date": "2025-07-01", "end_date": "2025-07-01"})
        assert _compute_nights(state) == 1  # minimum 1

    def test_missing_dates(self) -> None:
        state = _base_state(dates={})
        assert _compute_nights(state) == 1

    def test_invalid_dates(self) -> None:
        state = _base_state(dates={"start_date": "bad", "end_date": "bad"})
        assert _compute_nights(state) == 1


# ===================================================================
# _compute_hotel_cost
# ===================================================================


class TestComputeHotelCost:
    def test_with_selected_hotel(self) -> None:
        hotel = _hotel(price_per_night=150.0)
        state = _base_state(
            selected_hotel_id="htl-000",
            hotel_options=[hotel],
        )
        # 9 nights * 150 = 1350
        assert _compute_hotel_cost(state) == 1350.0

    def test_no_selected_hotel(self) -> None:
        state = _base_state(selected_hotel_id=None, hotel_options=[_hotel()])
        assert _compute_hotel_cost(state) == 0.0

    def test_hotel_not_found_in_options(self) -> None:
        state = _base_state(
            selected_hotel_id="htl-999",
            hotel_options=[_hotel(id="htl-000")],
        )
        assert _compute_hotel_cost(state) == 0.0

    def test_empty_hotel_options(self) -> None:
        state = _base_state(selected_hotel_id="htl-000", hotel_options=[])
        assert _compute_hotel_cost(state) == 0.0


# ===================================================================
# _compute_activity_cost
# ===================================================================


class TestComputeActivityCost:
    def test_with_selected_activities(self) -> None:
        activities = [
            _activity(id="act-001", price=25.0),
            _activity(id="act-002", price=40.0),
            _activity(id="act-003", price=15.0),
        ]
        state = _base_state(
            selected_activity_ids=["act-001", "act-003"],
            activity_options=activities,
        )
        # 25 + 15 = 40
        assert _compute_activity_cost(state) == 40.0

    def test_no_selected_activities(self) -> None:
        state = _base_state(
            selected_activity_ids=[],
            activity_options=[_activity()],
        )
        assert _compute_activity_cost(state) == 0.0

    def test_selected_id_not_in_options(self) -> None:
        state = _base_state(
            selected_activity_ids=["act-999"],
            activity_options=[_activity(id="act-001")],
        )
        assert _compute_activity_cost(state) == 0.0

    def test_all_activities_selected(self) -> None:
        activities = [
            _activity(id="act-001", price=10.0),
            _activity(id="act-002", price=20.0),
        ]
        state = _base_state(
            selected_activity_ids=["act-001", "act-002"],
            activity_options=activities,
        )
        assert _compute_activity_cost(state) == 30.0


# ===================================================================
# _compute_flight_cost
# ===================================================================


class TestComputeFlightCost:
    def test_with_selected_flight(self) -> None:
        flight = _flight(id="flt-001", price=350.0)
        state = _base_state(
            selected_flight_id="flt-001",
            traveler_profile={"group_size": 2, "pace": "moderate", "interests": []},
        )
        state["flight_options"] = [flight]
        # 350 * 2 = 700
        assert _compute_flight_cost(state) == 700.0

    def test_no_selected_flight(self) -> None:
        state = _base_state(selected_flight_id=None)
        assert _compute_flight_cost(state) == 0.0

    def test_no_flight_options_field(self) -> None:
        """When flight_options isn't on state yet (search_flights is a stub)."""
        state = _base_state(selected_flight_id="flt-001")
        assert _compute_flight_cost(state) == 0.0

    def test_flight_not_found_in_options(self) -> None:
        state = _base_state(selected_flight_id="flt-999")
        state["flight_options"] = [_flight(id="flt-001")]
        assert _compute_flight_cost(state) == 0.0

    def test_group_size_multiplier(self) -> None:
        flight = _flight(id="flt-001", price=200.0)
        state = _base_state(
            selected_flight_id="flt-001",
            traveler_profile={"group_size": 4, "pace": "moderate", "interests": []},
        )
        state["flight_options"] = [flight]
        assert _compute_flight_cost(state) == 800.0

    def test_default_group_size_is_1(self) -> None:
        flight = _flight(id="flt-001", price=300.0)
        state = _base_state(
            selected_flight_id="flt-001",
            traveler_profile={"pace": "moderate", "interests": []},
        )
        state["flight_options"] = [flight]
        assert _compute_flight_cost(state) == 300.0


# ===================================================================
# Full node: cost recalculation
# ===================================================================


class TestNodeCostRecalculation:
    async def test_recalculates_from_scratch(self) -> None:
        """The node should ignore the existing current_cost and recalculate."""
        hotel = _hotel(price_per_night=100.0)
        activities = [_activity(id="act-001", price=30.0)]
        state = _base_state(
            current_cost=9999.0,  # stale value from previous iteration
            selected_hotel_id="htl-000",
            hotel_options=[hotel],
            selected_activity_ids=["act-001"],
            activity_options=activities,
        )
        result = await calculate_budget_node(state)
        # Hotel: 100 * 9 nights = 900, Activities: 30, Total: 930
        assert result["current_cost"] == 930.0

    async def test_hotel_plus_activities(self) -> None:
        hotel = _hotel(price_per_night=200.0)
        activities = [
            _activity(id="act-001", price=25.0),
            _activity(id="act-002", price=50.0),
        ]
        state = _base_state(
            selected_hotel_id="htl-000",
            hotel_options=[hotel],
            selected_activity_ids=["act-001", "act-002"],
            activity_options=activities,
        )
        result = await calculate_budget_node(state)
        # Hotel: 200 * 9 = 1800, Activities: 75, Total: 1875
        assert result["current_cost"] == 1875.0

    async def test_no_services_selected(self) -> None:
        state = _base_state()
        result = await calculate_budget_node(state)
        assert result["current_cost"] == 0.0

    async def test_only_hotel(self) -> None:
        hotel = _hotel(price_per_night=120.0)
        state = _base_state(
            selected_hotel_id="htl-000",
            hotel_options=[hotel],
        )
        result = await calculate_budget_node(state)
        # 120 * 9 = 1080
        assert result["current_cost"] == 1080.0

    async def test_only_activities(self) -> None:
        activities = [
            _activity(id="act-001", price=50.0),
            _activity(id="act-002", price=30.0),
        ]
        state = _base_state(
            selected_activity_ids=["act-001", "act-002"],
            activity_options=activities,
        )
        result = await calculate_budget_node(state)
        assert result["current_cost"] == 80.0

    async def test_with_flight(self) -> None:
        flight = _flight(id="flt-001", price=400.0)
        hotel = _hotel(price_per_night=100.0)
        state = _base_state(
            selected_flight_id="flt-001",
            selected_hotel_id="htl-000",
            hotel_options=[hotel],
            traveler_profile={"group_size": 2, "pace": "moderate", "interests": []},
        )
        state["flight_options"] = [flight]
        result = await calculate_budget_node(state)
        # Flight: 400*2=800, Hotel: 100*9=900, Activities: 0, Total: 1700
        assert result["current_cost"] == 1700.0


# ===================================================================
# Budget validation & risk flags
# ===================================================================


class TestBudgetValidation:
    async def test_within_budget_no_flags(self) -> None:
        """Cost well within budget → no risk flags."""
        hotel = _hotel(price_per_night=100.0)
        state = _base_state(
            budget={"total": 5000.0, "currency": "EUR", "flexibility": 0.1},
            selected_hotel_id="htl-000",
            hotel_options=[hotel],
        )
        result = await calculate_budget_node(state)
        # 100*9 = 900, well under 5000
        budget_flags = [f for f in result["risk_flags"] if f.startswith("budget:")]
        assert len(budget_flags) == 0

    async def test_over_budget_adds_flag(self) -> None:
        """Cost exceeding budget → risk flag added."""
        hotel = _hotel(price_per_night=600.0)
        state = _base_state(
            budget={"total": 3000.0, "currency": "EUR", "flexibility": 0.1},
            selected_hotel_id="htl-000",
            hotel_options=[hotel],
        )
        result = await calculate_budget_node(state)
        # 600*9 = 5400, exceeds 3000
        budget_flags = [f for f in result["risk_flags"] if f.startswith("budget:")]
        assert len(budget_flags) > 0
        assert any("excede" in f for f in budget_flags)

    async def test_near_budget_warning_flag(self) -> None:
        """Cost close to budget limit → warning flag."""
        # Budget: 1000, cost should be > 900 (90% threshold) but <= 1000
        hotel = _hotel(price_per_night=105.0)  # 105*9 = 945
        state = _base_state(
            budget={"total": 1000.0, "currency": "EUR", "flexibility": 0.1},
            selected_hotel_id="htl-000",
            hotel_options=[hotel],
        )
        result = await calculate_budget_node(state)
        # 945 < 1000 but > 900 (margin) → warning
        budget_flags = [f for f in result["risk_flags"] if f.startswith("budget:")]
        assert len(budget_flags) > 0
        assert any("margem" in f.lower() or "próximo" in f.lower() for f in budget_flags)

    async def test_stale_budget_flags_cleared(self) -> None:
        """Previous budget flags should be replaced, not accumulated."""
        hotel = _hotel(price_per_night=50.0)  # 50*9 = 450
        state = _base_state(
            budget={"total": 5000.0, "currency": "EUR", "flexibility": 0.1},
            risk_flags=["budget: old stale flag", "other: keep this"],
            selected_hotel_id="htl-000",
            hotel_options=[hotel],
        )
        result = await calculate_budget_node(state)
        assert "budget: old stale flag" not in result["risk_flags"]
        assert "other: keep this" in result["risk_flags"]

    async def test_non_budget_flags_preserved(self) -> None:
        """Non-budget risk flags should not be removed."""
        state = _base_state(
            risk_flags=["weather: rain expected", "policy: visa required"],
        )
        result = await calculate_budget_node(state)
        assert "weather: rain expected" in result["risk_flags"]
        assert "policy: visa required" in result["risk_flags"]


# ===================================================================
# State preservation
# ===================================================================


class TestStatePreservation:
    async def test_preserves_plan_id(self) -> None:
        state = _base_state(plan_id="plan_keep_me")
        result = await calculate_budget_node(state)
        assert result["plan_id"] == "plan_keep_me"

    async def test_preserves_destination(self) -> None:
        state = _base_state(destination="Tokyo")
        result = await calculate_budget_node(state)
        assert result["destination"] == "Tokyo"

    async def test_preserves_hotel_options(self) -> None:
        hotel = _hotel()
        state = _base_state(hotel_options=[hotel])
        result = await calculate_budget_node(state)
        assert len(result["hotel_options"]) == 1

    async def test_preserves_activity_options(self) -> None:
        act = _activity()
        state = _base_state(activity_options=[act])
        result = await calculate_budget_node(state)
        assert len(result["activity_options"]) == 1

    async def test_preserves_revision_count(self) -> None:
        state = _base_state(revision_count=2)
        result = await calculate_budget_node(state)
        assert result["revision_count"] == 2


# ===================================================================
# Edge cases
# ===================================================================


class TestEdgeCases:
    async def test_zero_budget(self) -> None:
        """Zero budget with zero cost → valid."""
        state = _base_state(
            budget={"total": 0.0, "currency": "EUR", "flexibility": 0.0},
        )
        result = await calculate_budget_node(state)
        assert result["current_cost"] == 0.0

    async def test_single_night_trip(self) -> None:
        hotel = _hotel(price_per_night=200.0)
        state = _base_state(
            dates={"start_date": "2025-07-01", "end_date": "2025-07-02"},
            selected_hotel_id="htl-000",
            hotel_options=[hotel],
        )
        result = await calculate_budget_node(state)
        # 1 night * 200 = 200
        assert result["current_cost"] == 200.0

    async def test_long_trip(self) -> None:
        hotel = _hotel(price_per_night=80.0)
        state = _base_state(
            dates={"start_date": "2025-07-01", "end_date": "2025-07-31"},
            selected_hotel_id="htl-000",
            hotel_options=[hotel],
        )
        result = await calculate_budget_node(state)
        # 30 nights * 80 = 2400
        assert result["current_cost"] == 2400.0

    async def test_free_activities_cost_zero(self) -> None:
        activities = [
            _activity(id="act-001", price=0.0),
            _activity(id="act-002", price=0.0),
        ]
        state = _base_state(
            selected_activity_ids=["act-001", "act-002"],
            activity_options=activities,
        )
        result = await calculate_budget_node(state)
        assert result["current_cost"] == 0.0

    async def test_cost_rounding(self) -> None:
        """Verify costs are rounded to 2 decimal places."""
        hotel = _hotel(price_per_night=133.33)
        state = _base_state(
            selected_hotel_id="htl-000",
            hotel_options=[hotel],
        )
        result = await calculate_budget_node(state)
        cost_str = f"{result['current_cost']:.2f}"
        assert result["current_cost"] == float(cost_str)


# ===================================================================
# Graph integration
# ===================================================================


class TestGraphIntegration:
    async def test_node_runs_inside_graph(self) -> None:
        """Verify calculate_budget executes within the compiled graph."""
        from travel_orchestrator.graph.planner_graph import compile_graph

        compiled = compile_graph()
        initial_state = _base_state()
        config = {"configurable": {"thread_id": "test-calculate-budget"}}
        result = await compiled.ainvoke(initial_state, config=config)

        # The node should have set current_cost
        assert "current_cost" in result
        assert isinstance(result["current_cost"], float)

    async def test_budget_recalculated_after_full_pipeline(self) -> None:
        """After real nodes run, calculate_budget should reflect accurate totals."""
        from travel_orchestrator.graph.planner_graph import compile_graph

        compiled = compile_graph()
        initial_state = _base_state(destination="Paris")
        config = {"configurable": {"thread_id": "test-calc-budget-pipeline"}}
        result = await compiled.ainvoke(initial_state, config=config)

        # current_cost should reflect hotel + activities (flights are stub)
        assert result["current_cost"] >= 0.0
        assert isinstance(result["risk_flags"], list)
