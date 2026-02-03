"""``risk_and_policy_check`` graph node.

Pre-approval gate that runs deterministic checks against the completed
travel plan.  Responsible for:

1. Checking travel advisory level for the destination (mock database).
2. Flagging plans that exceed the corporate approval threshold.
3. Detecting destination-specific restrictions (visa, health, etc.).
4. Recommending travel insurance when appropriate.
5. Surfacing weather-based advisories from ``destination_analysis``.

All checks are deterministic — no LLM calls.  The resulting
``risk_flags`` inform the human reviewer at the next HITL checkpoint.
"""

from __future__ import annotations

import datetime

from travel_orchestrator.state.models import TravelPlannerCore
from travel_orchestrator.utils.logging import get_logger, log_node_execution

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Risk-check constants
# ---------------------------------------------------------------------------

# Insurance recommendation thresholds
_INSURANCE_COST_THRESHOLD = 5000.0
_INSURANCE_DURATION_THRESHOLD_DAYS = 14

# Budget threshold prefix for flags managed by this node
_RISK_FLAG_PREFIX = "risk:"

# ---------------------------------------------------------------------------
# Mock travel advisory database
# ---------------------------------------------------------------------------
# Levels: GREEN (safe), YELLOW (caution), ORANGE (reconsider), RED (do not travel)

_TRAVEL_ADVISORY_LEVELS: dict[str, str] = {
    # Conflict / instability
    "syria": "RED",
    "yemen": "RED",
    "afghanistan": "RED",
    "libya": "RED",
    "somalia": "RED",
    "south sudan": "RED",
    "north korea": "RED",
    # Elevated caution
    "iraq": "ORANGE",
    "venezuela": "ORANGE",
    "haiti": "ORANGE",
    "myanmar": "ORANGE",
    # General caution
    "mexico": "YELLOW",
    "colombia": "YELLOW",
    "kenya": "YELLOW",
    "india": "YELLOW",
    "turkey": "YELLOW",
    "egypt": "YELLOW",
    "south africa": "YELLOW",
    "brazil": "YELLOW",
    "nigeria": "YELLOW",
    "pakistan": "YELLOW",
}

# Destinations requiring special documentation / preparation
_DESTINATION_RESTRICTIONS: dict[str, list[str]] = {
    "china": ["Visa required for most nationalities"],
    "russia": ["Visa required — apply well in advance"],
    "india": ["e-Visa or tourist visa required"],
    "australia": ["ETA or eVisitor required"],
    "brazil": ["Yellow fever vaccination recommended"],
    "saudi arabia": ["Tourist visa required", "Dress code restrictions apply"],
    "japan": ["No visa required for short stays (most nationalities)"],
    "cuba": ["Tourist card required", "Travel insurance mandatory"],
    "iran": ["Visa required", "Travel insurance mandatory"],
    "north korea": ["Organized tour mandatory", "Extreme travel restrictions"],
    "egypt": ["Visa on arrival or e-Visa available"],
    "kenya": ["e-Visa required", "Yellow fever vaccination may be required"],
    "tanzania": ["Visa required", "Yellow fever vaccination required from endemic areas"],
    "nepal": ["Visa on arrival available", "Altitude sickness risk for trekking"],
    "peru": ["Altitude sickness risk in Cusco/Machu Picchu region"],
    "tibet": ["Special permit required in addition to Chinese visa"],
}


@log_node_execution("risk_and_policy_check")
async def risk_and_policy_check_node(
    state: TravelPlannerCore,
) -> TravelPlannerCore:
    """Run deterministic risk and policy checks on the completed plan."""

    destination = state["destination"]
    total_cost = state.get("current_cost", 0.0)

    logger.info(
        "checking_risks",
        destination=destination,
        cost=total_cost,
    )

    # Start from existing flags, clearing stale risk: entries
    risk_flags: list[str] = [
        f for f in state.get("risk_flags", []) if not f.startswith(_RISK_FLAG_PREFIX)
    ]

    # -- 1. Travel advisory check -------------------------------------------
    advisory_flags = _check_travel_advisory(destination)
    risk_flags.extend(advisory_flags)

    # -- 2. Budget approval threshold check ---------------------------------
    threshold_flags = _check_approval_threshold(total_cost)
    risk_flags.extend(threshold_flags)

    # -- 3. Destination restrictions ----------------------------------------
    restriction_flags = _check_destination_restrictions(destination)
    risk_flags.extend(restriction_flags)

    # -- 4. Travel insurance recommendation ---------------------------------
    insurance_flags = _check_insurance_recommendation(state)
    risk_flags.extend(insurance_flags)

    # -- 5. Weather advisories from destination_analysis --------------------
    weather_flags = _check_weather_advisories(state)
    risk_flags.extend(weather_flags)

    new_risk_count = (
        len(advisory_flags)
        + len(threshold_flags)
        + len(restriction_flags)
        + len(insurance_flags)
        + len(weather_flags)
    )

    logger.info(
        "risk_check_completed",
        total_flags=len(risk_flags),
        new_flags=new_risk_count,
    )

    return {
        **state,
        "risk_flags": risk_flags,
    }


# ---------------------------------------------------------------------------
# Individual check functions
# ---------------------------------------------------------------------------


def _check_travel_advisory(destination: str) -> list[str]:
    """Look up mock travel advisory level for the destination.

    Returns risk flags for YELLOW / ORANGE / RED levels.
    GREEN and unknown destinations produce no flags.
    """
    key = destination.strip().lower()
    level = _TRAVEL_ADVISORY_LEVELS.get(key, "GREEN")

    flags: list[str] = []

    if level == "RED":
        flags.append(
            f"{_RISK_FLAG_PREFIX} Travel advisory RED for {destination} "
            "— do not travel. Consider alternative destination."
        )
    elif level == "ORANGE":
        flags.append(
            f"{_RISK_FLAG_PREFIX} Travel advisory ORANGE for {destination} "
            "— reconsider travel. Manager approval strongly recommended."
        )
    elif level == "YELLOW":
        flags.append(
            f"{_RISK_FLAG_PREFIX} Travel advisory YELLOW for {destination} "
            "— exercise increased caution."
        )

    if level != "GREEN":
        logger.info(
            "travel_advisory_flagged",
            destination=destination,
            level=level,
        )

    return flags


def _check_approval_threshold(total_cost: float) -> list[str]:
    """Flag when total cost exceeds the corporate approval threshold.

    Reads the threshold from settings.  Falls back to a sensible
    default if settings are unavailable (no .env file).
    """
    threshold = _get_approval_threshold()

    flags: list[str] = []
    if total_cost > threshold:
        flags.append(
            f"{_RISK_FLAG_PREFIX} Cost ({total_cost:.2f}) exceeds approval "
            f"threshold ({threshold:.2f}) — manager review required."
        )
        logger.warning(
            "requires_approval",
            cost=total_cost,
            threshold=threshold,
        )

    return flags


def _check_destination_restrictions(destination: str) -> list[str]:
    """Look up destination-specific restrictions (visa, health, etc.)."""
    key = destination.strip().lower()
    restrictions = _DESTINATION_RESTRICTIONS.get(key, [])

    flags: list[str] = []
    for restriction in restrictions:
        flags.append(f"{_RISK_FLAG_PREFIX} {destination}: {restriction}")

    if flags:
        logger.info(
            "destination_restrictions_found",
            destination=destination,
            count=len(flags),
        )

    return flags


def _check_insurance_recommendation(state: TravelPlannerCore) -> list[str]:
    """Recommend travel insurance based on cost, duration, and advisory level."""
    total_cost = state.get("current_cost", 0.0)
    destination = state["destination"].strip().lower()
    trip_days = _compute_trip_days(state)

    reasons: list[str] = []

    if total_cost > _INSURANCE_COST_THRESHOLD:
        reasons.append(f"high trip cost ({total_cost:.2f})")

    if trip_days > _INSURANCE_DURATION_THRESHOLD_DAYS:
        reasons.append(f"extended trip duration ({trip_days} days)")

    advisory_level = _TRAVEL_ADVISORY_LEVELS.get(destination, "GREEN")
    if advisory_level in ("ORANGE", "RED"):
        reasons.append(f"elevated travel advisory ({advisory_level})")

    # Check if destination mandates insurance
    restrictions = _DESTINATION_RESTRICTIONS.get(destination, [])
    mandatory = any("insurance mandatory" in r.lower() for r in restrictions)
    if mandatory:
        reasons.append("mandatory per destination regulations")

    flags: list[str] = []
    if reasons:
        reason_text = "; ".join(reasons)
        prefix = "Travel insurance mandatory" if mandatory else "Travel insurance recommended"
        flags.append(f"{_RISK_FLAG_PREFIX} {prefix}: {reason_text}.")

    return flags


def _check_weather_advisories(state: TravelPlannerCore) -> list[str]:
    """Surface travel advisories from the destination analysis weather data."""
    analysis = state.get("destination_analysis")
    if not analysis:
        return []

    advisories: list[str] = analysis.get("travel_advisories", [])
    if not advisories:
        return []

    # Only surface severe weather advisories as risk flags (not all)
    severe_keywords = ("severe", "extreme", "storm", "hurricane", "typhoon", "freezing")
    flags: list[str] = []
    for advisory in advisories:
        if any(kw in advisory.lower() for kw in severe_keywords):
            flags.append(f"{_RISK_FLAG_PREFIX} {advisory}")

    return flags


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_approval_threshold() -> float:
    """Read the approval threshold from settings, with graceful fallback."""
    try:
        from travel_orchestrator.config.settings import get_settings

        settings = get_settings()
        return settings.approval_threshold_usd
    except Exception:
        return 10_000.0  # sensible default


def _compute_trip_days(state: TravelPlannerCore) -> int:
    """Calculate the number of days from travel dates."""
    dates = state.get("dates", {})
    start_raw = dates.get("start_date", "")
    end_raw = dates.get("end_date", "")

    if not start_raw or not end_raw:
        return 1

    try:
        start = datetime.date.fromisoformat(start_raw)
        end = datetime.date.fromisoformat(end_raw)
        days = (end - start).days
        return max(days, 1)
    except ValueError:
        return 1
