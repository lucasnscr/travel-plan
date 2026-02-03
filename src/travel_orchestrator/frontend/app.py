"""Gradio web frontend for the travel orchestrator.

Run with::

    python -m travel_orchestrator.frontend.app
    # or
    python -m travel_orchestrator.frontend
"""

from __future__ import annotations

import html as html_lib
import json
import os
import tempfile
import uuid
from typing import Any

import gradio as gr

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
    progress: gr.Progress = gr.Progress(),
) -> tuple[str, str, str | None]:
    """Main planning pipeline.

    Returns:
        (plan_json, map_html, pdf_path)
    """
    global _last_result_state

    progress(0.0, desc="Initializing...")

    # -- 1. Process multimodal inputs -----------------------------------------
    audio_state: dict[str, Any] | None = None
    image_vibe: dict[str, Any] | None = None
    competitor_data: dict[str, Any] | None = None

    if audio_file:
        progress(0.1, desc="Processing audio input...")
        try:
            audio_state = await populate_state_from_audio(audio_file)
            logger.info("audio_processed", path=audio_file)
        except Exception as exc:
            logger.warning("audio_processing_failed", error=str(exc))

    if image_file:
        progress(0.2, desc="Analyzing inspiration image...")
        try:
            image_vibe = await analyze_inspiration_image(image_file)
            logger.info("image_analyzed", path=image_file)
        except Exception as exc:
            logger.warning("image_analysis_failed", error=str(exc))

    if pdf_file:
        progress(0.3, desc="Parsing competitor PDF...")
        try:
            competitor_data = await parse_competitor_offer_pdf(pdf_file)
            logger.info("pdf_parsed", path=pdf_file)
        except Exception as exc:
            logger.warning("pdf_parsing_failed", error=str(exc))

    # -- 2. Build initial state -----------------------------------------------
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
    progress(0.5, desc="Running travel planner graph...")
    try:
        from travel_orchestrator.graph.planner_graph import compile_graph

        graph = compile_graph()
        thread_id = uuid.uuid4().hex
        config = {"configurable": {"thread_id": thread_id}}
        result_state = await graph.ainvoke(state, config=config)
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

    progress(1.0, desc="Done!")
    return plan_json, map_html, pdf_path


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


# ---------------------------------------------------------------------------
# Gradio UI
# ---------------------------------------------------------------------------


def build_app() -> gr.Blocks:
    """Construct and return the Gradio Blocks application."""

    with gr.Blocks(
        title="Travel Orchestrator",
    ) as app:
        gr.Markdown("# Travel Orchestrator")
        gr.Markdown("AI-powered travel planning system")

        # -- Input section ------------------------------------------------
        with gr.Row():
            with gr.Column(scale=2):
                gr.Markdown("### Trip Details")
                destination = gr.Textbox(
                    label="Destination",
                    placeholder="e.g. Paris, France",
                )
                with gr.Row():
                    start_date = gr.Textbox(
                        label="Start Date (YYYY-MM-DD)",
                        placeholder="2026-07-01",
                    )
                    end_date = gr.Textbox(
                        label="End Date (YYYY-MM-DD)",
                        placeholder="2026-07-08",
                    )
                with gr.Row():
                    budget = gr.Number(label="Budget", value=5000.0)
                    currency = gr.Dropdown(
                        label="Currency",
                        choices=["USD", "EUR", "BRL", "GBP"],
                        value="USD",
                    )
                group_size = gr.Slider(
                    label="Group Size",
                    minimum=1,
                    maximum=20,
                    step=1,
                    value=2,
                )
                interests = gr.Textbox(
                    label="Interests (comma-separated)",
                    placeholder="museums, gastronomy, outdoors",
                )

            with gr.Column(scale=1):
                gr.Markdown("### Optional Uploads")
                audio_input = gr.Audio(
                    label="Voice Description",
                    type="filepath",
                )
                image_input = gr.Image(
                    label="Inspiration Image",
                    type="filepath",
                )
                pdf_input = gr.File(
                    label="Competitor PDF",
                    file_types=[".pdf"],
                )

        plan_btn = gr.Button(
            "Plan My Trip",
            variant="primary",
            size="lg",
        )

        # -- Output section -----------------------------------------------
        with gr.Tabs():
            with gr.TabItem("Plan"):
                plan_output = gr.JSON(label="Travel Plan")
            with gr.TabItem("Map"):
                map_output = gr.HTML(label="Interactive Map")
            with gr.TabItem("PDF"):
                pdf_output = gr.File(label="Download Itinerary PDF")

        # -- Approval section ---------------------------------------------
        gr.Markdown("---")
        gr.Markdown("### Plan Review")
        with gr.Row():
            feedback_text = gr.Textbox(
                label="Feedback (for rejection)",
                placeholder="e.g. Hotel too far from center",
                scale=3,
            )
            approve_btn = gr.Button("Approve", variant="primary", scale=1)
            reject_btn = gr.Button("Reject", variant="stop", scale=1)
        approval_output = gr.Textbox(
            label="Decision Result",
            interactive=False,
        )

        # -- Wiring -------------------------------------------------------
        async def on_plan_click(
            dest: str,
            s_date: str,
            e_date: str,
            bdgt: float,
            curr: str,
            grp: int,
            ints: str,
            audio: str | None,
            image: str | None,
            pdf: Any,
            progress: gr.Progress = gr.Progress(),
        ) -> tuple[Any, str, str | None]:
            # Gradio File component returns a filepath string or UploadedFile
            pdf_path = None
            if pdf is not None:
                if isinstance(pdf, str):
                    pdf_path = pdf
                elif hasattr(pdf, "name"):
                    pdf_path = pdf.name

            plan_json, map_html, pdf_out = await plan_trip(
                dest, s_date, e_date, bdgt, curr, int(grp), ints,
                audio, image, pdf_path, progress,
            )

            return json.loads(plan_json), map_html, pdf_out

        plan_btn.click(
            fn=on_plan_click,
            inputs=[
                destination, start_date, end_date, budget, currency,
                group_size, interests, audio_input, image_input, pdf_input,
            ],
            outputs=[plan_output, map_output, pdf_output],
        )

        async def on_approve(feedback: str) -> str:
            return await handle_approval("approved", feedback)

        async def on_reject(feedback: str) -> str:
            return await handle_approval("rejected", feedback)

        approve_btn.click(
            fn=on_approve,
            inputs=[feedback_text],
            outputs=[approval_output],
        )
        reject_btn.click(
            fn=on_reject,
            inputs=[feedback_text],
            outputs=[approval_output],
        )

    return app


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Launch the Gradio application."""
    app = build_app()
    app.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        theme=gr.themes.Soft(),
    )


if __name__ == "__main__":
    main()
