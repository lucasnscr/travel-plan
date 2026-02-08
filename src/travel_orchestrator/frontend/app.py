"""Business logic for the travel orchestrator frontend.

This module contains the core planning pipeline and approval workflow.
The web UI is served by ``frontend.server`` (FastAPI + static SPA).
"""

from __future__ import annotations

import html as html_lib
import json
import os
import tempfile
import time
import uuid
from typing import Any

from travel_orchestrator.multimodal.audio_processor import populate_state_from_audio
from travel_orchestrator.multimodal.image_analyzer import analyze_inspiration_image
from travel_orchestrator.multimodal.pdf_parser import parse_competitor_offer_pdf
from travel_orchestrator.output.map_generator import generate_map_from_state
from travel_orchestrator.output.pdf_generator import generate_pdf_from_state
from travel_orchestrator.utils.logging import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Module-level state cache for approval workflow
# ---------------------------------------------------------------------------

_last_result_state: dict[str, Any] = {}


# ---------------------------------------------------------------------------
# State builder
# ---------------------------------------------------------------------------


def _empty_state() -> dict[str, Any]:
    """Return a fresh TravelPlannerCore-compatible dict with defaults."""
    return {
        "plan_id": "",
        "destination": "",
        "dates": {"start_date": "", "end_date": ""},
        "budget": {"total": 0.0, "currency": "USD", "flexibility": 0.1},
        "traveler_profile": {"interests": [], "pace": "moderate", "group_size": 2},
        "selected_flight_id": None,
        "selected_hotel_id": None,
        "selected_activity_ids": [],
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


def _build_initial_state(
    *,
    destination: str,
    start_date: str,
    end_date: str,
    budget_total: float,
    currency: str,
    group_size: int,
    interests: list[str],
    audio_state: dict[str, Any] | None = None,
    image_vibe: dict[str, Any] | None = None,
    competitor_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a TravelPlannerCore-compatible dict from inputs.

    Merges text inputs with optional multimodal enrichment.
    Audio state is used as a base (lowest priority); text inputs
    always override.
    """
    # Start from audio state if available, else empty
    state: dict[str, Any] = dict(audio_state) if audio_state else _empty_state()

    # Text inputs always override
    state["plan_id"] = f"plan_{uuid.uuid4().hex[:8]}"
    if destination:
        state["destination"] = destination
    if start_date or end_date:
        state["dates"] = {
            "start_date": start_date or state.get("dates", {}).get("start_date", ""),
            "end_date": end_date or state.get("dates", {}).get("end_date", ""),
        }
    state["budget"] = {"total": budget_total, "currency": currency, "flexibility": 0.1}

    # Merge interests from text + image vibe
    merged_interests = list(interests)
    if image_vibe:
        for bias in image_vibe.get("activity_bias", []):
            if bias not in merged_interests:
                merged_interests.append(bias)
        # If no destination was typed, use first suggestion from image
        if not destination and image_vibe.get("destination_suggestions"):
            state["destination"] = image_vibe["destination_suggestions"][0]

    state["traveler_profile"] = {
        "interests": merged_interests,
        "pace": "moderate",
        "group_size": group_size,
    }

    # Competitor data goes into alternative_plans
    if competitor_data:
        state["alternative_plans"] = {"competitor_offer": competitor_data}

    return state


# ---------------------------------------------------------------------------
# Core planning pipeline
# ---------------------------------------------------------------------------


async def plan_trip(
    destination: str,
    start_date: str,
    end_date: str,
    budget: float,
    currency: str,
    group_size: int,
    interests_text: str,
    audio_file: str | None,
    image_file: str | None,
    pdf_file: str | None,
    progress: Any = None,
    callbacks: Any = None,
) -> tuple[str, str, str | None]:
    """Main planning pipeline.

    Args:
        callbacks: Optional ``OrchestratorCallbacks`` instance for emitting
            real-time WebSocket events during graph execution.

    Returns:
        (plan_json, map_html, pdf_path)
    """
    global _last_result_state

    if callable(progress):
        progress(0.0, desc="Initializing...")

    # -- 1. Process multimodal inputs -----------------------------------------
    audio_state: dict[str, Any] | None = None
    image_vibe: dict[str, Any] | None = None
    competitor_data: dict[str, Any] | None = None

    if audio_file:
        if callable(progress):
            progress(0.1, desc="Processing audio input...")
        try:
            audio_state = await populate_state_from_audio(audio_file)
            logger.info("audio_processed", path=audio_file)
        except Exception as exc:
            logger.warning("audio_processing_failed", error=str(exc))

    if image_file:
        if callable(progress):
            progress(0.2, desc="Analyzing inspiration image...")
        try:
            image_vibe = await analyze_inspiration_image(image_file)
            logger.info("image_analyzed", path=image_file)
        except Exception as exc:
            logger.warning("image_analysis_failed", error=str(exc))

    if pdf_file:
        if callable(progress):
            progress(0.3, desc="Parsing competitor PDF...")
        try:
            competitor_data = await parse_competitor_offer_pdf(pdf_file)
            logger.info("pdf_parsed", path=pdf_file)
        except Exception as exc:
            logger.warning("pdf_parsing_failed", error=str(exc))

    # -- 2. Build initial state -----------------------------------------------
    if callable(progress):
        progress(0.4, desc="Building travel plan state...")
    interests = [i.strip() for i in interests_text.split(",") if i.strip()]

    state = _build_initial_state(
        destination=destination,
        start_date=start_date,
        end_date=end_date,
        budget_total=budget,
        currency=currency,
        group_size=group_size,
        interests=interests,
        audio_state=audio_state,
        image_vibe=image_vibe,
        competitor_data=competitor_data,
    )

    # -- 3. Run graph ---------------------------------------------------------
    if callable(progress):
        progress(0.5, desc="Running travel planner graph...")
    try:
        from travel_orchestrator.graph.planner_graph import compile_graph

        graph = compile_graph()
        thread_id = uuid.uuid4().hex
        config = {"configurable": {"thread_id": thread_id}}

        result_state = await _run_graph_with_callbacks(
            graph, state, config, callbacks, progress,
        )
        logger.info("graph_completed", plan_id=result_state.get("plan_id"))
    except Exception as exc:
        logger.warning("graph_execution_failed", error=str(exc))
        result_state = state
        result_state["risk_flags"] = [
            *result_state.get("risk_flags", []),
            f"graph_error: {exc}",
        ]

    # Cache for approval workflow
    _last_result_state = result_state

    # -- 4. Generate outputs --------------------------------------------------
    if callable(progress):
        progress(0.8, desc="Generating outputs...")

    plan_json = json.dumps(result_state, indent=2, default=str)

    # Generate map
    map_html = ""
    try:
        with tempfile.NamedTemporaryFile(
            suffix=".html", delete=False, prefix="travel_map_",
        ) as f:
            map_path = generate_map_from_state(result_state, f.name)
        if map_path and os.path.isfile(map_path):
            with open(map_path, encoding="utf-8") as mf:
                raw_html = mf.read()
            escaped = html_lib.escape(raw_html)
            map_html = (
                f'<iframe srcdoc="{escaped}" '
                f'width="100%" height="600" frameborder="0"></iframe>'
            )
    except Exception as exc:
        logger.warning("map_generation_failed", error=str(exc))
        map_html = f"<p>Map generation failed: {exc}</p>"

    # Generate PDF
    if callable(progress):
        progress(0.9, desc="Generating PDF...")
    pdf_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            suffix=".pdf", delete=False, prefix="travel_itinerary_",
        ) as f:
            result = generate_pdf_from_state(result_state, f.name)
            if result and os.path.isfile(result):
                pdf_path = result
    except Exception as exc:
        logger.warning("pdf_generation_failed", error=str(exc))

    if callable(progress):
        progress(1.0, desc="Done!")
    return plan_json, map_html, pdf_path


# ---------------------------------------------------------------------------
# Graph execution with streaming callbacks
# ---------------------------------------------------------------------------

# Keys that each node typically modifies — used for state_update events.
_NODE_CHANGED_KEYS: dict[str, list[str]] = {
    "gather_requirements": ["destination", "dates", "budget", "traveler_profile"],
    "analyze_destination": ["destination_analysis", "risk_flags"],
    "search_flights": [],
    "search_hotels": ["hotel_options", "selected_hotel_id", "current_cost"],
    "search_activities": ["activity_options", "selected_activity_ids", "current_cost"],
    "optimize_itinerary": ["optimized_itinerary"],
    "calculate_budget": ["current_cost"],
    "risk_and_policy_check": ["risk_flags"],
    "present_for_approval": ["approval_status"],
    "process_feedback": ["revision_count"],
    "book_services": [],
    "generate_documents": [],
}


async def _run_graph_with_callbacks(
    graph: Any,
    state: dict[str, Any],
    config: dict[str, Any],
    callbacks: Any,
    progress: Any = None,
) -> dict[str, Any]:
    """Execute the graph using ``astream`` and emit WS events per node.

    Falls back to ``ainvoke`` if ``astream`` is unavailable.
    """
    if callbacks is None:
        # No callbacks — use simple ainvoke
        return await graph.ainvoke(state, config=config)

    result_state = dict(state)
    node_count = 0
    total_nodes = 12  # approximate for progress bar

    try:
        async for chunk in graph.astream(state, config=config, stream_mode="updates"):
            for node_name, node_output in chunk.items():
                t0 = time.time()
                await callbacks.on_node_start(node_name)

                # Merge output into accumulated state
                if isinstance(node_output, dict):
                    result_state.update(node_output)

                duration_ms = (time.time() - t0) * 1000
                await callbacks.on_node_end(node_name, duration_ms=duration_ms)

                # Emit state snapshot
                changed = _NODE_CHANGED_KEYS.get(node_name, [])
                if changed:
                    await callbacks.on_state_update(
                        node_name, result_state, changed,
                    )

                node_count += 1
                if callable(progress):
                    frac = 0.5 + 0.3 * (node_count / total_nodes)
                    progress(min(frac, 0.8), desc=f"Running {node_name}...")
    except Exception as exc:
        # GraphInterrupt or other errors — use state accumulated so far
        exc_name = type(exc).__name__
        if exc_name != "GraphInterrupt":
            logger.warning("graph_stream_error", error=str(exc))
            result_state["risk_flags"] = [
                *result_state.get("risk_flags", []),
                f"graph_error: {exc}",
            ]

    return result_state


# ---------------------------------------------------------------------------
# Approval handler
# ---------------------------------------------------------------------------


async def handle_approval(decision: str, feedback: str) -> str:
    """Handle plan approval or rejection.

    Updates the cached state's approval_status and returns
    a confirmation message.
    """
    global _last_result_state

    if not _last_result_state:
        return "No plan to review. Please generate a plan first."

    _last_result_state["approval_status"] = decision

    if decision == "rejected" and feedback:
        flags = list(_last_result_state.get("risk_flags", []))
        flags = [f for f in flags if not f.startswith("feedback:")]
        flags.append(f"feedback: {feedback}")
        _last_result_state["risk_flags"] = flags

    logger.info(
        "plan_decision",
        decision=decision,
        plan_id=_last_result_state.get("plan_id"),
        feedback=feedback if decision == "rejected" else "",
    )

    msg = f"Plan {decision}."
    if decision == "rejected" and feedback:
        msg += f" Feedback: {feedback}"
    return msg
