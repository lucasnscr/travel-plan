"""Unit tests for the risk_and_policy_check graph node."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest

from travel_orchestrator.graph.nodes.risk_check import (
    _DESTINATION_RESTRICTIONS,
    _INSURANCE_COST_THRESHOLD,
    _INSURANCE_DURATION_THRESHOLD_DAYS,
    _RISK_FLAG_PREFIX,
    _TRAVEL_ADVISORY_LEVELS,
    _check_approval_threshold,
    _check_destination_restrictions,
    _check_insurance_recommendation,
    _check_travel_advisory,
    _check_weather_advisories,
    _compute_trip_days,
    risk_and_policy_check_node,
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
        "current_cost": 3000.0,
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


def _destination_analysis(**overrides: Any) -> dict[str, Any]:
    """Build a DestinationAnalysis dict."""
    analysis: dict[str, Any] = {
        "forecast": [],
        "alerts": [],
        "weather_summary": {
            "avg_temp_max": 28.0,
            "avg_temp_min": 18.0,
            "avg_rain_chance": 20.0,
            "dominant_condition": "sunny",
            "severe_weather_days": 0,
            "packing_suggestions": [],
        },
        "seasonal_events": [],
        "travel_advisories": [],
        "analysis_timestamp": "2025-06-15T10:00:00+00:00",
    }
    analysis.update(overrides)
    return analysis


# ===================================================================
# _check_travel_advisory
# ===================================================================


class TestCheckTravelAdvisory:
    def test_green_destination_no_flags(self) -> None:
        flags = _check_travel_advisory("Paris")
        assert flags == []

    def test_unknown_destination_no_flags(self) -> None:
        flags = _check_travel_advisory("Atlantis")
        assert flags == []

    def test_red_advisory(self) -> None:
        flags = _check_travel_advisory("Syria")
        assert len(flags) == 1
        assert "RED" in flags[0]
        assert "do not travel" in flags[0].lower()

    def test_orange_advisory(self) -> None:
        flags = _check_travel_advisory("Venezuela")
        assert len(flags) == 1
        assert "ORANGE" in flags[0]
        assert "reconsider" in flags[0].lower()

    def test_yellow_advisory(self) -> None:
        flags = _check_travel_advisory("Mexico")
        assert len(flags) == 1
        assert "YELLOW" in flags[0]
        assert "caution" in flags[0].lower()

    def test_case_insensitive(self) -> None:
        flags = _check_travel_advisory("SYRIA")
        assert len(flags) == 1
        assert "RED" in flags[0]

    def test_whitespace_trimmed(self) -> None:
        flags = _check_travel_advisory("  syria  ")
        assert len(flags) == 1

    def test_all_red_destinations_flagged(self) -> None:
        for dest, level in _TRAVEL_ADVISORY_LEVELS.items():
            if level == "RED":
                flags = _check_travel_advisory(dest)
                assert len(flags) == 1, f"{dest} should produce a RED flag"


# ===================================================================
# _check_approval_threshold
# ===================================================================


class TestCheckApprovalThreshold:
    def test_below_threshold_no_flags(self) -> None:
        flags = _check_approval_threshold(5000.0)
        assert flags == []

    def test_above_threshold_flags(self) -> None:
        flags = _check_approval_threshold(15000.0)
        assert len(flags) == 1
        assert "approval" in flags[0].lower()
        assert "manager" in flags[0].lower()

    def test_exactly_at_threshold_no_flags(self) -> None:
        # Default threshold is 10000. Exactly at threshold should not trigger.
        flags = _check_approval_threshold(10000.0)
        assert flags == []

    def test_just_above_threshold(self) -> None:
        flags = _check_approval_threshold(10000.01)
        assert len(flags) == 1

    def test_zero_cost_no_flags(self) -> None:
        flags = _check_approval_threshold(0.0)
        assert flags == []

    def test_settings_fallback(self) -> None:
        """Should use fallback threshold when settings unavailable."""
        with patch(
            "travel_orchestrator.graph.nodes.risk_check._get_approval_threshold",
            return_value=10_000.0,
        ):
            flags = _check_approval_threshold(15000.0)
            assert len(flags) == 1


# ===================================================================
# _check_destination_restrictions
# ===================================================================


class TestCheckDestinationRestrictions:
    def test_no_restrictions(self) -> None:
        flags = _check_destination_restrictions("Paris")
        assert flags == []

    def test_china_visa_required(self) -> None:
        flags = _check_destination_restrictions("China")
        assert len(flags) >= 1
        assert any("visa" in f.lower() for f in flags)

    def test_cuba_multiple_restrictions(self) -> None:
        flags = _check_destination_restrictions("Cuba")
        assert len(flags) >= 2
        assert any("tourist card" in f.lower() for f in flags)
        assert any("insurance mandatory" in f.lower() for f in flags)

    def test_case_insensitive(self) -> None:
        flags_lower = _check_destination_restrictions("china")
        flags_upper = _check_destination_restrictions("CHINA")
        assert len(flags_lower) == len(flags_upper)

    def test_all_restricted_destinations_produce_flags(self) -> None:
        for dest in _DESTINATION_RESTRICTIONS:
            flags = _check_destination_restrictions(dest)
            assert len(flags) > 0, f"{dest} should produce restriction flags"


# ===================================================================
# _check_insurance_recommendation
# ===================================================================


class TestCheckInsuranceRecommendation:
    def test_low_cost_short_trip_no_insurance(self) -> None:
        state = _base_state(current_cost=2000.0)
        flags = _check_insurance_recommendation(state)
        assert flags == []

    def test_high_cost_recommends_insurance(self) -> None:
        state = _base_state(current_cost=6000.0)
        flags = _check_insurance_recommendation(state)
        assert len(flags) == 1
        assert "recommended" in flags[0].lower()
        assert "high trip cost" in flags[0].lower()

    def test_long_trip_recommends_insurance(self) -> None:
        state = _base_state(
            current_cost=2000.0,
            dates={"start_date": "2025-07-01", "end_date": "2025-07-20"},
        )
        flags = _check_insurance_recommendation(state)
        assert len(flags) == 1
        assert "duration" in flags[0].lower()

    def test_orange_advisory_recommends_insurance(self) -> None:
        state = _base_state(destination="Venezuela", current_cost=2000.0)
        flags = _check_insurance_recommendation(state)
        assert len(flags) == 1
        assert "advisory" in flags[0].lower()

    def test_mandatory_insurance_destination(self) -> None:
        state = _base_state(destination="Cuba", current_cost=2000.0)
        flags = _check_insurance_recommendation(state)
        assert len(flags) == 1
        assert "mandatory" in flags[0].lower()

    def test_multiple_reasons_combined(self) -> None:
        state = _base_state(
            destination="Venezuela",
            current_cost=8000.0,
            dates={"start_date": "2025-07-01", "end_date": "2025-07-20"},
        )
        flags = _check_insurance_recommendation(state)
        assert len(flags) == 1
        # Should mention both cost and duration and advisory
        flag_text = flags[0].lower()
        assert "high trip cost" in flag_text
        assert "duration" in flag_text
        assert "advisory" in flag_text

    def test_threshold_constants(self) -> None:
        assert _INSURANCE_COST_THRESHOLD == 5000.0
        assert _INSURANCE_DURATION_THRESHOLD_DAYS == 14


# ===================================================================
# _check_weather_advisories
# ===================================================================


class TestCheckWeatherAdvisories:
    def test_no_destination_analysis(self) -> None:
        state = _base_state(destination_analysis=None)
        flags = _check_weather_advisories(state)
        assert flags == []

    def test_no_advisories(self) -> None:
        analysis = _destination_analysis(travel_advisories=[])
        state = _base_state(destination_analysis=analysis)
        flags = _check_weather_advisories(state)
        assert flags == []

    def test_severe_advisory_surfaced(self) -> None:
        analysis = _destination_analysis(
            travel_advisories=[
                "Severe weather expected on 2 day(s). Consider flexible bookings.",
            ]
        )
        state = _base_state(destination_analysis=analysis)
        flags = _check_weather_advisories(state)
        assert len(flags) == 1
        assert "severe" in flags[0].lower()

    def test_extreme_heat_surfaced(self) -> None:
        analysis = _destination_analysis(
            travel_advisories=[
                "Extreme heat expected. Stay hydrated.",
            ]
        )
        state = _base_state(destination_analysis=analysis)
        flags = _check_weather_advisories(state)
        assert len(flags) == 1

    def test_non_severe_advisory_not_surfaced(self) -> None:
        analysis = _destination_analysis(
            travel_advisories=[
                "High average rain chance during your trip. Plan indoor alternatives.",
            ]
        )
        state = _base_state(destination_analysis=analysis)
        flags = _check_weather_advisories(state)
        # "rain" alone is not in the severe keywords list
        assert flags == []

    def test_freezing_advisory_surfaced(self) -> None:
        analysis = _destination_analysis(
            travel_advisories=[
                "Near-freezing temperatures expected. Pack warm clothing.",
            ]
        )
        state = _base_state(destination_analysis=analysis)
        flags = _check_weather_advisories(state)
        assert len(flags) == 1

    def test_storm_advisory_surfaced(self) -> None:
        analysis = _destination_analysis(
            travel_advisories=[
                "Weather alert (warning): Tropical storm approaching.",
            ]
        )
        state = _base_state(destination_analysis=analysis)
        flags = _check_weather_advisories(state)
        assert len(flags) == 1


# ===================================================================
# _compute_trip_days
# ===================================================================


class TestComputeTripDays:
    def test_multi_day(self) -> None:
        state = _base_state(dates={"start_date": "2025-07-01", "end_date": "2025-07-10"})
        assert _compute_trip_days(state) == 9

    def test_same_day(self) -> None:
        state = _base_state(dates={"start_date": "2025-07-01", "end_date": "2025-07-01"})
        assert _compute_trip_days(state) == 1

    def test_missing_dates(self) -> None:
        state = _base_state(dates={})
        assert _compute_trip_days(state) == 1

    def test_invalid_dates(self) -> None:
        state = _base_state(dates={"start_date": "bad", "end_date": "bad"})
        assert _compute_trip_days(state) == 1


# ===================================================================
# Full node: flag management
# ===================================================================


class TestNodeFlagManagement:
    async def test_stale_risk_flags_cleared(self) -> None:
        state = _base_state(
            risk_flags=[
                "risk: old stale flag",
                "budget: keep this",
                "weather:high_rain",
            ],
        )
        result = await risk_and_policy_check_node(state)
        assert "risk: old stale flag" not in result["risk_flags"]
        assert "budget: keep this" in result["risk_flags"]
        assert "weather:high_rain" in result["risk_flags"]

    async def test_non_risk_flags_preserved(self) -> None:
        state = _base_state(
            risk_flags=["budget: cost near limit", "weather:extreme_temperature"],
        )
        result = await risk_and_policy_check_node(state)
        assert "budget: cost near limit" in result["risk_flags"]
        assert "weather:extreme_temperature" in result["risk_flags"]

    async def test_all_flags_prefixed_with_risk(self) -> None:
        """All new flags from this node should start with 'risk:'."""
        state = _base_state(
            destination="Syria",
            current_cost=15000.0,
        )
        result = await risk_and_policy_check_node(state)
        new_flags = [f for f in result["risk_flags"] if f.startswith(_RISK_FLAG_PREFIX)]
        # Should have at least advisory + threshold flags
        assert len(new_flags) >= 2


# ===================================================================
# Full node: integration scenarios
# ===================================================================


class TestNodeScenarios:
    async def test_safe_destination_low_cost(self) -> None:
        """Paris, low cost → no risk flags."""
        state = _base_state(destination="Paris", current_cost=3000.0)
        result = await risk_and_policy_check_node(state)
        risk_flags = [f for f in result["risk_flags"] if f.startswith(_RISK_FLAG_PREFIX)]
        assert risk_flags == []

    async def test_red_advisory_destination(self) -> None:
        state = _base_state(destination="Syria", current_cost=2000.0)
        result = await risk_and_policy_check_node(state)
        risk_flags = [f for f in result["risk_flags"] if f.startswith(_RISK_FLAG_PREFIX)]
        assert any("RED" in f for f in risk_flags)
        # Insurance should also be recommended (ORANGE/RED advisory)
        assert any("insurance" in f.lower() for f in risk_flags)

    async def test_expensive_trip_needs_approval(self) -> None:
        state = _base_state(current_cost=15000.0)
        result = await risk_and_policy_check_node(state)
        risk_flags = [f for f in result["risk_flags"] if f.startswith(_RISK_FLAG_PREFIX)]
        assert any("approval" in f.lower() for f in risk_flags)
        # Also insurance since > 5000
        assert any("insurance" in f.lower() for f in risk_flags)

    async def test_restricted_destination(self) -> None:
        state = _base_state(destination="China", current_cost=3000.0)
        result = await risk_and_policy_check_node(state)
        risk_flags = [f for f in result["risk_flags"] if f.startswith(_RISK_FLAG_PREFIX)]
        assert any("visa" in f.lower() for f in risk_flags)

    async def test_severe_weather_flagged(self) -> None:
        analysis = _destination_analysis(
            travel_advisories=[
                "Severe weather expected on 3 day(s). Consider flexible bookings.",
            ]
        )
        state = _base_state(destination_analysis=analysis)
        result = await risk_and_policy_check_node(state)
        risk_flags = [f for f in result["risk_flags"] if f.startswith(_RISK_FLAG_PREFIX)]
        assert any("severe" in f.lower() for f in risk_flags)

    async def test_combined_risks(self) -> None:
        """Venezuela (ORANGE), high cost, long trip → multiple flags."""
        analysis = _destination_analysis(
            travel_advisories=[
                "Severe weather expected on 1 day(s). Consider flexible bookings.",
            ]
        )
        state = _base_state(
            destination="Venezuela",
            current_cost=12000.0,
            dates={"start_date": "2025-07-01", "end_date": "2025-07-20"},
            destination_analysis=analysis,
        )
        result = await risk_and_policy_check_node(state)
        risk_flags = [f for f in result["risk_flags"] if f.startswith(_RISK_FLAG_PREFIX)]
        # Should have: advisory ORANGE, approval threshold, insurance, weather
        assert len(risk_flags) >= 4

    async def test_zero_cost_no_approval_needed(self) -> None:
        state = _base_state(current_cost=0.0)
        result = await risk_and_policy_check_node(state)
        risk_flags = [f for f in result["risk_flags"] if f.startswith(_RISK_FLAG_PREFIX)]
        assert not any("approval" in f.lower() for f in risk_flags)


# ===================================================================
# State preservation
# ===================================================================


class TestStatePreservation:
    async def test_preserves_plan_id(self) -> None:
        state = _base_state(plan_id="plan_keep_me")
        result = await risk_and_policy_check_node(state)
        assert result["plan_id"] == "plan_keep_me"

    async def test_preserves_current_cost(self) -> None:
        state = _base_state(current_cost=4500.0)
        result = await risk_and_policy_check_node(state)
        assert result["current_cost"] == 4500.0

    async def test_preserves_approval_status(self) -> None:
        state = _base_state(approval_status="pending")
        result = await risk_and_policy_check_node(state)
        assert result["approval_status"] == "pending"

    async def test_preserves_hotel_options(self) -> None:
        state = _base_state(hotel_options=[{"id": "htl-000", "name": "Test"}])
        result = await risk_and_policy_check_node(state)
        assert len(result["hotel_options"]) == 1

    async def test_preserves_revision_count(self) -> None:
        state = _base_state(revision_count=2)
        result = await risk_and_policy_check_node(state)
        assert result["revision_count"] == 2


# ===================================================================
# Graph integration
# ===================================================================


class TestGraphIntegration:
    async def test_node_runs_inside_graph(self) -> None:
        """Verify risk_and_policy_check executes within the compiled graph."""
        from travel_orchestrator.graph.planner_graph import compile_graph

        compiled = compile_graph()
        initial_state = _base_state()
        config = {"configurable": {"thread_id": "test-risk-check"}}
        result = await compiled.ainvoke(initial_state, config=config)

        assert "risk_flags" in result
        assert isinstance(result["risk_flags"], list)

    async def test_risk_flags_populated_after_full_pipeline(self) -> None:
        """After real nodes run, risk_flags should be a list."""
        from travel_orchestrator.graph.planner_graph import compile_graph

        compiled = compile_graph()
        initial_state = _base_state(destination="Paris")
        config = {"configurable": {"thread_id": "test-risk-pipeline"}}
        result = await compiled.ainvoke(initial_state, config=config)

        assert isinstance(result["risk_flags"], list)
        # Paris is GREEN advisory, so no travel advisory flags expected
        advisory_flags = [
            f for f in result["risk_flags"]
            if f.startswith(_RISK_FLAG_PREFIX) and "advisory" in f.lower()
        ]
        assert advisory_flags == []
