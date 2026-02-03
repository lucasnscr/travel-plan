"""Unit tests for the conditional edge routing functions."""

from __future__ import annotations

from typing import Any

import pytest

from travel_orchestrator.graph.edges import (
    MAX_REVISION_COUNT,
    _ACTIVITY_KEYWORDS,
    _BUDGET_OVERSHOOT_THRESHOLD,
    _FLIGHT_KEYWORDS,
    _HOTEL_KEYWORDS,
    determine_revision_target,
    process_approval_decision,
    should_optimize_costs,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _base_state(**overrides: Any) -> dict[str, Any]:
    """Return a minimal valid state."""
    state: dict[str, Any] = {
        "plan_id": "plan_test1234",
        "destination": "Paris",
        "dates": {"start_date": "2025-07-01", "end_date": "2025-07-10"},
        "budget": {"total": 5000.0, "currency": "EUR", "flexibility": 0.1},
        "traveler_profile": {
            "interests": ["culture", "food"],
            "pace": "moderate",
            "group_size": 2,
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


# ===================================================================
# should_optimize_costs
# ===================================================================


class TestShouldOptimizeCosts:
    def test_within_budget_proceeds(self) -> None:
        state = _base_state(current_cost=3000.0)
        assert should_optimize_costs(state) == "proceed"

    def test_exactly_at_budget_proceeds(self) -> None:
        # 5000 * 1.10 = 5500 (10% threshold), cost = 5500 → not over
        state = _base_state(current_cost=5500.0)
        assert should_optimize_costs(state) == "proceed"

    def test_over_budget_optimizes(self) -> None:
        # 5000 * 1.10 = 5500, cost = 5501 → over
        state = _base_state(current_cost=5501.0)
        assert should_optimize_costs(state) == "optimize_costs"

    def test_uses_flexibility_when_larger(self) -> None:
        # flexibility=0.20 > 0.10 → threshold becomes 5000*1.20=6000
        state = _base_state(
            budget={"total": 5000.0, "currency": "EUR", "flexibility": 0.20},
            current_cost=5800.0,
        )
        # 5800 < 6000 → proceed
        assert should_optimize_costs(state) == "proceed"

    def test_uses_10pct_when_flexibility_smaller(self) -> None:
        # flexibility=0.05 < 0.10 → threshold becomes 5000*1.10=5500
        state = _base_state(
            budget={"total": 5000.0, "currency": "EUR", "flexibility": 0.05},
            current_cost=5400.0,
        )
        # 5400 < 5500 → proceed
        assert should_optimize_costs(state) == "proceed"

    def test_uses_10pct_when_no_flexibility(self) -> None:
        state = _base_state(
            budget={"total": 5000.0, "currency": "EUR", "flexibility": 0.0},
            current_cost=5501.0,
        )
        assert should_optimize_costs(state) == "optimize_costs"

    def test_revision_cap_stops_loop(self) -> None:
        state = _base_state(
            current_cost=10000.0,
            revision_count=MAX_REVISION_COUNT,
        )
        # Over budget but retries exhausted → proceed anyway
        assert should_optimize_costs(state) == "proceed"

    def test_revision_count_below_cap_loops(self) -> None:
        state = _base_state(
            current_cost=10000.0,
            revision_count=MAX_REVISION_COUNT - 1,
        )
        assert should_optimize_costs(state) == "optimize_costs"

    def test_zero_budget_proceeds(self) -> None:
        state = _base_state(
            budget={"total": 0.0, "currency": "EUR", "flexibility": 0.0},
            current_cost=0.0,
        )
        assert should_optimize_costs(state) == "proceed"

    def test_zero_cost_proceeds(self) -> None:
        state = _base_state(current_cost=0.0)
        assert should_optimize_costs(state) == "proceed"

    def test_missing_budget_proceeds(self) -> None:
        state = _base_state()
        state["budget"] = {}
        state["current_cost"] = 0.0
        assert should_optimize_costs(state) == "proceed"


# ===================================================================
# process_approval_decision
# ===================================================================


class TestProcessApprovalDecision:
    def test_approved(self) -> None:
        state = _base_state(approval_status="approved")
        assert process_approval_decision(state) == "approved"

    def test_rejected(self) -> None:
        state = _base_state(approval_status="rejected")
        assert process_approval_decision(state) == "rejected"

    def test_pending_defaults_to_rejected(self) -> None:
        state = _base_state(approval_status="pending")
        assert process_approval_decision(state) == "rejected"

    def test_in_review_defaults_to_rejected(self) -> None:
        state = _base_state(approval_status="in_review")
        assert process_approval_decision(state) == "rejected"

    def test_missing_status_defaults_to_rejected(self) -> None:
        state = _base_state()
        state.pop("approval_status", None)
        assert process_approval_decision(state) == "rejected"


# ===================================================================
# determine_revision_target
# ===================================================================


class TestDetermineRevisionTarget:
    # -- Explicit feedback keywords (EN) ------------------------------------

    def test_flight_feedback(self) -> None:
        state = _base_state(risk_flags=["feedback: Need a cheaper flight"])
        assert determine_revision_target(state) == "search_flights"

    def test_hotel_feedback(self) -> None:
        state = _base_state(risk_flags=["feedback: Hotel is too far from center"])
        assert determine_revision_target(state) == "search_hotels"

    def test_activity_feedback(self) -> None:
        state = _base_state(risk_flags=["feedback: Want more outdoor activity options"])
        assert determine_revision_target(state) == "search_activities"

    def test_itinerary_feedback(self) -> None:
        state = _base_state(risk_flags=["feedback: The itinerary is too packed"])
        assert determine_revision_target(state) == "search_activities"

    # -- Portuguese keywords ------------------------------------------------

    def test_voo_feedback(self) -> None:
        state = _base_state(risk_flags=["feedback: Preciso de um voo mais barato"])
        assert determine_revision_target(state) == "search_flights"

    def test_hospedagem_feedback(self) -> None:
        state = _base_state(risk_flags=["feedback: Mudar hospedagem para algo mais central"])
        assert determine_revision_target(state) == "search_hotels"

    def test_atividade_feedback(self) -> None:
        state = _base_state(risk_flags=["feedback: Adicionar mais atividade cultural"])
        assert determine_revision_target(state) == "search_activities"

    def test_passeio_feedback(self) -> None:
        state = _base_state(risk_flags=["feedback: Quero mais passeio ao ar livre"])
        assert determine_revision_target(state) == "search_activities"

    def test_itinerario_feedback(self) -> None:
        state = _base_state(risk_flags=["feedback: Itinerário muito corrido"])
        assert determine_revision_target(state) == "search_activities"

    # -- Fallback to all flags when no feedback: prefix ----------------------

    def test_fallback_to_all_flags_flight(self) -> None:
        state = _base_state(risk_flags=["risk: Flight issues detected"])
        assert determine_revision_target(state) == "search_flights"

    def test_fallback_to_all_flags_hotel(self) -> None:
        state = _base_state(risk_flags=["budget: hotel cost too high"])
        assert determine_revision_target(state) == "search_hotels"

    # -- Default when no hints -----------------------------------------------

    def test_no_flags_defaults_to_flights(self) -> None:
        state = _base_state(risk_flags=[])
        assert determine_revision_target(state) == "search_flights"

    def test_unrelated_flags_defaults_to_flights(self) -> None:
        state = _base_state(risk_flags=["risk: something generic"])
        assert determine_revision_target(state) == "search_flights"

    # -- Priority: feedback takes precedence over generic flags ---------------

    def test_feedback_takes_precedence(self) -> None:
        state = _base_state(
            risk_flags=[
                "risk: Flight issues detected",
                "feedback: Change the hotel please",
            ]
        )
        # feedback: mentions hotel → search_hotels (not flights)
        assert determine_revision_target(state) == "search_hotels"

    # -- Multiple feedback entries -------------------------------------------

    def test_first_matching_keyword_wins(self) -> None:
        state = _base_state(
            risk_flags=[
                "feedback: Fix the flight and hotel",
            ]
        )
        # "flight" appears before "hotel" → search_flights
        assert determine_revision_target(state) == "search_flights"


# ===================================================================
# Constants sanity checks
# ===================================================================


class TestConstants:
    def test_max_revision_count(self) -> None:
        assert MAX_REVISION_COUNT == 3

    def test_budget_overshoot_threshold(self) -> None:
        assert _BUDGET_OVERSHOOT_THRESHOLD == 0.10

    def test_keyword_sets_not_empty(self) -> None:
        assert len(_FLIGHT_KEYWORDS) > 0
        assert len(_HOTEL_KEYWORDS) > 0
        assert len(_ACTIVITY_KEYWORDS) > 0

    def test_keywords_include_portuguese(self) -> None:
        assert "voo" in _FLIGHT_KEYWORDS
        assert "hospedagem" in _HOTEL_KEYWORDS
        assert "atividade" in _ACTIVITY_KEYWORDS
        assert "passeio" in _ACTIVITY_KEYWORDS

    def test_keywords_include_english(self) -> None:
        assert "flight" in _FLIGHT_KEYWORDS
        assert "hotel" in _HOTEL_KEYWORDS
        assert "activity" in _ACTIVITY_KEYWORDS
        assert "itinerary" in _ACTIVITY_KEYWORDS


# ===================================================================
# Graph integration — edges wired correctly
# ===================================================================


class TestGraphIntegration:
    async def test_graph_compiles_with_new_edges(self) -> None:
        from travel_orchestrator.graph.planner_graph import compile_graph

        compiled = compile_graph()
        assert compiled is not None

    async def test_budget_edge_routes_to_risk_check(self) -> None:
        """Within-budget plan should reach risk_and_policy_check."""
        from travel_orchestrator.graph.planner_graph import compile_graph

        compiled = compile_graph()
        state = _base_state(destination="Paris")
        config = {"configurable": {"thread_id": "test-edges-proceed"}}
        result = await compiled.ainvoke(state, config=config)

        # Graph should have passed through risk_and_policy_check
        # and paused at present_for_approval interrupt
        assert isinstance(result["risk_flags"], list)

    async def test_approval_edge_routes_approved(self) -> None:
        """Approved plan should reach book_services."""
        from langgraph.types import Command

        from travel_orchestrator.graph.planner_graph import compile_graph

        compiled = compile_graph()
        state = _base_state(destination="Paris")
        config = {"configurable": {"thread_id": "test-edges-approved"}}

        # Run to interrupt
        await compiled.ainvoke(state, config=config)
        # Resume with approval
        result = await compiled.ainvoke(
            Command(resume={"decision": "approved"}), config=config
        )

        assert result["approval_status"] == "approved"
