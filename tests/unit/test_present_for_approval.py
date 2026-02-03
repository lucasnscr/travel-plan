"""Unit tests for the present_for_approval graph node (HITL interrupt)."""

from __future__ import annotations

from typing import Any

import pytest
from langgraph.types import Command, interrupt

from travel_orchestrator.graph.nodes.present_for_approval import (
    _build_presentation,
    _compute_nights,
    _parse_decision,
    present_for_approval_node,
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
        "selected_activity_ids": ["act-001", "act-002", "act-003"],
        "current_cost": 3200.0,
        "revision_count": 0,
        "approval_status": "pending",
        "risk_flags": ["budget: cost near limit"],
        "alternative_plans": {},
        "destination_analysis": None,
        "hotel_options": [
            {
                "id": "htl-000",
                "name": "Hotel Paris Centre",
                "stars": 4,
                "price_per_night": 180.0,
                "address": "Le Marais",
                "coordinates": {"lat": 48.856, "lng": 2.352},
                "currency": "EUR",
                "amenities": ["wifi", "breakfast"],
                "reviews_score": 8.5,
                "distance_to_center_km": 0.5,
                "score": 0.9,
            }
        ],
        "activity_options": [
            {"id": "act-001", "name": "Louvre Museum", "price": 25.0},
            {"id": "act-002", "name": "Seine Cruise", "price": 40.0},
            {"id": "act-003", "name": "Eiffel Tower", "price": 30.0},
        ],
        "optimized_itinerary": {
            "days": [
                {
                    "date": "2025-07-01",
                    "day_number": 1,
                    "theme": "Art & Culture",
                    "slots": [],
                    "weather_condition": "sunny",
                    "notes": "",
                },
                {
                    "date": "2025-07-02",
                    "day_number": 2,
                    "theme": "River & Views",
                    "slots": [],
                    "weather_condition": "partly_cloudy",
                    "notes": "",
                },
            ],
            "unscheduled_activity_ids": [],
            "optimization_method": "deterministic_fallback",
            "validation_iterations": 0,
            "validation_warnings": [],
        },
    }
    state.update(overrides)
    return state


# ===================================================================
# _build_presentation
# ===================================================================


class TestBuildPresentation:
    def test_contains_required_fields(self) -> None:
        state = _base_state()
        pres = _build_presentation(state)
        assert pres["plan_id"] == "plan_test1234"
        assert pres["destination"] == "Paris"
        assert pres["total_cost"] == 3200.0
        assert pres["budget_total"] == 5000.0
        assert pres["budget_currency"] == "EUR"
        assert "message" in pres

    def test_budget_variance_calculation(self) -> None:
        state = _base_state(current_cost=5500.0)
        pres = _build_presentation(state)
        assert pres["budget_variance"] == 500.0  # 5500 - 5000

    def test_budget_variance_negative_under_budget(self) -> None:
        state = _base_state(current_cost=3000.0)
        pres = _build_presentation(state)
        assert pres["budget_variance"] == -2000.0  # 3000 - 5000

    def test_hotel_summary_included(self) -> None:
        state = _base_state()
        pres = _build_presentation(state)
        assert pres["hotel"] is not None
        assert pres["hotel"]["name"] == "Hotel Paris Centre"
        assert pres["hotel"]["stars"] == 4
        assert pres["hotel"]["price_per_night"] == 180.0

    def test_no_selected_hotel(self) -> None:
        state = _base_state(selected_hotel_id=None)
        pres = _build_presentation(state)
        assert pres["hotel"] is None

    def test_hotel_not_found_in_options(self) -> None:
        state = _base_state(selected_hotel_id="htl-999")
        pres = _build_presentation(state)
        assert pres["hotel"] is None

    def test_activity_count(self) -> None:
        state = _base_state()
        pres = _build_presentation(state)
        assert pres["activity_count"] == 3

    def test_itinerary_summary(self) -> None:
        state = _base_state()
        pres = _build_presentation(state)
        itin = pres["itinerary"]
        assert itin["total_days"] == 2
        assert itin["optimization_method"] == "deterministic_fallback"
        assert itin["day_themes"] == ["Art & Culture", "River & Views"]

    def test_no_itinerary(self) -> None:
        state = _base_state(optimized_itinerary=None)
        pres = _build_presentation(state)
        assert pres["itinerary"] == {}

    def test_risk_flags_included(self) -> None:
        state = _base_state(risk_flags=["budget: near limit", "risk: advisory"])
        pres = _build_presentation(state)
        assert len(pres["risk_flags"]) == 2

    def test_nights_calculation(self) -> None:
        state = _base_state()
        pres = _build_presentation(state)
        assert pres["nights"] == 9

    def test_revision_count_included(self) -> None:
        state = _base_state(revision_count=2)
        pres = _build_presentation(state)
        assert pres["revision_count"] == 2


# ===================================================================
# _parse_decision
# ===================================================================


class TestParseDecision:
    def test_dict_approved(self) -> None:
        result = _parse_decision({"decision": "approved"})
        assert result["status"] == "approved"
        assert result["feedback"] == ""

    def test_dict_rejected_with_feedback(self) -> None:
        result = _parse_decision(
            {"decision": "rejected", "feedback": "Hotel too expensive"}
        )
        assert result["status"] == "rejected"
        assert result["feedback"] == "Hotel too expensive"

    def test_dict_rejected_no_feedback(self) -> None:
        result = _parse_decision({"decision": "rejected"})
        assert result["status"] == "rejected"
        assert result["feedback"] == ""

    def test_string_approved(self) -> None:
        result = _parse_decision("approved")
        assert result["status"] == "approved"

    def test_string_approved_case_insensitive(self) -> None:
        result = _parse_decision("APPROVED")
        assert result["status"] == "approved"

    def test_string_rejected_with_reason(self) -> None:
        result = _parse_decision("rejected: Need cheaper hotel")
        assert result["status"] == "rejected"
        assert result["feedback"] == "Need cheaper hotel"

    def test_string_rejected_no_reason(self) -> None:
        result = _parse_decision("rejected")
        assert result["status"] == "rejected"
        assert result["feedback"] == ""

    def test_unrecognised_format_defaults_to_rejected(self) -> None:
        result = _parse_decision(42)
        assert result["status"] == "rejected"
        assert "Unrecognised" in result["feedback"]

    def test_empty_dict_defaults_to_rejected(self) -> None:
        result = _parse_decision({})
        assert result["status"] == "rejected"

    def test_whitespace_handling(self) -> None:
        result = _parse_decision("  approved  ")
        assert result["status"] == "approved"


# ===================================================================
# _compute_nights
# ===================================================================


class TestComputeNights:
    def test_multi_day(self) -> None:
        assert _compute_nights({"start_date": "2025-07-01", "end_date": "2025-07-10"}) == 9

    def test_same_day(self) -> None:
        assert _compute_nights({"start_date": "2025-07-01", "end_date": "2025-07-01"}) == 1

    def test_empty_dates(self) -> None:
        assert _compute_nights({}) == 0

    def test_invalid_dates(self) -> None:
        assert _compute_nights({"start_date": "bad", "end_date": "bad"}) == 0


# ===================================================================
# Node: interrupt & resume via compiled graph
# ===================================================================


class TestNodeInterruptResume:
    """Test the full interrupt/resume cycle using a compiled graph."""

    async def test_graph_pauses_at_interrupt(self) -> None:
        """First invocation should pause at the interrupt point."""
        from travel_orchestrator.graph.planner_graph import compile_graph

        compiled = compile_graph()
        state = _base_state()
        config = {"configurable": {"thread_id": "test-hitl-pause"}}

        result = await compiled.ainvoke(state, config=config)

        # Graph should have paused — approval_status not yet changed
        # (the node was interrupted before returning)
        assert result["approval_status"] == "pending"

        # Verify the interrupt is pending
        graph_state = await compiled.aget_state(config)
        assert len(graph_state.tasks) > 0
        # The interrupted task should carry the presentation value
        task = graph_state.tasks[0]
        assert hasattr(task, "interrupts")
        assert len(task.interrupts) > 0
        presentation = task.interrupts[0].value
        assert presentation["plan_id"] == "plan_test1234"
        assert presentation["destination"] == "Paris"
        assert "message" in presentation

    async def test_resume_approved(self) -> None:
        """Resume with 'approved' should set approval_status and continue."""
        from travel_orchestrator.graph.planner_graph import compile_graph

        compiled = compile_graph()
        state = _base_state()
        config = {"configurable": {"thread_id": "test-hitl-approve"}}

        # First run — pauses at interrupt
        await compiled.ainvoke(state, config=config)

        # Resume with approval
        result = await compiled.ainvoke(
            Command(resume={"decision": "approved"}), config=config
        )

        assert result["approval_status"] == "approved"

    async def test_resume_rejected_with_feedback(self) -> None:
        """Resume with rejection should set status and capture feedback."""
        from travel_orchestrator.graph.planner_graph import compile_graph

        compiled = compile_graph()
        state = _base_state()
        config = {"configurable": {"thread_id": "test-hitl-reject"}}

        # First run — pauses at interrupt
        await compiled.ainvoke(state, config=config)

        # Resume with rejection — this will hit process_feedback (stub)
        # and then loop back to search_flights, which hits the full
        # pipeline again and pauses at the next interrupt.
        result = await compiled.ainvoke(
            Command(resume={"decision": "rejected", "feedback": "Too expensive"}),
            config=config,
        )

        # After rejection → process_feedback → loops → eventually pauses
        # at present_for_approval interrupt again. Check that feedback
        # was captured in risk_flags at some point.
        graph_state = await compiled.aget_state(config)
        # The graph is paused again at present_for_approval
        assert len(graph_state.tasks) > 0

    async def test_resume_string_approved(self) -> None:
        """String shorthand 'approved' should also work."""
        from travel_orchestrator.graph.planner_graph import compile_graph

        compiled = compile_graph()
        state = _base_state()
        config = {"configurable": {"thread_id": "test-hitl-string-approve"}}

        await compiled.ainvoke(state, config=config)
        result = await compiled.ainvoke(
            Command(resume="approved"), config=config
        )

        assert result["approval_status"] == "approved"

    async def test_resume_unknown_format_rejects(self) -> None:
        """Unrecognised resume format should default to rejected."""
        from travel_orchestrator.graph.planner_graph import compile_graph

        compiled = compile_graph()
        state = _base_state()
        config = {"configurable": {"thread_id": "test-hitl-unknown"}}

        await compiled.ainvoke(state, config=config)
        # Resume with garbage — will be rejected and loop
        result = await compiled.ainvoke(
            Command(resume=12345), config=config
        )

        # Should have been rejected and looped back to interrupt
        graph_state = await compiled.aget_state(config)
        assert len(graph_state.tasks) > 0

    async def test_presentation_includes_risk_flags(self) -> None:
        """Risk flags generated by the pipeline should appear in the presentation."""
        from travel_orchestrator.graph.planner_graph import compile_graph

        compiled = compile_graph()
        # Mexico triggers a YELLOW travel advisory in risk_check
        state = _base_state(destination="Mexico")
        config = {"configurable": {"thread_id": "test-hitl-risk-flags"}}

        await compiled.ainvoke(state, config=config)

        graph_state = await compiled.aget_state(config)
        presentation = graph_state.tasks[0].interrupts[0].value
        # Should have at least the YELLOW advisory flag
        assert len(presentation["risk_flags"]) >= 1
        assert any("YELLOW" in f for f in presentation["risk_flags"])


# ===================================================================
# Node: feedback flag management
# ===================================================================


class TestFeedbackFlagManagement:
    async def test_stale_feedback_flags_cleared_on_new_rejection(self) -> None:
        """On re-rejection, old feedback: flags should be replaced."""
        from travel_orchestrator.graph.planner_graph import compile_graph

        compiled = compile_graph()
        state = _base_state(
            risk_flags=["feedback: old feedback", "budget: keep this"],
        )
        config = {"configurable": {"thread_id": "test-hitl-stale-feedback"}}

        # First run — pauses
        await compiled.ainvoke(state, config=config)

        # Resume with rejection — will loop back
        await compiled.ainvoke(
            Command(resume={"decision": "rejected", "feedback": "New feedback"}),
            config=config,
        )

        # Get state after rejection (graph loops and pauses again)
        graph_state = await compiled.aget_state(config)
        all_flags = graph_state.values.get("risk_flags", [])
        # Old feedback should be gone, new might be there or cleared by loop
        assert "feedback: old feedback" not in all_flags


# ===================================================================
# State preservation on approval
# ===================================================================


class TestStatePreservationOnApproval:
    async def test_preserves_plan_id(self) -> None:
        from travel_orchestrator.graph.planner_graph import compile_graph

        compiled = compile_graph()
        state = _base_state(plan_id="plan_keep_me")
        config = {"configurable": {"thread_id": "test-hitl-preserve-plan"}}

        await compiled.ainvoke(state, config=config)
        result = await compiled.ainvoke(
            Command(resume={"decision": "approved"}), config=config
        )

        assert result["plan_id"] == "plan_keep_me"

    async def test_preserves_current_cost(self) -> None:
        from travel_orchestrator.graph.planner_graph import compile_graph

        compiled = compile_graph()
        state = _base_state()
        config = {"configurable": {"thread_id": "test-hitl-preserve-cost"}}

        await compiled.ainvoke(state, config=config)
        result = await compiled.ainvoke(
            Command(resume={"decision": "approved"}), config=config
        )

        # current_cost should be whatever calculate_budget computed
        assert isinstance(result["current_cost"], float)

    async def test_preserves_hotel_options(self) -> None:
        from travel_orchestrator.graph.planner_graph import compile_graph

        compiled = compile_graph()
        state = _base_state()
        config = {"configurable": {"thread_id": "test-hitl-preserve-hotels"}}

        await compiled.ainvoke(state, config=config)
        result = await compiled.ainvoke(
            Command(resume={"decision": "approved"}), config=config
        )

        assert isinstance(result["hotel_options"], list)
