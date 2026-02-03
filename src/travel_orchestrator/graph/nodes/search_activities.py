"""``search_activities`` graph node.

Searches for activities and attractions at the destination.  Responsible for:

1. Computing the activity budget (~20 % of total budget, leaving 5 % buffer).
2. Calculating the budget per day for activity filtering.
3. Calling the activity MCP server to fetch scored options.
4. Balancing indoor/outdoor selection based on the weather forecast.
5. Ensuring category diversity across the trip.
6. Selecting ~15 activities and storing IDs in state.
7. Updating ``current_cost`` with the total activity cost.
"""

from __future__ import annotations

import datetime
from typing import Any

from travel_orchestrator.mcp_servers.activities.client import discover_activities
from travel_orchestrator.state.models import Activity, TravelPlannerCore
from travel_orchestrator.utils.logging import get_logger, log_node_execution

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Budget & selection constants
# ---------------------------------------------------------------------------

_ACTIVITY_BUDGET_RATIO = 0.20  # 20 % of total budget for activities
_TARGET_ACTIVITIES = 15
_MAX_ACTIVITIES = 20
_MIN_INDOOR_RATIO = 0.20  # at least 20 % indoor even on sunny trips
_MIN_OUTDOOR_RATIO = 0.20  # at least 20 % outdoor even on rainy trips
_RAIN_THRESHOLD = 50.0  # rain_chance % above which a day counts as "rainy"
_BAD_CONDITIONS = frozenset({"thunderstorm", "storm", "heavy rain", "snow"})


@log_node_execution("search_activities")
async def search_activities_node(
    state: TravelPlannerCore,
) -> TravelPlannerCore:
    """Query activity sources, filter by weather/budget, and select best options."""

    destination = state["destination"]
    dates = state["dates"]
    start_date = dates["start_date"]
    end_date = dates["end_date"]

    num_days = (
        datetime.date.fromisoformat(end_date)
        - datetime.date.fromisoformat(start_date)
    ).days
    if num_days <= 0:
        num_days = 1

    # -- 1. Compute activity budget ----------------------------------------
    budget = state.get("budget", {})
    total_budget = float(budget.get("total", 0))
    activity_budget = total_budget * _ACTIVITY_BUDGET_RATIO
    budget_per_day = activity_budget / num_days if num_days > 0 else activity_budget

    logger.info(
        "activity_budget_computed",
        total_budget=total_budget,
        activity_budget=round(activity_budget, 2),
        budget_per_day=round(budget_per_day, 2),
        num_days=num_days,
    )

    # -- 2. Derive search params from profile ------------------------------
    profile = state.get("traveler_profile", {})
    interests: list[str] = list(profile.get("interests", []))  # type: ignore[arg-type]
    if not interests:
        interests = ["culture", "food"]

    # -- 3. Call activity search (non-blocking) ----------------------------
    raw_activities: list[dict[str, Any]] = []
    try:
        raw_activities = await discover_activities(
            destination=destination,
            interests=interests,
            start_date=start_date,
            end_date=end_date,
            budget_per_day=budget_per_day,
        )
        logger.info(
            "activity_search_completed",
            destination=destination,
            results=len(raw_activities),
        )
    except Exception as exc:
        logger.warning("activity_search_failed", error=str(exc))

    if not raw_activities:
        logger.info("no_activities_found", destination=destination)
        return {
            **state,
            "activity_options": [],
            "selected_activity_ids": [],
            "current_cost": state.get("current_cost", 0.0),
        }

    # -- 4. Compute indoor/outdoor target ratio from weather ---------------
    indoor_ratio = _compute_indoor_ratio(state)

    # -- 5. Select activities with category diversity & weather balance -----
    selected = _select_activities(
        raw_activities,
        target_count=min(_TARGET_ACTIVITIES, num_days * 3),
        indoor_ratio=indoor_ratio,
        budget_per_day=budget_per_day,
    )

    # -- 6. Convert to Activity TypedDicts & compute cost ------------------
    activity_options: list[Activity] = []
    total_activity_cost = 0.0

    for raw in selected:
        activity: Activity = _to_activity(raw)
        activity_options.append(activity)
        total_activity_cost += activity["price"]

    # Cap at budget with 20 % flexibility
    if activity_budget > 0 and total_activity_cost > activity_budget * 1.2:
        activity_options, total_activity_cost = _trim_to_budget(
            activity_options, activity_budget * 1.2
        )

    selected_ids = [a["id"] for a in activity_options]
    current_cost = state.get("current_cost", 0.0) + total_activity_cost

    logger.info(
        "activities_selected",
        count=len(activity_options),
        total_activity_cost=round(total_activity_cost, 2),
        current_cost=round(current_cost, 2),
        indoor_ratio=round(indoor_ratio, 2),
    )

    return {
        **state,
        "activity_options": activity_options,
        "selected_activity_ids": selected_ids,
        "current_cost": round(current_cost, 2),
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _compute_indoor_ratio(state: TravelPlannerCore) -> float:
    """Determine the target indoor activity ratio from the weather forecast.

    Returns a float between 0.0 and 1.0 indicating how many activities
    should be indoor.  Uses the destination analysis forecast if available.
    """
    analysis = state.get("destination_analysis")
    if not analysis:
        return 0.5  # no forecast → balanced default

    forecast = analysis.get("forecast", [])
    if not forecast:
        return 0.5

    rainy_days = 0
    for day in forecast:
        condition = day.get("condition", "").lower()
        rain_chance = day.get("rain_chance", 0.0)
        if rain_chance >= _RAIN_THRESHOLD or condition in _BAD_CONDITIONS:
            rainy_days += 1

    ratio = rainy_days / len(forecast)

    # Clamp to ensure minimum diversity
    return max(_MIN_INDOOR_RATIO, min(1.0 - _MIN_OUTDOOR_RATIO, ratio))


def _select_activities(
    raw: list[dict[str, Any]],
    target_count: int,
    indoor_ratio: float,
    budget_per_day: float,
) -> list[dict[str, Any]]:
    """Select activities balancing indoor/outdoor and category diversity.

    Already-sorted by score from the MCP server (descending).
    """
    target_count = min(target_count, _MAX_ACTIVITIES)
    if target_count <= 0:
        target_count = _TARGET_ACTIVITIES

    target_indoor = max(1, round(target_count * indoor_ratio))
    target_outdoor = max(1, target_count - target_indoor)

    # Track category counts for diversity
    category_counts: dict[str, int] = {}
    max_per_category = max(target_count // 3, 2)

    indoor_selected: list[dict[str, Any]] = []
    outdoor_selected: list[dict[str, Any]] = []

    for activity in raw:
        cat = activity.get("category", "other")
        is_indoor = activity.get("indoor", False)

        # Category cap
        if category_counts.get(cat, 0) >= max_per_category:
            continue

        if is_indoor and len(indoor_selected) < target_indoor:
            indoor_selected.append(activity)
            category_counts[cat] = category_counts.get(cat, 0) + 1
        elif not is_indoor and len(outdoor_selected) < target_outdoor:
            outdoor_selected.append(activity)
            category_counts[cat] = category_counts.get(cat, 0) + 1

        if (
            len(indoor_selected) >= target_indoor
            and len(outdoor_selected) >= target_outdoor
        ):
            break

    # If one bucket is underfilled, top up from the other side
    combined = indoor_selected + outdoor_selected
    if len(combined) < target_count:
        seen_ids = {a.get("id") or a.get("name") for a in combined}
        for activity in raw:
            key = activity.get("id") or activity.get("name")
            if key in seen_ids:
                continue
            cat = activity.get("category", "other")
            if category_counts.get(cat, 0) >= max_per_category:
                continue
            combined.append(activity)
            category_counts[cat] = category_counts.get(cat, 0) + 1
            seen_ids.add(key)
            if len(combined) >= target_count:
                break

    return combined


def _to_activity(raw: dict[str, Any]) -> Activity:
    """Convert a raw activity dict from the MCP server to an ``Activity``."""
    return {
        "id": raw.get("id", "act-unknown"),
        "name": raw.get("name", "Unknown"),
        "category": raw.get("category", "other"),
        "address": raw.get("address", ""),
        "coordinates": raw.get("coordinates", {"lat": 0.0, "lng": 0.0}),
        "duration_minutes": raw.get("duration_minutes", 60),
        "price": raw.get("price", 0.0),
        "currency": raw.get("currency", "EUR"),
        "opening_hours": raw.get("opening_hours", {}),
        "requires_booking": raw.get("requires_booking", False),
        "indoor": raw.get("indoor", False),
        "description": raw.get("description", ""),
        "score": raw.get("score", 0.0),
    }


def _trim_to_budget(
    activities: list[Activity],
    max_cost: float,
) -> tuple[list[Activity], float]:
    """Remove lowest-scored activities until total cost is within budget."""
    # Sort by score ascending so we drop least valuable first
    ranked = sorted(activities, key=lambda a: a["score"])
    total = sum(a["price"] for a in activities)

    while total > max_cost and ranked:
        dropped = ranked.pop(0)
        total -= dropped["price"]

    # Return in original order (by score descending)
    kept_ids = {a["id"] for a in ranked}
    result = [a for a in activities if a["id"] in kept_ids]
    return result, round(total, 2)
