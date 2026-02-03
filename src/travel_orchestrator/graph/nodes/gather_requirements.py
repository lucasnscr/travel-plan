"""``gather_requirements`` graph node.

First node in the travel-planning workflow.  Responsible for:

1. Generating a ``plan_id`` if one is not already set.
2. Validating that the minimum required inputs are present
   (destination, dates, positive budget).
3. Enriching the ``traveler_profile`` with preferences stored in the
   MCP context server (travel style, dietary restrictions, etc.).
4. Initialising mutable state fields to their starting values so
   downstream nodes can rely on them being present.
"""

from __future__ import annotations

import datetime
import uuid

from travel_orchestrator.mcp_servers.context.client import get_user_preferences
from travel_orchestrator.state.models import TravelPlannerCore
from travel_orchestrator.utils.logging import get_logger, log_node_execution

logger = get_logger(__name__)


class RequirementsError(ValueError):
    """Raised when mandatory inputs are missing or invalid."""


def _validate_dates(dates: dict[str, str]) -> None:
    """Ensure start/end dates are present, parseable, and in order."""
    start_raw = dates.get("start_date", "")
    end_raw = dates.get("end_date", "")

    if not start_raw or not end_raw:
        raise RequirementsError("Travel dates (start_date, end_date) are required")

    try:
        start = datetime.date.fromisoformat(start_raw)
        end = datetime.date.fromisoformat(end_raw)
    except ValueError as exc:
        raise RequirementsError(f"Invalid date format: {exc}") from exc

    if end < start:
        raise RequirementsError(
            f"end_date ({end_raw}) must not be before start_date ({start_raw})"
        )


@log_node_execution("gather_requirements")
async def gather_requirements_node(state: TravelPlannerCore) -> TravelPlannerCore:
    """Collect, validate, and enrich the initial travel-plan requirements."""

    # -- 1. Generate plan_id ---------------------------------------------------
    plan_id = state.get("plan_id") or f"plan_{uuid.uuid4().hex[:8]}"

    # -- 2. Validate mandatory inputs -----------------------------------------
    destination = state.get("destination", "")
    if not destination:
        raise RequirementsError("Destination is required")

    dates = state.get("dates", {})
    _validate_dates(dates)

    budget = state.get("budget", {})
    budget_total = float(budget.get("total", 0))
    if budget_total <= 0:
        raise RequirementsError("Budget must be positive")

    # -- 3. Enrich traveler_profile from context server -----------------------
    profile = dict(state.get("traveler_profile", {}))

    user_id = state.get("user_id", "user_default")  # type: ignore[typeddict-item]

    try:
        preferences = await get_user_preferences(user_id)

        travel_style = preferences.get("travel_style", {})
        accommodation = preferences.get("accommodation_preferences", {})

        # Only fill in fields that the caller left empty
        if not profile.get("interests"):
            # Derive interests from travel-style string
            style = travel_style.get("style", "")
            profile["interests"] = _style_to_interests(style)

        if not profile.get("pace"):
            profile["pace"] = travel_style.get("pace", "moderate")

        # Stash accommodation preference for downstream nodes
        if not profile.get("accommodation_type"):
            profile["accommodation_type"] = accommodation.get("type", "hotel")

        # Dietary restrictions (informational, used by activity filtering)
        if preferences.get("dietary_restrictions"):
            profile["dietary_restrictions"] = preferences["dietary_restrictions"]

        logger.info(
            "preferences_enriched",
            user_id=user_id,
            style=travel_style.get("style"),
            pace=profile.get("pace"),
        )
    except Exception as exc:
        logger.warning("failed_to_fetch_preferences", error=str(exc))

    # Ensure group_size has a default
    if not profile.get("group_size"):
        profile["group_size"] = 1

    # -- 4. Initialise mutable fields -----------------------------------------
    return {
        **state,
        "plan_id": plan_id,
        "destination": destination,
        "dates": dates,
        "budget": budget,
        "traveler_profile": profile,
        "selected_flight_id": state.get("selected_flight_id"),
        "selected_hotel_id": state.get("selected_hotel_id"),
        "selected_activity_ids": state.get("selected_activity_ids", []),
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_STYLE_INTERESTS: dict[str, list[str]] = {
    "adventure": ["adventure", "nature", "sports"],
    "cultural": ["culture", "history", "art"],
    "relaxation": ["wellness", "beach", "nature"],
    "luxury": ["shopping", "gastronomy", "wellness"],
}


def _style_to_interests(style: str) -> list[str]:
    """Map a travel-style label to a default interest list."""
    return list(_STYLE_INTERESTS.get(style, ["culture", "food"]))
