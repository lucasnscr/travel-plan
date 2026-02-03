"""``optimize_itinerary`` graph node.

Hybrid LLM + deterministic validator approach:

1. The Anthropic LLM proposes a day-by-day itinerary grouping activities.
2. Deterministic validators check feasibility (geographic coherence,
   timing conflicts, weather/outdoor risks) per day.
3. If invalid, the LLM repairs with structured feedback from validators.
4. Maximum 3 iterations.  Falls back to a deterministic algorithm when
   the LLM is unavailable (no API key, network error, etc.).
"""

from __future__ import annotations

import datetime
import json
from collections import Counter
from typing import Any

from travel_orchestrator.config.constants import (
    DEFAULT_DAY_END_HOUR,
    DEFAULT_DAY_START_HOUR,
    MAX_ACTIVITIES_PER_DAY,
    MAX_DAILY_TRAVEL_TIME_MINUTES,
    MAX_OPTIMIZATION_ITERATIONS,
    PACE_ACTIVITIES_PER_DAY,
    RAIN_THRESHOLD_FOR_INDOOR,
    TRAVEL_BUFFER_MINUTES,
)
from travel_orchestrator.state.models import (
    Activity,
    HotelOption,
    ItineraryDay,
    ItinerarySlot,
    OptimizedItinerary,
    TravelPlannerCore,
    ValidationResult,
    WeatherForecast,
)
from travel_orchestrator.utils.logging import get_logger, log_node_execution
from travel_orchestrator.validators.itinerary_validator import (
    ItineraryValidator,
    _haversine_distance,
)
from travel_orchestrator.validators.weather_validator import WeatherValidator

logger = get_logger(__name__)

# Average urban speed used by the deterministic fallback (same as validators).
_AVERAGE_URBAN_SPEED_KMH = 30.0

# Theme labels derived from activity categories.
_CATEGORY_THEMES: dict[str, str] = {
    "museum": "Art & Culture",
    "tour": "City Exploration",
    "restaurant": "Gastronomy",
    "nature": "Nature & Outdoors",
    "shopping": "Shopping & Leisure",
    "nightlife": "Evening Entertainment",
}


# ---------------------------------------------------------------------------
# Main node
# ---------------------------------------------------------------------------


@log_node_execution("optimize_itinerary")
async def optimize_itinerary_node(
    state: TravelPlannerCore,
) -> TravelPlannerCore:
    """Build a day-by-day itinerary from selected hotel, activities, and weather."""

    # -- 1. Resolve inputs -------------------------------------------------
    activities = _resolve_selected_activities(state)
    hotel = _resolve_selected_hotel(state)
    trip_dates = _compute_trip_dates(state)
    forecast_map = _build_forecast_map(state)
    pace = str(state.get("traveler_profile", {}).get("pace", "moderate"))
    target_per_day = PACE_ACTIVITIES_PER_DAY.get(pace, 3)

    if not activities:
        logger.warning("no_activities_to_schedule")
        return {**state, "optimized_itinerary": _empty_itinerary()}

    if not hotel:
        logger.warning("no_hotel_selected_for_itinerary")
        return {**state, "optimized_itinerary": _empty_itinerary()}

    logger.info(
        "optimizing_itinerary",
        activities_count=len(activities),
        trip_days=len(trip_dates),
        target_per_day=target_per_day,
        pace=pace,
    )

    # -- 2. Attempt LLM-based optimization ---------------------------------
    itinerary_days: list[ItineraryDay] | None = None
    unscheduled: list[str] = []
    method = "deterministic_fallback"
    iterations = 0

    client = _get_anthropic_client()
    if client is not None:
        try:
            itinerary_days, unscheduled, iterations = await _llm_optimize_loop(
                client=client,
                activities=activities,
                hotel=hotel,
                trip_dates=trip_dates,
                forecast_map=forecast_map,
                target_per_day=target_per_day,
                state=state,
            )
            method = "llm"
        except Exception as exc:
            logger.warning("llm_optimization_failed_using_fallback", error=str(exc))

    # -- 3. Deterministic fallback -----------------------------------------
    if itinerary_days is None:
        itinerary_days, unscheduled = _deterministic_fallback(
            activities=activities,
            hotel=hotel,
            trip_dates=trip_dates,
            forecast_map=forecast_map,
            target_per_day=target_per_day,
        )

    # -- 4. Final informational warnings -----------------------------------
    final_warnings = _collect_final_warnings(itinerary_days)

    # -- 5. Build output ---------------------------------------------------
    optimized: OptimizedItinerary = {
        "days": itinerary_days,
        "unscheduled_activity_ids": unscheduled,
        "optimization_method": method,
        "validation_iterations": iterations,
        "validation_warnings": final_warnings,
    }

    logger.info(
        "itinerary_optimized",
        method=method,
        iterations=iterations,
        days=len(itinerary_days),
        total_slots=sum(len(d["slots"]) for d in itinerary_days),
        unscheduled=len(unscheduled),
        warnings=len(final_warnings),
    )

    return {**state, "optimized_itinerary": optimized}


# ---------------------------------------------------------------------------
# LLM optimization loop
# ---------------------------------------------------------------------------


async def _llm_optimize_loop(
    *,
    client: Any,
    activities: list[Activity],
    hotel: HotelOption,
    trip_dates: list[str],
    forecast_map: dict[str, WeatherForecast],
    target_per_day: int,
    state: TravelPlannerCore,
) -> tuple[list[ItineraryDay], list[str], int]:
    """Run the generate → validate → repair loop up to MAX_OPTIMIZATION_ITERATIONS."""

    settings = _get_settings_safe()
    system_prompt = _build_system_prompt()
    user_prompt = _build_initial_prompt(
        activities=activities,
        hotel=hotel,
        trip_dates=trip_dates,
        forecast_map=forecast_map,
        target_per_day=target_per_day,
        state=state,
    )

    messages: list[dict[str, str]] = [{"role": "user", "content": user_prompt}]
    itinerary_days: list[ItineraryDay] = []
    unscheduled: list[str] = []

    model = settings.get("model_name", "claude-sonnet-4-20250514") if settings else "claude-sonnet-4-20250514"
    temperature = settings.get("temperature", 0.3) if settings else 0.3
    max_tokens = settings.get("max_tokens", 4096) if settings else 4096

    for iteration in range(1, MAX_OPTIMIZATION_ITERATIONS + 1):
        logger.info("llm_iteration_start", iteration=iteration)

        raw_response = await _call_llm(
            client=client,
            system=system_prompt,
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        itinerary_days, unscheduled = _parse_llm_response(
            raw_response, activities, trip_dates, forecast_map,
        )

        # Validate
        all_issues = _validate_itinerary(itinerary_days, hotel, forecast_map, activities)
        errors = [r for r in all_issues if r["severity"] == "error"]

        if not errors:
            logger.info("itinerary_valid", iteration=iteration)
            return itinerary_days, unscheduled, iteration

        logger.info(
            "itinerary_invalid_repairing",
            iteration=iteration,
            error_count=len(errors),
        )
        messages.append({"role": "assistant", "content": raw_response})
        messages.append({"role": "user", "content": _build_repair_prompt(all_issues)})

    # Exhausted iterations — return last attempt
    logger.warning("max_iterations_reached", iterations=MAX_OPTIMIZATION_ITERATIONS)
    return itinerary_days, unscheduled, MAX_OPTIMIZATION_ITERATIONS


# ---------------------------------------------------------------------------
# Anthropic client helpers
# ---------------------------------------------------------------------------


def _get_anthropic_client() -> Any | None:
    """Create an ``AsyncAnthropic`` client, or ``None`` if unavailable."""
    try:
        from anthropic import AsyncAnthropic

        from travel_orchestrator.config.settings import get_settings

        settings = get_settings()
        api_key = settings.anthropic_api_key
        if not api_key:
            logger.warning("no_anthropic_api_key")
            return None
        return AsyncAnthropic(api_key=api_key)
    except Exception as exc:
        logger.warning("anthropic_client_unavailable", error=str(exc))
        return None


def _get_settings_safe() -> dict[str, Any] | None:
    """Return settings as a plain dict, or ``None`` if unavailable."""
    try:
        from travel_orchestrator.config.settings import get_settings

        s = get_settings()
        return {
            "model_name": s.model_name,
            "temperature": s.temperature,
            "max_tokens": s.max_tokens,
        }
    except Exception:
        return None


async def _call_llm(
    *,
    client: Any,
    system: str,
    messages: list[dict[str, str]],
    model: str,
    temperature: float,
    max_tokens: int,
) -> str:
    """Invoke the Anthropic messages API and return the text content."""
    response = await client.messages.create(
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        system=system,
        messages=messages,
    )
    return response.content[0].text


# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------


def _build_system_prompt() -> str:
    return (
        "You are a travel itinerary optimizer. You receive a list of selected "
        "activities, hotel location, daily weather forecasts, and traveler "
        "preferences. Your job is to arrange activities into a day-by-day "
        "schedule that:\n\n"
        "1. Respects opening hours (never schedule an activity when it's closed).\n"
        "2. Groups geographically close activities on the same day to minimize "
        "travel time.\n"
        "3. Accounts for weather (prefer indoor activities on rainy days, "
        "outdoor on sunny days).\n"
        "4. Matches the traveler's pace preference (activities per day target).\n"
        "5. Orders activities within each day to minimize backtracking.\n"
        f"6. Never exceeds {MAX_ACTIVITIES_PER_DAY} activities per day.\n"
        "7. Assigns realistic start/end times with travel time between "
        "activities.\n\n"
        "You MUST respond with valid JSON only, no markdown fences, no "
        "commentary outside the JSON. Follow the exact schema provided in "
        "the user message."
    )


def _build_initial_prompt(
    *,
    activities: list[Activity],
    hotel: HotelOption,
    trip_dates: list[str],
    forecast_map: dict[str, WeatherForecast],
    target_per_day: int,
    state: TravelPlannerCore,
) -> str:
    activity_summaries = []
    for a in activities:
        activity_summaries.append({
            "id": a["id"],
            "name": a["name"],
            "category": a["category"],
            "duration_minutes": a["duration_minutes"],
            "indoor": a["indoor"],
            "coordinates": a["coordinates"],
            "opening_hours": a.get("opening_hours", {}),
            "price": a["price"],
        })

    daily_weather = []
    for date in trip_dates:
        fc = forecast_map.get(date)
        if fc:
            daily_weather.append({
                "date": date,
                "condition": fc["condition"],
                "temp_max": fc["temp_max"],
                "temp_min": fc["temp_min"],
                "rain_chance": fc["rain_chance"],
                "rain_start": fc.get("rain_start"),
            })
        else:
            daily_weather.append({"date": date, "condition": "unknown"})

    profile = state.get("traveler_profile", {})
    interests = profile.get("interests", [])

    prompt_data = {
        "hotel": {"name": hotel["name"], "coordinates": hotel["coordinates"]},
        "activities": activity_summaries,
        "trip_dates": trip_dates,
        "daily_weather": daily_weather,
        "target_activities_per_day": target_per_day,
        "traveler_interests": interests,
        "max_activities_per_day": MAX_ACTIVITIES_PER_DAY,
        "max_daily_travel_time_minutes": MAX_DAILY_TRAVEL_TIME_MINUTES,
    }

    schema = (
        '{\n  "days": [\n    {\n      "date": "YYYY-MM-DD",\n'
        '      "day_number": 1,\n      "theme": "short theme label",\n'
        '      "slots": [\n        {\n'
        '          "activity_id": "the activity id",\n'
        '          "activity_name": "the activity name",\n'
        '          "start_time": "HH:MM",\n'
        '          "end_time": "HH:MM",\n'
        '          "travel_time_from_previous_minutes": 0,\n'
        '          "notes": ""\n        }\n      ],\n'
        '      "notes": "day-level notes"\n    }\n  ],\n'
        '  "unscheduled_activity_ids": ["ids that could not fit"]\n}'
    )

    return (
        "Arrange the following activities into a day-by-day itinerary.\n\n"
        f"INPUT DATA:\n{json.dumps(prompt_data, indent=2, ensure_ascii=False)}\n\n"
        f"RESPOND with this exact JSON schema:\n{schema}\n\n"
        "RULES:\n"
        "- Every activity from the input must appear exactly once "
        "(either in a slot or in unscheduled).\n"
        "- Slots must not overlap in time.\n"
        "- end_time = start_time + duration_minutes (from activity data).\n"
        "- travel_time_from_previous_minutes for the first slot of a day "
        "is travel from hotel.\n"
        "- start_time of a slot must be >= end_time of previous slot + "
        "travel_time_from_previous_minutes.\n"
        "- Do not schedule activities outside their opening hours for that "
        "day of the week.\n"
        f"- On days with rain_chance >= {RAIN_THRESHOLD_FOR_INDOOR}%, prefer "
        "indoor activities; schedule outdoor ones only in dry windows.\n"
        f"- Target {target_per_day} activities per day, never exceed "
        f"{MAX_ACTIVITIES_PER_DAY}.\n"
        f"- Total inter-activity travel time per day must not exceed "
        f"{MAX_DAILY_TRAVEL_TIME_MINUTES} minutes.\n"
        "- JSON only, no commentary."
    )


def _build_repair_prompt(issues: list[ValidationResult]) -> str:
    issue_lines: list[str] = []
    for idx, result in enumerate(issues, 1):
        for problem in result["issues"]:
            issue_lines.append(f"  {idx}. [{result['severity'].upper()}] {problem}")
        for fix in result["suggested_fixes"]:
            issue_lines.append(f"     Suggested fix: {fix}")

    issues_text = "\n".join(issue_lines)

    return (
        "The itinerary you proposed has the following validation issues:\n\n"
        f"{issues_text}\n\n"
        "Please fix ALL issues and return the corrected itinerary in the same "
        "JSON schema.\n"
        "Do not remove activities unless absolutely necessary; prefer "
        "rearranging them between days.\n"
        "JSON only, no commentary."
    )


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------


def _parse_llm_response(
    raw: str,
    activities: list[Activity],
    trip_dates: list[str],
    forecast_map: dict[str, WeatherForecast],
) -> tuple[list[ItineraryDay], list[str]]:
    """Parse the LLM JSON response into ``ItineraryDay`` list."""
    text = raw.strip()
    # Strip markdown fences if present (defensive)
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3].rstrip()

    data = json.loads(text)

    activity_lookup = {a["id"]: a for a in activities}
    days_raw = data.get("days", [])
    unscheduled = data.get("unscheduled_activity_ids", [])

    itinerary_days: list[ItineraryDay] = []
    for day_raw in days_raw:
        date = day_raw["date"]
        slots: list[ItinerarySlot] = []
        for slot_raw in day_raw.get("slots", []):
            aid = slot_raw["activity_id"]
            act = activity_lookup.get(aid)
            slots.append({
                "activity_id": aid,
                "activity_name": slot_raw.get(
                    "activity_name",
                    act["name"] if act else "Unknown",
                ),
                "start_time": slot_raw["start_time"],
                "end_time": slot_raw["end_time"],
                "travel_time_from_previous_minutes": slot_raw.get(
                    "travel_time_from_previous_minutes", 0,
                ),
                "notes": slot_raw.get("notes", ""),
            })

        fc = forecast_map.get(date)
        itinerary_days.append({
            "date": date,
            "day_number": day_raw.get("day_number", 0),
            "theme": day_raw.get("theme", ""),
            "slots": slots,
            "weather_condition": fc["condition"] if fc else "unknown",
            "notes": day_raw.get("notes", ""),
        })

    return itinerary_days, unscheduled


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def _validate_itinerary(
    days: list[ItineraryDay],
    hotel: HotelOption,
    forecast_map: dict[str, WeatherForecast],
    all_activities: list[Activity],
) -> list[ValidationResult]:
    """Run all deterministic validators on the proposed itinerary."""
    activity_lookup = {a["id"]: a for a in all_activities}
    issues: list[ValidationResult] = []

    for day in days:
        date = day["date"]
        day_label = f"Day {day['day_number']} ({date})"
        day_activity_ids = [slot["activity_id"] for slot in day["slots"]]
        day_activities = [
            activity_lookup[aid]
            for aid in day_activity_ids
            if aid in activity_lookup
        ]

        # 1. Geographic coherence
        geo = ItineraryValidator.validate_geographic_coherence(day_activities, hotel)
        if not geo["is_valid"]:
            issues.append({
                "is_valid": False,
                "issues": [f"{day_label}: {i}" for i in geo["issues"]],
                "severity": geo["severity"],
                "suggested_fixes": geo["suggested_fixes"],
            })

        # 2. Timing conflicts
        timing = ItineraryValidator.validate_timing_conflicts(day_activities, date)
        if not timing["is_valid"]:
            issues.append({
                "is_valid": False,
                "issues": [f"{day_label}: {i}" for i in timing["issues"]],
                "severity": timing["severity"],
                "suggested_fixes": timing["suggested_fixes"],
            })

        # 3. Weather / outdoor
        forecast = forecast_map.get(date)
        if forecast:
            weather = WeatherValidator.validate_outdoor_activities(
                day_activities, forecast,
            )
            if not weather["is_valid"]:
                issues.append({
                    "is_valid": False,
                    "issues": [f"{day_label}: {i}" for i in weather["issues"]],
                    "severity": weather["severity"],
                    "suggested_fixes": weather["suggested_fixes"],
                })

    return issues


# ---------------------------------------------------------------------------
# Deterministic fallback
# ---------------------------------------------------------------------------


def _deterministic_fallback(
    *,
    activities: list[Activity],
    hotel: HotelOption,
    trip_dates: list[str],
    forecast_map: dict[str, WeatherForecast],
    target_per_day: int,
) -> tuple[list[ItineraryDay], list[str]]:
    """Group activities into days without any LLM call.

    Weather-aware, proximity-based, opening-hours-aware.
    """
    available = sorted(activities, key=lambda a: a["score"], reverse=True)

    indoor_pool = [a for a in available if a["indoor"]]
    outdoor_pool = [a for a in available if not a["indoor"]]

    assigned: set[str] = set()
    itinerary_days: list[ItineraryDay] = []
    activity_lookup = {a["id"]: a for a in activities}

    for day_idx, date in enumerate(trip_dates):
        forecast = forecast_map.get(date)
        is_indoor_day = False
        weather_condition = "unknown"
        if forecast:
            weather_condition = forecast["condition"]
            if forecast["rain_chance"] >= RAIN_THRESHOLD_FOR_INDOOR:
                is_indoor_day = True

        weekday = datetime.date.fromisoformat(date).strftime("%A").lower()

        # Pick primary and secondary pools
        if is_indoor_day:
            primary, secondary = indoor_pool, outdoor_pool
        else:
            primary, secondary = outdoor_pool, indoor_pool

        # Greedy select
        day_activities: list[Activity] = []
        for pool in [primary, secondary]:
            for act in pool:
                if act["id"] in assigned:
                    continue
                if len(day_activities) >= target_per_day:
                    break
                # Check opening hours
                hours = act.get("opening_hours", {})
                if weekday in hours and hours[weekday].lower() == "closed":
                    continue
                day_activities.append(act)
                assigned.add(act["id"])
            if len(day_activities) >= target_per_day:
                break

        # Order by nearest-neighbor from hotel
        day_activities = _nearest_neighbor_sort(day_activities, hotel)

        # Assign time slots
        slots = _assign_time_slots(day_activities, hotel, is_indoor_day)

        itinerary_days.append({
            "date": date,
            "day_number": day_idx + 1,
            "theme": _infer_theme(slots, activity_lookup),
            "slots": slots,
            "weather_condition": weather_condition,
            "notes": "Rain expected — indoor activities preferred" if is_indoor_day else "",
        })

    unscheduled = [a["id"] for a in activities if a["id"] not in assigned]
    return itinerary_days, unscheduled


def _assign_time_slots(
    day_activities: list[Activity],
    hotel: HotelOption,
    is_indoor_day: bool,
) -> list[ItinerarySlot]:
    """Assign start/end times to a day's activities."""
    slots: list[ItinerarySlot] = []
    h, m = DEFAULT_DAY_START_HOUR.split(":")
    current = datetime.datetime(2000, 1, 1, int(h), int(m))
    end_h = int(DEFAULT_DAY_END_HOUR.split(":")[0])

    prev_lat = hotel["coordinates"]["lat"]
    prev_lng = hotel["coordinates"]["lng"]

    for act in day_activities:
        travel_km = _haversine_distance(
            prev_lat, prev_lng,
            act["coordinates"]["lat"], act["coordinates"]["lng"],
        )
        travel_minutes = int((travel_km / _AVERAGE_URBAN_SPEED_KMH) * 60)
        buffer = travel_minutes + TRAVEL_BUFFER_MINUTES

        start = current + datetime.timedelta(minutes=buffer)
        end = start + datetime.timedelta(minutes=act["duration_minutes"])

        if end.hour >= end_h and end.minute > 0:
            # Doesn't fit — skip
            continue

        note = ""
        if is_indoor_day and act["indoor"]:
            note = "Indoor alternative due to weather"

        slots.append({
            "activity_id": act["id"],
            "activity_name": act["name"],
            "start_time": start.strftime("%H:%M"),
            "end_time": end.strftime("%H:%M"),
            "travel_time_from_previous_minutes": travel_minutes,
            "notes": note,
        })
        current = end
        prev_lat = act["coordinates"]["lat"]
        prev_lng = act["coordinates"]["lng"]

    return slots


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def _resolve_selected_activities(state: TravelPlannerCore) -> list[Activity]:
    """Filter ``activity_options`` to only those in ``selected_activity_ids``."""
    selected_ids = set(state.get("selected_activity_ids", []))
    if not selected_ids:
        return list(state.get("activity_options", []))
    return [a for a in state.get("activity_options", []) if a["id"] in selected_ids]


def _resolve_selected_hotel(state: TravelPlannerCore) -> HotelOption | None:
    """Find the selected hotel from ``hotel_options``."""
    selected_id = state.get("selected_hotel_id")
    if not selected_id:
        return None
    for h in state.get("hotel_options", []):
        if h["id"] == selected_id:
            return h
    return None


def _compute_trip_dates(state: TravelPlannerCore) -> list[str]:
    """Return list of ISO date strings from start to end (exclusive end)."""
    dates = state.get("dates", {})
    start = datetime.date.fromisoformat(dates["start_date"])
    end = datetime.date.fromisoformat(dates["end_date"])
    result: list[str] = []
    current = start
    while current < end:
        result.append(current.isoformat())
        current += datetime.timedelta(days=1)
    if not result:
        result.append(start.isoformat())
    return result


def _build_forecast_map(state: TravelPlannerCore) -> dict[str, WeatherForecast]:
    """Build date→WeatherForecast lookup from ``destination_analysis``."""
    analysis = state.get("destination_analysis")
    if not analysis:
        return {}
    return {f["date"]: f for f in analysis.get("forecast", [])}


def _nearest_neighbor_sort(
    activities: list[Activity],
    hotel: HotelOption,
) -> list[Activity]:
    """Order activities in nearest-neighbour sequence starting from hotel."""
    if not activities:
        return []

    remaining = list(activities)
    ordered: list[Activity] = []
    prev_lat = hotel["coordinates"]["lat"]
    prev_lng = hotel["coordinates"]["lng"]

    while remaining:
        nearest = min(
            remaining,
            key=lambda a: _haversine_distance(
                prev_lat, prev_lng,
                a["coordinates"]["lat"], a["coordinates"]["lng"],
            ),
        )
        ordered.append(nearest)
        remaining.remove(nearest)
        prev_lat = nearest["coordinates"]["lat"]
        prev_lng = nearest["coordinates"]["lng"]

    return ordered


def _infer_theme(
    slots: list[ItinerarySlot],
    activity_lookup: dict[str, Activity],
) -> str:
    """Derive a day theme from the dominant activity category."""
    if not slots:
        return "Free Day"
    categories = [
        activity_lookup[s["activity_id"]]["category"]
        for s in slots
        if s["activity_id"] in activity_lookup
    ]
    if not categories:
        return "Exploration"
    dominant = Counter(categories).most_common(1)[0][0]
    return _CATEGORY_THEMES.get(dominant, dominant.title())


def _empty_itinerary() -> OptimizedItinerary:
    """Return an empty itinerary for edge cases."""
    return {
        "days": [],
        "unscheduled_activity_ids": [],
        "optimization_method": "none",
        "validation_iterations": 0,
        "validation_warnings": ["No activities or hotel available for scheduling"],
    }


def _collect_final_warnings(days: list[ItineraryDay]) -> list[str]:
    """Collect remaining informational warnings from the final itinerary."""
    warnings: list[str] = []
    for day in days:
        if not day["slots"]:
            warnings.append(
                f"Day {day['day_number']} ({day['date']}) has no scheduled activities"
            )
    return warnings
