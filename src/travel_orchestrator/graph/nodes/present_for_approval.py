"""``present_for_approval`` graph node — HITL checkpoint.

Pauses the graph so a human reviewer can inspect the complete travel
plan and decide whether to approve or reject it.

Uses :func:`langgraph.types.interrupt` to:

1. Build a structured presentation of the plan (costs, itinerary,
   risk flags, options).
2. Pause execution and surface the presentation to the client.
3. On resume (via ``Command(resume=answer)``), process the human's
   decision and set ``approval_status`` accordingly.

Expected resume payload::

    # Approve
    Command(resume={"decision": "approved"})

    # Reject with feedback
    Command(resume={"decision": "rejected", "feedback": "Hotel too far from center"})
"""

from __future__ import annotations

import datetime
from typing import Any

from langgraph.types import interrupt

from travel_orchestrator.state.models import TravelPlannerCore
from travel_orchestrator.utils.logging import get_logger, log_node_execution

logger = get_logger(__name__)


@log_node_execution("present_for_approval")
async def present_for_approval_node(
    state: TravelPlannerCore,
) -> TravelPlannerCore:
    """Present the plan for human approval, then process the decision."""

    # -- Build presentation summary -----------------------------------------
    presentation = _build_presentation(state)

    logger.info(
        "presenting_for_approval",
        plan_id=state.get("plan_id"),
        total_cost=presentation["total_cost"],
        risk_flag_count=len(presentation["risk_flags"]),
    )

    # -- Interrupt: pause for human review ----------------------------------
    # First invocation: raises GraphInterrupt, sends presentation to client.
    # On resume via Command(resume=answer): returns the human's answer.
    answer = interrupt(presentation)

    # -- Process the human's decision (only runs after resume) --------------
    decision = _parse_decision(answer)

    if decision["status"] == "approved":
        logger.info(
            "plan_approved",
            plan_id=state.get("plan_id"),
        )
        return {
            **state,
            "approval_status": "approved",
        }

    # Rejected — capture feedback in risk_flags for downstream routing
    feedback = decision.get("feedback", "")
    risk_flags: list[str] = list(state.get("risk_flags", []))

    # Remove stale feedback flags from previous rejection cycles
    risk_flags = [f for f in risk_flags if not f.startswith("feedback:")]

    if feedback:
        risk_flags.append(f"feedback: {feedback}")

    logger.info(
        "plan_rejected",
        plan_id=state.get("plan_id"),
        feedback=feedback,
    )

    return {
        **state,
        "approval_status": "rejected",
        "risk_flags": risk_flags,
    }


# ---------------------------------------------------------------------------
# Presentation builder
# ---------------------------------------------------------------------------


def _build_presentation(state: TravelPlannerCore) -> dict[str, Any]:
    """Assemble a human-readable summary of the complete travel plan."""

    budget = state.get("budget", {})
    budget_total = float(budget.get("total", 0))
    current_cost = state.get("current_cost", 0.0)

    # -- Selected hotel summary ---------------------------------------------
    hotel_summary: dict[str, Any] | None = None
    selected_hotel_id = state.get("selected_hotel_id")
    if selected_hotel_id:
        for hotel in state.get("hotel_options", []):
            if hotel.get("id") == selected_hotel_id:
                hotel_summary = {
                    "id": hotel["id"],
                    "name": hotel.get("name", ""),
                    "stars": hotel.get("stars", 0),
                    "price_per_night": hotel.get("price_per_night", 0.0),
                    "address": hotel.get("address", ""),
                }
                break

    # -- Itinerary summary --------------------------------------------------
    itinerary_summary: dict[str, Any] = {}
    itinerary = state.get("optimized_itinerary")
    if itinerary:
        days = itinerary.get("days", [])
        itinerary_summary = {
            "total_days": len(days),
            "optimization_method": itinerary.get("optimization_method", ""),
            "unscheduled_count": len(itinerary.get("unscheduled_activity_ids", [])),
            "day_themes": [d.get("theme", "") for d in days],
            "warnings": itinerary.get("validation_warnings", []),
        }

    # -- Activity count -----------------------------------------------------
    selected_activity_ids = state.get("selected_activity_ids", [])

    # -- Trip dates ---------------------------------------------------------
    dates = state.get("dates", {})
    nights = _compute_nights(dates)

    return {
        "plan_id": state.get("plan_id", ""),
        "destination": state.get("destination", ""),
        "dates": dates,
        "nights": nights,
        "total_cost": current_cost,
        "budget_total": budget_total,
        "budget_variance": round(current_cost - budget_total, 2),
        "budget_currency": budget.get("currency", "USD"),
        "risk_flags": list(state.get("risk_flags", [])),
        "hotel": hotel_summary,
        "activity_count": len(selected_activity_ids),
        "itinerary": itinerary_summary,
        "revision_count": state.get("revision_count", 0),
        "message": (
            "Travel plan ready for review. "
            "Respond with: {'decision': 'approved'} or "
            "{'decision': 'rejected', 'feedback': '<reason>'}"
        ),
    }


# ---------------------------------------------------------------------------
# Decision parser
# ---------------------------------------------------------------------------


def _parse_decision(answer: Any) -> dict[str, str]:
    """Normalise the human's answer into a decision dict.

    Accepts:
    - ``{"decision": "approved"}``
    - ``{"decision": "rejected", "feedback": "..."}``
    - ``"approved"``  (string shorthand)
    - ``"rejected: reason"``  (string shorthand)
    """
    if isinstance(answer, dict):
        status = str(answer.get("decision", "rejected")).strip().lower()
        feedback = str(answer.get("feedback", "")).strip()
        return {"status": status, "feedback": feedback}

    if isinstance(answer, str):
        text = answer.strip().lower()
        if text == "approved":
            return {"status": "approved", "feedback": ""}
        if text.startswith("rejected"):
            # "rejected: reason" or just "rejected"
            parts = answer.split(":", 1)
            feedback = parts[1].strip() if len(parts) > 1 else ""
            return {"status": "rejected", "feedback": feedback}

    # Unrecognised format → reject for safety
    return {"status": "rejected", "feedback": f"Unrecognised answer format: {answer!r}"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _compute_nights(dates: dict[str, str]) -> int:
    """Calculate number of nights from travel dates."""
    start_raw = dates.get("start_date", "")
    end_raw = dates.get("end_date", "")

    if not start_raw or not end_raw:
        return 0

    try:
        start = datetime.date.fromisoformat(start_raw)
        end = datetime.date.fromisoformat(end_raw)
        return max((end - start).days, 1)
    except ValueError:
        return 0
