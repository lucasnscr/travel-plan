"""Unit tests for the analyze_destination graph node."""

from __future__ import annotations

import datetime
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from travel_orchestrator.graph.nodes.analyze_destination import (
    _compute_risk_flags,
    _compute_weather_summary,
    _generate_advisories,
    _suggest_packing,
    analyze_destination_node,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _base_state(**overrides: Any) -> dict[str, Any]:
    """Return a minimal valid state as produced by gather_requirements."""
    state: dict[str, Any] = {
        "plan_id": "plan_test1234",
        "destination": "Paris",
        "dates": {"start_date": "2025-07-01", "end_date": "2025-07-05"},
        "budget": {"total": 5000.0, "currency": "EUR", "flexibility": 0.1},
        "traveler_profile": {
            "interests": ["culture", "food"],
            "pace": "moderate",
            "group_size": 2,
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
    }
    state.update(overrides)
    return state


def _sample_forecast(days: int = 5, **day_overrides: Any) -> list[dict[str, Any]]:
    """Build a list of mock forecast dicts."""
    forecasts = []
    base_date = datetime.date(2025, 7, 1)
    for i in range(days):
        f: dict[str, Any] = {
            "date": (base_date + datetime.timedelta(days=i)).isoformat(),
            "condition": "partly_cloudy",
            "temp_max": 25.0,
            "temp_min": 15.0,
            "rain_chance": 20.0,
            "rain_start": None,
            "wind_speed": 10.0,
        }
        f.update(day_overrides)
        forecasts.append(f)
    return forecasts


# ===================================================================
# Node: happy path
# ===================================================================


class TestAnalyzeDestinationHappyPath:
    async def test_produces_destination_analysis(self) -> None:
        state = _base_state()
        result = await analyze_destination_node(state)
        analysis = result["destination_analysis"]
        assert analysis is not None
        assert "forecast" in analysis
        assert "alerts" in analysis
        assert "weather_summary" in analysis
        assert "seasonal_events" in analysis
        assert "travel_advisories" in analysis
        assert "analysis_timestamp" in analysis

    async def test_preserves_existing_state_fields(self) -> None:
        state = _base_state(plan_id="plan_keep_me", current_cost=0.0)
        result = await analyze_destination_node(state)
        assert result["plan_id"] == "plan_keep_me"
        assert result["current_cost"] == 0.0
        assert result["approval_status"] == "pending"

    async def test_forecast_matches_date_range(self) -> None:
        state = _base_state(
            destination="Tokyo",
            dates={"start_date": "2025-04-01", "end_date": "2025-04-03"},
        )
        result = await analyze_destination_node(state)
        analysis = result["destination_analysis"]
        assert len(analysis["forecast"]) == 3
        assert analysis["forecast"][0]["date"] == "2025-04-01"
        assert analysis["forecast"][2]["date"] == "2025-04-03"

    async def test_seasonal_events_detected_for_paris_july(self) -> None:
        """Paris Fete Nationale is in July."""
        state = _base_state(
            destination="Paris",
            dates={"start_date": "2025-07-10", "end_date": "2025-07-16"},
        )
        result = await analyze_destination_node(state)
        events = result["destination_analysis"]["seasonal_events"]
        event_names = [e["name"] for e in events]
        assert "Fête Nationale (14 Juillet)" in event_names

    async def test_no_seasonal_events_when_off_season(self) -> None:
        state = _base_state(
            destination="Paris",
            dates={"start_date": "2025-03-01", "end_date": "2025-03-05"},
        )
        result = await analyze_destination_node(state)
        events = result["destination_analysis"]["seasonal_events"]
        assert len(events) == 0

    async def test_analysis_timestamp_is_iso_format(self) -> None:
        state = _base_state()
        result = await analyze_destination_node(state)
        ts = result["destination_analysis"]["analysis_timestamp"]
        # Should parse without error
        datetime.datetime.fromisoformat(ts)

    async def test_tokyo_hanami_detected_in_march_april(self) -> None:
        state = _base_state(
            destination="Tokyo",
            dates={"start_date": "2025-03-25", "end_date": "2025-04-05"},
        )
        result = await analyze_destination_node(state)
        events = result["destination_analysis"]["seasonal_events"]
        event_names = [e["name"] for e in events]
        assert "Hanami — Cherry Blossom" in event_names

    async def test_weather_summary_has_expected_fields(self) -> None:
        state = _base_state()
        result = await analyze_destination_node(state)
        summary = result["destination_analysis"]["weather_summary"]
        assert "avg_temp_max" in summary
        assert "avg_temp_min" in summary
        assert "avg_rain_chance" in summary
        assert "dominant_condition" in summary
        assert "severe_weather_days" in summary
        assert "packing_suggestions" in summary


# ===================================================================
# Node: non-blocking / graceful degradation
# ===================================================================


class TestGracefulDegradation:
    async def test_continues_when_forecast_fails(self) -> None:
        state = _base_state()
        with patch(
            "travel_orchestrator.graph.nodes.analyze_destination.get_weather_forecast",
            new_callable=AsyncMock,
            side_effect=RuntimeError("network error"),
        ):
            result = await analyze_destination_node(state)
        analysis = result["destination_analysis"]
        assert analysis["forecast"] == []
        assert analysis["weather_summary"]["dominant_condition"] == "unknown"

    async def test_continues_when_alerts_fail(self) -> None:
        state = _base_state()
        with patch(
            "travel_orchestrator.graph.nodes.analyze_destination.get_weather_alerts",
            new_callable=AsyncMock,
            side_effect=RuntimeError("service down"),
        ):
            result = await analyze_destination_node(state)
        analysis = result["destination_analysis"]
        assert analysis["alerts"] == []

    async def test_continues_when_seasonal_events_fail(self) -> None:
        state = _base_state()
        with patch(
            "travel_orchestrator.graph.nodes.analyze_destination.get_seasonal_events",
            side_effect=RuntimeError("bad data"),
        ):
            result = await analyze_destination_node(state)
        analysis = result["destination_analysis"]
        assert analysis["seasonal_events"] == []

    async def test_all_services_fail_still_returns_valid_state(self) -> None:
        state = _base_state()
        with (
            patch(
                "travel_orchestrator.graph.nodes.analyze_destination.get_weather_forecast",
                new_callable=AsyncMock,
                side_effect=RuntimeError("fail"),
            ),
            patch(
                "travel_orchestrator.graph.nodes.analyze_destination.get_weather_alerts",
                new_callable=AsyncMock,
                side_effect=RuntimeError("fail"),
            ),
            patch(
                "travel_orchestrator.graph.nodes.analyze_destination.get_seasonal_events",
                side_effect=RuntimeError("fail"),
            ),
        ):
            result = await analyze_destination_node(state)
        analysis = result["destination_analysis"]
        assert analysis["forecast"] == []
        assert analysis["alerts"] == []
        assert analysis["seasonal_events"] == []
        assert analysis["travel_advisories"] == []
        assert result["risk_flags"] == []


# ===================================================================
# Risk flags
# ===================================================================


class TestRiskFlags:
    async def test_severe_alert_adds_risk_flag(self) -> None:
        state = _base_state()
        mock_alerts = [
            {"type": "storm", "severity": "warning", "message": "Storm coming"}
        ]
        with patch(
            "travel_orchestrator.graph.nodes.analyze_destination.get_weather_alerts",
            new_callable=AsyncMock,
            return_value=mock_alerts,
        ):
            result = await analyze_destination_node(state)
        assert "weather:severe_alert:storm" in result["risk_flags"]

    async def test_extreme_temperature_adds_risk_flag(self) -> None:
        hot_forecast = _sample_forecast(days=3, temp_max=40.0)
        state = _base_state()
        with patch(
            "travel_orchestrator.graph.nodes.analyze_destination.get_weather_forecast",
            new_callable=AsyncMock,
            return_value=hot_forecast,
        ):
            result = await analyze_destination_node(state)
        assert "weather:extreme_temperature" in result["risk_flags"]

    async def test_dangerous_wind_adds_risk_flag(self) -> None:
        windy_forecast = _sample_forecast(days=3, wind_speed=55.0)
        state = _base_state()
        with patch(
            "travel_orchestrator.graph.nodes.analyze_destination.get_weather_forecast",
            new_callable=AsyncMock,
            return_value=windy_forecast,
        ):
            result = await analyze_destination_node(state)
        assert "weather:dangerous_wind" in result["risk_flags"]

    async def test_high_rain_adds_risk_flag(self) -> None:
        rainy_forecast = _sample_forecast(days=3, rain_chance=80.0)
        state = _base_state()
        with patch(
            "travel_orchestrator.graph.nodes.analyze_destination.get_weather_forecast",
            new_callable=AsyncMock,
            return_value=rainy_forecast,
        ):
            result = await analyze_destination_node(state)
        assert "weather:high_rain" in result["risk_flags"]

    async def test_no_risk_flags_for_mild_weather(self) -> None:
        mild = _sample_forecast(
            days=3, temp_max=25.0, temp_min=15.0, rain_chance=20.0, wind_speed=10.0
        )
        state = _base_state()
        with (
            patch(
                "travel_orchestrator.graph.nodes.analyze_destination.get_weather_forecast",
                new_callable=AsyncMock,
                return_value=mild,
            ),
            patch(
                "travel_orchestrator.graph.nodes.analyze_destination.get_weather_alerts",
                new_callable=AsyncMock,
                return_value=[],
            ),
        ):
            result = await analyze_destination_node(state)
        assert result["risk_flags"] == []

    async def test_risk_flags_appended_to_existing(self) -> None:
        state = _base_state(risk_flags=["pre_existing_flag"])
        mock_alerts = [
            {"type": "flood", "severity": "warning", "message": "Flood risk"}
        ]
        with patch(
            "travel_orchestrator.graph.nodes.analyze_destination.get_weather_alerts",
            new_callable=AsyncMock,
            return_value=mock_alerts,
        ):
            result = await analyze_destination_node(state)
        assert "pre_existing_flag" in result["risk_flags"]
        assert "weather:severe_alert:flood" in result["risk_flags"]


# ===================================================================
# _compute_weather_summary helper
# ===================================================================


class TestComputeWeatherSummary:
    def test_empty_forecast(self) -> None:
        summary = _compute_weather_summary([])
        assert summary["dominant_condition"] == "unknown"
        assert summary["severe_weather_days"] == 0
        assert summary["packing_suggestions"] == []

    def test_computes_averages(self) -> None:
        forecast = [
            {
                "date": "2025-07-01",
                "condition": "sunny",
                "temp_max": 30.0,
                "temp_min": 20.0,
                "rain_chance": 10.0,
                "wind_speed": 5.0,
            },
            {
                "date": "2025-07-02",
                "condition": "sunny",
                "temp_max": 32.0,
                "temp_min": 22.0,
                "rain_chance": 20.0,
                "wind_speed": 8.0,
            },
        ]
        summary = _compute_weather_summary(forecast)
        assert summary["avg_temp_max"] == 31.0
        assert summary["avg_temp_min"] == 21.0
        assert summary["avg_rain_chance"] == 15.0

    def test_dominant_condition(self) -> None:
        forecast = [
            {
                "date": "d1",
                "condition": "sunny",
                "temp_max": 25.0,
                "temp_min": 15.0,
                "rain_chance": 0.0,
                "wind_speed": 5.0,
            },
            {
                "date": "d2",
                "condition": "rain",
                "temp_max": 20.0,
                "temp_min": 12.0,
                "rain_chance": 80.0,
                "wind_speed": 10.0,
            },
            {
                "date": "d3",
                "condition": "sunny",
                "temp_max": 26.0,
                "temp_min": 16.0,
                "rain_chance": 5.0,
                "wind_speed": 5.0,
            },
        ]
        summary = _compute_weather_summary(forecast)
        assert summary["dominant_condition"] == "sunny"

    def test_severe_weather_days_counted(self) -> None:
        forecast = [
            {
                "date": "d1",
                "condition": "thunderstorm",
                "temp_max": 30.0,
                "temp_min": 20.0,
                "rain_chance": 90.0,
                "wind_speed": 55.0,
            },
            {
                "date": "d2",
                "condition": "sunny",
                "temp_max": 28.0,
                "temp_min": 18.0,
                "rain_chance": 5.0,
                "wind_speed": 8.0,
            },
            {
                "date": "d3",
                "condition": "sunny",
                "temp_max": 27.0,
                "temp_min": 17.0,
                "rain_chance": 10.0,
                "wind_speed": 60.0,
            },
        ]
        summary = _compute_weather_summary(forecast)
        # d1: thunderstorm + wind; d3: wind alone
        assert summary["severe_weather_days"] == 2


# ===================================================================
# _suggest_packing helper
# ===================================================================


class TestSuggestPacking:
    def test_rainy_weather(self) -> None:
        suggestions = _suggest_packing(20.0, 10.0, 50.0)
        assert "umbrella" in suggestions
        assert "waterproof jacket" in suggestions

    def test_hot_weather(self) -> None:
        suggestions = _suggest_packing(35.0, 25.0, 5.0)
        assert "sunscreen" in suggestions
        assert "light clothing" in suggestions

    def test_cold_weather(self) -> None:
        suggestions = _suggest_packing(5.0, -3.0, 10.0)
        assert "warm layers" in suggestions
        assert "thermal underwear" in suggestions

    def test_mild_weather(self) -> None:
        suggestions = _suggest_packing(22.0, 12.0, 10.0)
        assert "comfortable walking shoes" in suggestions


# ===================================================================
# _generate_advisories helper
# ===================================================================


class TestGenerateAdvisories:
    def test_severe_weather_advisory(self) -> None:
        summary = _compute_weather_summary(
            _sample_forecast(days=2, condition="thunderstorm", wind_speed=55.0)
        )
        advisories = _generate_advisories(summary, [], [])
        assert any("Severe weather" in a for a in advisories)

    def test_alert_included_in_advisories(self) -> None:
        summary = _compute_weather_summary(_sample_forecast(days=1))
        alerts = [
            {
                "type": "storm",
                "severity": "warning",
                "message": "Storm approaching",
            }
        ]
        advisories = _generate_advisories(summary, alerts, [])
        assert any("Storm approaching" in a for a in advisories)

    def test_seasonal_event_advisory(self) -> None:
        summary = _compute_weather_summary(_sample_forecast(days=1))
        events = [
            {
                "name": "Carnaval do Rio",
                "category": "tour",
                "description": "The greatest show",
                "month_start": 2,
                "month_end": 3,
            }
        ]
        advisories = _generate_advisories(summary, [], events)
        assert any("Carnaval do Rio" in a for a in advisories)

    def test_no_advisories_for_mild_and_empty(self) -> None:
        summary = _compute_weather_summary(_sample_forecast(days=1))
        advisories = _generate_advisories(summary, [], [])
        assert advisories == []


# ===================================================================
# _compute_risk_flags helper
# ===================================================================


class TestComputeRiskFlags:
    def test_no_flags_for_clean_data(self) -> None:
        forecast = _sample_forecast(days=2)
        flags = _compute_risk_flags(forecast, [])
        assert flags == []

    def test_alert_flag(self) -> None:
        alerts = [{"type": "heat_wave", "severity": "warning", "message": "..."}]
        flags = _compute_risk_flags([], alerts)
        assert "weather:severe_alert:heat_wave" in flags

    def test_advisory_severity_not_flagged(self) -> None:
        alerts = [{"type": "flood", "severity": "advisory", "message": "..."}]
        flags = _compute_risk_flags([], alerts)
        assert flags == []

    def test_extreme_heat_flag(self) -> None:
        forecast = _sample_forecast(days=1, temp_max=40.0)
        flags = _compute_risk_flags(forecast, [])
        assert "weather:extreme_temperature" in flags

    def test_extreme_cold_flag(self) -> None:
        forecast = _sample_forecast(days=1, temp_min=-5.0)
        flags = _compute_risk_flags(forecast, [])
        assert "weather:extreme_temperature" in flags

    def test_empty_forecast_no_forecast_flags(self) -> None:
        alerts = [{"type": "flood", "severity": "warning", "message": "..."}]
        flags = _compute_risk_flags([], alerts)
        # Only alert flags, no forecast-based flags
        assert flags == ["weather:severe_alert:flood"]


# ===================================================================
# Graph integration
# ===================================================================


class TestGraphIntegration:
    async def test_node_runs_inside_graph(self) -> None:
        """Verify the real node works when invoked via the compiled graph."""
        from travel_orchestrator.graph.planner_graph import compile_graph

        compiled = compile_graph()
        initial_state = _base_state()
        config = {"configurable": {"thread_id": "test-analyze-dest"}}
        result = await compiled.ainvoke(initial_state, config=config)

        # analyze_destination should have run
        assert result.get("destination_analysis") is not None
        assert result["destination_analysis"]["forecast"] is not None
