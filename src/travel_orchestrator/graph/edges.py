"""Conditional edge routing functions for the travel planner graph.

Each function receives the current ``TravelPlannerCore`` state and
returns a string key that the graph's ``path_map`` resolves to the
next node.  All functions are pure — no side-effects, no I/O.
"""

from __future__ import annotations

from travel_orchestrator.state.models import TravelPlannerCore
from travel_orchestrator.utils.logging import get_logger

logger = get_logger(__name__)

# Maximum number of re-optimisation loops before giving up and
# proceeding to risk check regardless of budget status.
MAX_REVISION_COUNT = 3

# Budget overshoot threshold (fraction).  When ``current_cost``
# exceeds ``budget.total * (1 + BUDGET_OVERSHOOT_THRESHOLD)`` the
# plan is sent back for re-optimisation.  This is combined with the
# traveler's own ``budget.flexibility`` — whichever is larger wins.
_BUDGET_OVERSHOOT_THRESHOLD = 0.10


# ---------------------------------------------------------------------------
# 1. Budget → optimise or proceed?
# ---------------------------------------------------------------------------


def should_optimize_costs(state: TravelPlannerCore) -> str:
    """Decide whether the plan needs cost re-optimisation.

    Compares ``current_cost`` against the allowed ceiling, which is
    the higher of:

    * ``budget.total * (1 + flexibility)``  (traveler's tolerance)
    * ``budget.total * 1.10``               (system 10 % hard cap)

    When the cost exceeds that ceiling **and** retries remain, the
    graph loops back to re-search.  Otherwise it proceeds to the
    risk-and-policy gate.

    Returns:
        ``"optimize_costs"`` — re-route to ``search_flights``
        ``"proceed"``        — continue to ``risk_and_policy_check``
    """
    budget = state.get("budget", {})
    budget_total = float(budget.get("total", 0))
    flexibility = float(budget.get("flexibility", 0))
    current_cost = state.get("current_cost", 0.0)
    revision_count = state.get("revision_count", 0)

    # Use the more generous of the two thresholds
    max_allowed = budget_total * (1 + max(flexibility, _BUDGET_OVERSHOOT_THRESHOLD))

    if current_cost > max_allowed and revision_count < MAX_REVISION_COUNT:
        logger.info(
            "budget_exceeded_rerouting",
            current_cost=current_cost,
            max_allowed=round(max_allowed, 2),
            revision_count=revision_count,
        )
        return "optimize_costs"

    return "proceed"


# ---------------------------------------------------------------------------
# 2. Approval → book or revise?
# ---------------------------------------------------------------------------


def process_approval_decision(state: TravelPlannerCore) -> str:
    """Route based on the human reviewer's decision.

    Called after ``present_for_approval`` resumes from its HITL
    interrupt.  The node sets ``approval_status`` to ``"approved"``
    or ``"rejected"`` before returning.

    Returns:
        ``"approved"``  — continue to ``book_services``
        ``"rejected"``  — route to ``process_feedback``
    """
    if state.get("approval_status") == "approved":
        return "approved"
    return "rejected"


# ---------------------------------------------------------------------------
# 3. Feedback → which node to revisit?
# ---------------------------------------------------------------------------

# Keywords (EN + PT) that hint at which service needs revision.
_FLIGHT_KEYWORDS = frozenset({"flight", "voo", "airline", "aéreo"})
_HOTEL_KEYWORDS = frozenset({"hotel", "hospedagem", "accommodation", "alojamento"})
_ACTIVITY_KEYWORDS = frozenset({
    "activity", "atividade", "itinerary", "itinerário",
    "passeio", "tour", "excursion", "excursão",
})


def determine_revision_target(state: TravelPlannerCore) -> str:
    """Decide which search node to revisit after a plan rejection.

    Parses the ``feedback:`` entries in ``risk_flags`` (written by
    ``present_for_approval`` on rejection) plus the full flag text
    to determine the area that needs revision.

    Returns:
        ``"search_flights"``    — re-search flight options
        ``"search_hotels"``     — re-search hotel options
        ``"search_activities"`` — re-search activity options
    """
    # Collect all text sources for keyword matching
    parts: list[str] = []

    # Explicit feedback from the reviewer
    for flag in state.get("risk_flags", []):
        if flag.startswith("feedback:"):
            parts.append(flag)

    # Fall back to scanning all flags if no explicit feedback
    if not parts:
        parts = list(state.get("risk_flags", []))

    text = " ".join(parts).lower()

    if _any_keyword(text, _FLIGHT_KEYWORDS):
        return "search_flights"
    if _any_keyword(text, _HOTEL_KEYWORDS):
        return "search_hotels"
    if _any_keyword(text, _ACTIVITY_KEYWORDS):
        return "search_activities"

    # No recognisable hint → full re-optimisation from flights
    return "search_flights"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _any_keyword(text: str, keywords: frozenset[str]) -> bool:
    """Return ``True`` if any keyword appears in *text*."""
    return any(kw in text for kw in keywords)
