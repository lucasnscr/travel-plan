"""``calculate_budget`` graph node.

Final budget reconciliation node.  Responsible for:

1. Recalculating the total trip cost from scratch based on the
   currently selected services (flight, hotel, activities).
2. Running the deterministic budget validator to detect overruns.
3. Annotating ``risk_flags`` when the cost exceeds or approaches
   the traveler's budget.

The node intentionally recalculates from scratch — rather than
relying on accumulated ``current_cost`` — so that re-optimization
loops always produce an accurate total.
"""

from __future__ import annotations

import datetime

from travel_orchestrator.state.models import (
    Activity,
    HotelOption,
    TravelPlannerCore,
)
from travel_orchestrator.utils.logging import get_logger, log_node_execution
from travel_orchestrator.validators.itinerary_validator import ItineraryValidator

logger = get_logger(__name__)


@log_node_execution("calculate_budget")
async def calculate_budget_node(state: TravelPlannerCore) -> TravelPlannerCore:
    """Recalculate total cost, validate against budget, and flag overruns."""

    # -- 1. Resolve selected services ---------------------------------------
    flight_cost = _compute_flight_cost(state)
    hotel_cost = _compute_hotel_cost(state)
    activity_cost = _compute_activity_cost(state)

    total_cost = round(flight_cost + hotel_cost + activity_cost, 2)

    logger.info(
        "budget_calculated",
        flight_cost=round(flight_cost, 2),
        hotel_cost=round(hotel_cost, 2),
        activity_cost=round(activity_cost, 2),
        total_cost=total_cost,
    )

    # -- 2. Build intermediate state for validation -------------------------
    updated_state: TravelPlannerCore = {
        **state,
        "current_cost": total_cost,
    }

    # -- 3. Validate budget constraints -------------------------------------
    result = ItineraryValidator.validate_budget_constraints(updated_state)

    risk_flags: list[str] = list(state.get("risk_flags", []))

    # Remove stale budget flags from previous iterations
    risk_flags = [f for f in risk_flags if not f.startswith("budget:")]

    if not result["is_valid"]:
        for issue in result["issues"]:
            risk_flags.append(f"budget: {issue}")
        logger.warning(
            "budget_exceeded",
            issues=result["issues"],
            suggested_fixes=result["suggested_fixes"],
        )
    elif result["severity"] == "warning":
        for issue in result["issues"]:
            risk_flags.append(f"budget: {issue}")
        logger.info(
            "budget_near_limit",
            issues=result["issues"],
        )
    else:
        logger.info("budget_within_limits", total_cost=total_cost)

    return {
        **state,
        "current_cost": total_cost,
        "risk_flags": risk_flags,
    }


# ---------------------------------------------------------------------------
# Cost computation helpers
# ---------------------------------------------------------------------------


def _compute_flight_cost(state: TravelPlannerCore) -> float:
    """Compute total flight cost for the group.

    Looks up the selected flight in ``flight_options`` (when available)
    and multiplies by group size.  Returns 0 when no flight is selected
    or flight data is not yet available (search_flights stub).
    """
    selected_id = state.get("selected_flight_id")
    if not selected_id:
        return 0.0

    # flight_options is not yet a formal state field — handle gracefully
    flight_options: list[dict] = state.get("flight_options", [])  # type: ignore[typeddict-item]
    if not flight_options:
        return 0.0

    flight = next((f for f in flight_options if f.get("id") == selected_id), None)
    if not flight:
        return 0.0

    price = float(flight.get("price", 0.0))
    group_size = int(state.get("traveler_profile", {}).get("group_size", 1))  # type: ignore[arg-type]

    return price * group_size


def _compute_hotel_cost(state: TravelPlannerCore) -> float:
    """Compute total hotel cost for the stay.

    Finds the selected hotel in ``hotel_options`` and multiplies
    its nightly rate by the number of nights.
    """
    selected_id = state.get("selected_hotel_id")
    if not selected_id:
        return 0.0

    hotel_options: list[HotelOption] = state.get("hotel_options", [])
    hotel = next((h for h in hotel_options if h["id"] == selected_id), None)
    if not hotel:
        return 0.0

    nights = _compute_nights(state)
    return hotel["price_per_night"] * nights


def _compute_activity_cost(state: TravelPlannerCore) -> float:
    """Compute total cost of all selected activities."""
    selected_ids = set(state.get("selected_activity_ids", []))
    if not selected_ids:
        return 0.0

    activity_options: list[Activity] = state.get("activity_options", [])
    return sum(a["price"] for a in activity_options if a["id"] in selected_ids)


def _compute_nights(state: TravelPlannerCore) -> int:
    """Calculate the number of nights from travel dates."""
    dates = state.get("dates", {})
    start_raw = dates.get("start_date", "")
    end_raw = dates.get("end_date", "")

    if not start_raw or not end_raw:
        return 1

    try:
        start = datetime.date.fromisoformat(start_raw)
        end = datetime.date.fromisoformat(end_raw)
        nights = (end - start).days
        return max(nights, 1)
    except ValueError:
        return 1
