"""Unit tests for the gather_requirements graph node."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from travel_orchestrator.graph.nodes.gather_requirements import (
    RequirementsError,
    _style_to_interests,
    gather_requirements_node,
)
from travel_orchestrator.mcp_servers.context.preferences_server import _store


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _base_state(**overrides: Any) -> dict[str, Any]:
    """Return a minimal valid state, with optional overrides."""
    state: dict[str, Any] = {
        "plan_id": "",
        "destination": "Paris",
        "dates": {"start_date": "2025-07-01", "end_date": "2025-07-10"},
        "budget": {"total": 5000.0, "currency": "EUR", "flexibility": 0.1},
        "traveler_profile": {},
        "selected_flight_id": None,
        "selected_hotel_id": None,
        "selected_activity_ids": [],
        "current_cost": 999.0,  # should be reset to 0
        "revision_count": 5,    # should be reset to 0
        "approval_status": "approved",  # should be reset to pending
        "risk_flags": ["old_flag"],     # should be cleared
        "alternative_plans": {"old": {}},  # should be cleared
    }
    state.update(overrides)
    return state


@pytest.fixture(autouse=True)
async def _reset_store() -> None:
    """Clear the preference store before each test."""
    _store._data.clear()


# ===================================================================
# plan_id generation
# ===================================================================


class TestPlanId:
    async def test_generates_plan_id_when_empty(self) -> None:
        state = _base_state(plan_id="")
        result = await gather_requirements_node(state)
        assert result["plan_id"].startswith("plan_")
        assert len(result["plan_id"]) == 13  # "plan_" + 8 hex chars

    async def test_preserves_existing_plan_id(self) -> None:
        state = _base_state(plan_id="plan_existing")
        result = await gather_requirements_node(state)
        assert result["plan_id"] == "plan_existing"


# ===================================================================
# Input validation
# ===================================================================


class TestValidation:
    async def test_missing_destination_raises(self) -> None:
        state = _base_state(destination="")
        with pytest.raises(RequirementsError, match="Destination is required"):
            await gather_requirements_node(state)

    async def test_missing_start_date_raises(self) -> None:
        state = _base_state(dates={"start_date": "", "end_date": "2025-07-10"})
        with pytest.raises(RequirementsError, match="dates.*required"):
            await gather_requirements_node(state)

    async def test_missing_end_date_raises(self) -> None:
        state = _base_state(dates={"start_date": "2025-07-01", "end_date": ""})
        with pytest.raises(RequirementsError, match="dates.*required"):
            await gather_requirements_node(state)

    async def test_invalid_date_format_raises(self) -> None:
        state = _base_state(dates={"start_date": "not-a-date", "end_date": "2025-07-10"})
        with pytest.raises(RequirementsError, match="Invalid date format"):
            await gather_requirements_node(state)

    async def test_end_before_start_raises(self) -> None:
        state = _base_state(dates={"start_date": "2025-07-10", "end_date": "2025-07-01"})
        with pytest.raises(RequirementsError, match="must not be before"):
            await gather_requirements_node(state)

    async def test_zero_budget_raises(self) -> None:
        state = _base_state(budget={"total": 0, "currency": "EUR", "flexibility": 0.1})
        with pytest.raises(RequirementsError, match="Budget must be positive"):
            await gather_requirements_node(state)

    async def test_negative_budget_raises(self) -> None:
        state = _base_state(budget={"total": -100, "currency": "EUR", "flexibility": 0.1})
        with pytest.raises(RequirementsError, match="Budget must be positive"):
            await gather_requirements_node(state)

    async def test_same_start_end_is_valid(self) -> None:
        state = _base_state(dates={"start_date": "2025-07-01", "end_date": "2025-07-01"})
        result = await gather_requirements_node(state)
        assert result["dates"]["start_date"] == "2025-07-01"


# ===================================================================
# State initialisation
# ===================================================================


class TestStateInit:
    async def test_current_cost_reset_to_zero(self) -> None:
        state = _base_state(current_cost=1234.0)
        result = await gather_requirements_node(state)
        assert result["current_cost"] == 0.0

    async def test_revision_count_reset_to_zero(self) -> None:
        state = _base_state(revision_count=99)
        result = await gather_requirements_node(state)
        assert result["revision_count"] == 0

    async def test_approval_status_reset_to_pending(self) -> None:
        state = _base_state(approval_status="approved")
        result = await gather_requirements_node(state)
        assert result["approval_status"] == "pending"

    async def test_risk_flags_cleared(self) -> None:
        state = _base_state(risk_flags=["old_flag"])
        result = await gather_requirements_node(state)
        assert result["risk_flags"] == []

    async def test_alternative_plans_cleared(self) -> None:
        state = _base_state(alternative_plans={"plan_b": {"x": 1}})
        result = await gather_requirements_node(state)
        assert result["alternative_plans"] == {}

    async def test_group_size_defaults_to_one(self) -> None:
        state = _base_state(traveler_profile={})
        result = await gather_requirements_node(state)
        assert result["traveler_profile"]["group_size"] == 1


# ===================================================================
# Preference enrichment from context store
# ===================================================================


class TestPreferenceEnrichment:
    async def test_enriches_from_default_preferences(self) -> None:
        """When no user_id is given, uses user_default store defaults."""
        state = _base_state(traveler_profile={})
        result = await gather_requirements_node(state)
        # Default travel_style is "cultural" → interests should be culture-related
        profile = result["traveler_profile"]
        assert "culture" in profile["interests"]
        assert profile["pace"] == "moderate"

    async def test_enriches_from_stored_user_preferences(self) -> None:
        await _store.set("user_42", "travel_style", {"style": "adventure", "pace": "fast"})
        state = _base_state(traveler_profile={}, user_id="user_42")
        result = await gather_requirements_node(state)
        profile = result["traveler_profile"]
        assert "adventure" in profile["interests"]
        assert profile["pace"] == "fast"

    async def test_does_not_overwrite_explicit_interests(self) -> None:
        """Caller-provided interests take precedence over stored preferences."""
        await _store.set("user_42", "travel_style", {"style": "adventure", "pace": "fast"})
        state = _base_state(
            traveler_profile={"interests": ["food", "wine"]},
            user_id="user_42",
        )
        result = await gather_requirements_node(state)
        assert result["traveler_profile"]["interests"] == ["food", "wine"]

    async def test_does_not_overwrite_explicit_pace(self) -> None:
        await _store.set("user_42", "travel_style", {"style": "adventure", "pace": "fast"})
        state = _base_state(
            traveler_profile={"pace": "slow"},
            user_id="user_42",
        )
        result = await gather_requirements_node(state)
        assert result["traveler_profile"]["pace"] == "slow"

    async def test_enriches_accommodation_type(self) -> None:
        await _store.set("user_42", "accommodation_preferences", {"type": "airbnb", "amenities": ["kitchen"]})
        state = _base_state(traveler_profile={}, user_id="user_42")
        result = await gather_requirements_node(state)
        assert result["traveler_profile"]["accommodation_type"] == "airbnb"

    async def test_enriches_dietary_restrictions(self) -> None:
        await _store.set("user_42", "dietary_restrictions", ["vegetarian", "nut-free"])
        state = _base_state(traveler_profile={}, user_id="user_42")
        result = await gather_requirements_node(state)
        assert result["traveler_profile"]["dietary_restrictions"] == ["vegetarian", "nut-free"]

    async def test_preference_failure_does_not_crash(self) -> None:
        """If the preference store raises, the node logs a warning and continues."""
        state = _base_state(traveler_profile={})
        with patch(
            "travel_orchestrator.graph.nodes.gather_requirements.get_user_preferences",
            new_callable=AsyncMock,
            side_effect=RuntimeError("store unavailable"),
        ):
            result = await gather_requirements_node(state)
        # Should still succeed with defaults for group_size
        assert result["plan_id"].startswith("plan_")
        assert result["traveler_profile"]["group_size"] == 1


# ===================================================================
# _style_to_interests helper
# ===================================================================


class TestStyleToInterests:
    def test_adventure(self) -> None:
        assert _style_to_interests("adventure") == ["adventure", "nature", "sports"]

    def test_cultural(self) -> None:
        assert _style_to_interests("cultural") == ["culture", "history", "art"]

    def test_relaxation(self) -> None:
        assert _style_to_interests("relaxation") == ["wellness", "beach", "nature"]

    def test_luxury(self) -> None:
        assert _style_to_interests("luxury") == ["shopping", "gastronomy", "wellness"]

    def test_unknown_style_returns_fallback(self) -> None:
        assert _style_to_interests("unknown") == ["culture", "food"]

    def test_empty_string_returns_fallback(self) -> None:
        assert _style_to_interests("") == ["culture", "food"]


# ===================================================================
# Integration with the compiled graph
# ===================================================================


class TestGraphIntegration:
    async def test_node_runs_inside_graph(self) -> None:
        """Verify the real node works when invoked via the compiled graph."""
        from travel_orchestrator.graph.planner_graph import compile_graph

        compiled = compile_graph()
        initial_state = _base_state()
        config = {"configurable": {"thread_id": "test-gather-req"}}
        result = await compiled.ainvoke(initial_state, config=config)

        # gather_requirements should have run
        assert result["plan_id"].startswith("plan_")
        assert result["current_cost"] >= 0.0
        assert result["revision_count"] == 0
        assert result["approval_status"] in ("pending", "in_review")
