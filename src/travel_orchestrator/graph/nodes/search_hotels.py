"""``search_hotels`` graph node.

Searches for hotel accommodations at the destination.  Responsible for:

1. Computing the hotel budget (~35 % of total budget).
2. Deriving search parameters from the traveler profile
   (minimum stars, location preference).
3. Calling the hotel MCP server to fetch scored options.
4. Converting results to ``HotelOption`` TypedDicts.
5. Keeping the top 5 options and selecting the best one.
6. Updating ``current_cost`` with the selected hotel's total price.
"""

from __future__ import annotations

import datetime
import time
from typing import Any

from travel_orchestrator.mcp_servers.hotels.client import search_hotels
from travel_orchestrator.state.models import HotelOption, TravelPlannerCore
from travel_orchestrator.utils.logging import get_logger, log_node_execution

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Budget & search constants
# ---------------------------------------------------------------------------

_HOTEL_BUDGET_RATIO = 0.35  # 35 % of total budget goes to accommodation
_MAX_OPTIONS = 5

# Accommodation-type → minimum stars mapping
_ACCOMMODATION_MIN_STARS: dict[str, int | None] = {
    "luxury": 4,
    "hotel": 3,
    "mid-range": 3,
    "budget": None,
    "hostel": None,
    "airbnb": None,
}

# Pace → location centrality mapping (higher = prefer central)
_PACE_CENTRALITY: dict[str, float] = {
    "fast": 0.8,
    "moderate": 0.5,
    "slow": 0.3,
}


@log_node_execution("search_hotels")
async def search_hotels_node(
    state: TravelPlannerCore,
) -> TravelPlannerCore:
    """Query hotel sources, score and select the best option."""

    destination = state["destination"]
    dates = state["dates"]
    start_date = dates["start_date"]
    end_date = dates["end_date"]

    nights = (
        datetime.date.fromisoformat(end_date)
        - datetime.date.fromisoformat(start_date)
    ).days
    if nights <= 0:
        nights = 1

    # -- 1. Compute hotel budget -------------------------------------------
    budget = state.get("budget", {})
    total_budget = float(budget.get("total", 0))
    hotel_budget = total_budget * _HOTEL_BUDGET_RATIO
    budget_per_night = hotel_budget / nights if nights > 0 else hotel_budget

    logger.info(
        "hotel_budget_computed",
        total_budget=total_budget,
        hotel_budget=round(hotel_budget, 2),
        budget_per_night=round(budget_per_night, 2),
        nights=nights,
    )

    # -- 2. Derive search parameters from traveler profile -----------------
    profile = state.get("traveler_profile", {})
    group_size = int(profile.get("group_size", 1))  # type: ignore[arg-type]

    accommodation_type = str(profile.get("accommodation_type", "hotel"))
    min_stars = _ACCOMMODATION_MIN_STARS.get(accommodation_type)

    pace = str(profile.get("pace", "moderate"))
    location_centrality = _PACE_CENTRALITY.get(pace, 0.5)

    # -- 3. Call hotel search (non-blocking) -------------------------------
    from travel_orchestrator.api.ws_orchestrator import emit_tool_call, emit_agent_log

    raw_options: list[dict[str, Any]] = []
    try:
        search_params = {
            "destination": destination, "check_in": start_date,
            "check_out": end_date, "guests": group_size,
        }
        await emit_agent_log(
            node="search_hotels", log_type="tool_call",
            message="Calling search_hotels on hotels-mcp",
        )
        t0 = time.time()
        raw_options = await search_hotels(
            destination=destination,
            check_in=start_date,
            check_out=end_date,
            guests=group_size,
            location_centrality=location_centrality,
            min_stars=min_stars,
        )
        elapsed = (time.time() - t0) * 1000
        await emit_tool_call(
            node="search_hotels", tool="search_hotels",
            server="hotels-mcp", params=search_params,
            result={"count": len(raw_options)}, duration_ms=elapsed,
        )
        logger.info(
            "hotel_search_completed",
            destination=destination,
            results=len(raw_options),
        )
    except Exception as exc:
        logger.warning("hotel_search_failed", error=str(exc))

    # -- 4. Filter by budget per night & convert to HotelOption -----------
    hotel_options: list[HotelOption] = []
    for idx, raw in enumerate(raw_options):
        nightly = raw.get("nightly_price_avg") or 0.0
        # Allow up to 20% over budget-per-night for flexibility
        if nightly > budget_per_night * 1.2 and budget_per_night > 0:
            continue

        hotel_options.append(_to_hotel_option(raw, idx))

        if len(hotel_options) >= _MAX_OPTIONS:
            break

    logger.info(
        "hotel_options_filtered",
        total_returned=len(raw_options),
        within_budget=len(hotel_options),
        budget_per_night=round(budget_per_night, 2),
    )

    # -- 5. Select best option & update cost ------------------------------
    selected_id: str | None = state.get("selected_hotel_id")
    hotel_cost = 0.0

    if hotel_options:
        best = hotel_options[0]  # already sorted by score from server
        selected_id = best["id"]
        hotel_cost = best["price_per_night"] * nights

        logger.info(
            "hotel_selected",
            hotel_id=selected_id,
            hotel_name=best["name"],
            stars=best["stars"],
            price_per_night=best["price_per_night"],
            total_cost=round(hotel_cost, 2),
            score=best["score"],
        )

    current_cost = state.get("current_cost", 0.0) + hotel_cost

    return {
        **state,
        "hotel_options": hotel_options,
        "selected_hotel_id": selected_id,
        "current_cost": round(current_cost, 2),
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _to_hotel_option(raw: dict[str, Any], idx: int) -> HotelOption:
    """Convert a scored hotel result dict to a ``HotelOption`` TypedDict."""
    location = raw.get("location", {})
    return {
        "id": f"htl-{idx:03d}",
        "name": raw.get("name", "Unknown"),
        "address": location.get("area") or raw.get("area", ""),
        "coordinates": {
            "lat": location.get("lat", 0.0),
            "lng": location.get("lng", 0.0),
        },
        "stars": raw.get("stars") or 0,
        "price_per_night": raw.get("nightly_price_avg") or 0.0,
        "currency": raw.get("currency") or "EUR",
        "amenities": raw.get("amenities") or [],
        "reviews_score": raw.get("review_score") or 0.0,
        "distance_to_center_km": raw.get("distance_to_center_km") or 0.0,
        "score": raw.get("score", 0.0),
    }
