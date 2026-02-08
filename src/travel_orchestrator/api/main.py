"""FastAPI application for the Travel Orchestrator API.

Serves REST endpoints, WebSocket channels, health/metrics, and
optionally static files for the SPA.  Designed to run on port 8000
with the frontend served separately on port 3000 (dev) or 5173 (vite).

Run with::

    uvicorn travel_orchestrator.api.main:app --port 8000
"""

from __future__ import annotations

import asyncio
import html as html_lib
import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Form, HTTPException, Request, UploadFile, File, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from travel_orchestrator.api.callbacks import OrchestratorCallbacks
from travel_orchestrator.api.schemas import (
    ApprovalRequest,
    ChatMessage,
    ItineraryUpdate,
    PlanRequest,
    TripPlan,
)
from travel_orchestrator.api.ws_manager import manager
from travel_orchestrator.frontend.app import handle_approval, plan_trip
from travel_orchestrator.observability.metrics import get_metrics
from travel_orchestrator.utils.logging import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
_STATIC_DIR = _FRONTEND_DIR / "static"
_DASHBOARD_PATH = _FRONTEND_DIR / "dashboard.html"
_ARTIFACTS_DIR = Path(tempfile.mkdtemp(prefix="travel_artifacts_"))

# ---------------------------------------------------------------------------
# In-memory trip store
# ---------------------------------------------------------------------------

_trips: dict[str, dict[str, Any]] = {}

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(title="Travel Orchestrator API", docs_url="/docs", redoc_url=None)

# CORS — allow frontend dev server and production
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Global exception handler
# ---------------------------------------------------------------------------


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all handler so unhandled errors return structured JSON."""
    logger.error("unhandled_error", path=str(request.url.path), error=str(exc))
    return JSONResponse(
        status_code=500,
        content={
            "detail": "An internal error occurred. Please try again later.",
            "error_type": type(exc).__name__,
        },
    )


# ---------------------------------------------------------------------------
# Health & metrics
# ---------------------------------------------------------------------------


@app.get("/health")
async def health() -> dict[str, str]:
    """Liveness / readiness probe."""
    return {"status": "healthy"}


@app.get("/metrics")
async def metrics() -> Response:
    """Prometheus exposition endpoint."""
    return Response(
        content=get_metrics(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard() -> str:
    """Serve the monitoring dashboard."""
    if _DASHBOARD_PATH.is_file():
        return _DASHBOARD_PATH.read_text(encoding="utf-8")
    return "<p>Dashboard not found</p>"


# ---------------------------------------------------------------------------
# REST — Plan
# ---------------------------------------------------------------------------


@app.post("/api/plan")
async def api_plan_json(req: PlanRequest) -> dict[str, Any]:
    """Run the planning pipeline from a JSON request body."""
    return await _run_plan(
        destination=req.destination,
        start_date=req.start_date,
        end_date=req.end_date,
        budget=req.budget,
        currency=req.currency,
        group_size=req.num_travelers,
        interests_text=",".join(req.preferences),
    )


@app.post("/api/plan/form")
async def api_plan_form(
    destination: str = Form(""),
    start_date: str = Form(""),
    end_date: str = Form(""),
    budget: float = Form(5000.0),
    currency: str = Form("USD"),
    group_size: int = Form(2),
    interests: str = Form(""),
    audio_file: UploadFile | None = File(None),
    image_file: UploadFile | None = File(None),
    pdf_file: UploadFile | None = File(None),
) -> dict[str, Any]:
    """Run the planning pipeline from a multipart form (backward compat)."""
    audio_path = await _save_upload(audio_file) if audio_file and audio_file.filename else None
    image_path = await _save_upload(image_file) if image_file and image_file.filename else None
    pdf_path = await _save_upload(pdf_file) if pdf_file and pdf_file.filename else None

    return await _run_plan(
        destination=destination,
        start_date=start_date,
        end_date=end_date,
        budget=budget,
        currency=currency,
        group_size=group_size,
        interests_text=interests,
        audio_path=audio_path,
        image_path=image_path,
        pdf_path=pdf_path,
    )


async def _run_plan(
    *,
    destination: str,
    start_date: str,
    end_date: str,
    budget: float,
    currency: str,
    group_size: int,
    interests_text: str,
    audio_path: str | None = None,
    image_path: str | None = None,
    pdf_path: str | None = None,
) -> dict[str, Any]:
    """Shared planning logic for both JSON and Form endpoints."""
    callbacks = OrchestratorCallbacks(manager)

    plan_json, map_html, generated_pdf_path = await plan_trip(
        destination=destination,
        start_date=start_date,
        end_date=end_date,
        budget=budget,
        currency=currency,
        group_size=group_size,
        interests_text=interests_text,
        audio_file=audio_path,
        image_file=image_path,
        pdf_file=pdf_path,
        callbacks=callbacks,
    )

    plan_data = json.loads(plan_json)
    plan_id = plan_data.get("plan_id", "unknown")

    # Persist map artifact
    map_url = ""
    if map_html:
        map_filename = f"map_{plan_id}.html"
        if 'srcdoc="' in map_html:
            start = map_html.index('srcdoc="') + len('srcdoc="')
            end = map_html.index('" width=')
            raw_escaped = map_html[start:end]
            raw = html_lib.unescape(raw_escaped)
            (_ARTIFACTS_DIR / map_filename).write_text(raw, encoding="utf-8")
            map_url = f"/api/map/{map_filename}"

    # Persist PDF artifact
    pdf_url = ""
    if generated_pdf_path and os.path.isfile(generated_pdf_path):
        import shutil

        pdf_filename = f"itinerary_{plan_id}.pdf"
        shutil.copy2(generated_pdf_path, _ARTIFACTS_DIR / pdf_filename)
        pdf_url = f"/api/pdf/{pdf_filename}"

    # Convert raw state → TripPlan-shaped response
    trip = _state_to_trip_plan(plan_data, map_url=map_url, pdf_url=pdf_url)

    # Store for later retrieval
    _trips[plan_id] = trip

    # Notify orchestrator WS about completion
    await callbacks.on_hitl_required(plan_id)

    return {"plan": plan_data, "map_url": map_url, "pdf_url": pdf_url}


# ---------------------------------------------------------------------------
# REST — Trip CRUD
# ---------------------------------------------------------------------------


@app.get("/api/trip/{trip_id}")
async def get_trip(trip_id: str) -> dict[str, Any]:
    """Retrieve a previously created trip plan."""
    trip = _trips.get(trip_id)
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    return trip


@app.patch("/api/trip/{trip_id}/itinerary")
async def update_itinerary(trip_id: str, body: ItineraryUpdate) -> dict[str, Any]:
    """Update the itinerary (e.g. from drag-and-drop reordering)."""
    trip = _trips.get(trip_id)
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")

    trip["days"] = [d.model_dump() for d in body.days]
    return trip


@app.post("/api/trip/{trip_id}/approve")
async def approve_trip(trip_id: str, body: ApprovalRequest) -> dict[str, str]:
    """Approve or reject a trip plan."""
    trip = _trips.get(trip_id)
    if trip:
        trip["approval_status"] = body.decision

    msg = await handle_approval(body.decision, body.feedback)
    return {"message": msg}


# Legacy form-based approval (backward compat)
@app.post("/api/approve")
async def api_approve_legacy(
    decision: str = Form("approved"),
    feedback: str = Form(""),
) -> dict[str, str]:
    """Handle plan approval via form data (backward compat)."""
    msg = await handle_approval(decision, feedback)
    return {"message": msg}


# ---------------------------------------------------------------------------
# Artifact serving
# ---------------------------------------------------------------------------


@app.get("/api/map/{filename}")
async def serve_map(filename: str) -> HTMLResponse:
    """Serve a generated map HTML file."""
    filepath = _ARTIFACTS_DIR / filename
    if not filepath.is_file():
        return HTMLResponse(content="<p>Map not found</p>", status_code=404)
    return HTMLResponse(content=filepath.read_text(encoding="utf-8"))


@app.get("/api/pdf/{filename}")
async def serve_pdf(filename: str) -> FileResponse:
    """Serve a generated PDF file for download."""
    filepath = _ARTIFACTS_DIR / filename
    if not filepath.is_file():
        raise HTTPException(status_code=404, detail="PDF not found")
    return FileResponse(path=str(filepath), media_type="application/pdf", filename=filename)


# ---------------------------------------------------------------------------
# WebSocket — Orchestrator
# ---------------------------------------------------------------------------


@app.websocket("/ws/orchestrator")
async def ws_orchestrator(websocket: WebSocket) -> None:
    """Real-time orchestrator pipeline events."""
    await manager.connect("orchestrator", websocket)
    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
            except json.JSONDecodeError:
                continue

            action = msg.get("action")
            if action == "start_demo":
                from travel_orchestrator.api.ws_orchestrator import _run_demo_simulation

                asyncio.create_task(_run_demo_simulation())
    except WebSocketDisconnect:
        await manager.disconnect("orchestrator", websocket)


# ---------------------------------------------------------------------------
# WebSocket — Chat
# ---------------------------------------------------------------------------

_MOCK_RESPONSES: dict[str, str] = {
    "greeting": (
        "Hello! I'm your AI travel planning assistant. I can help you plan trips, "
        "find hotels, discover activities, and optimize your itinerary. "
        "What would you like to do?"
    ),
    "hotels": (
        "I found several excellent hotel options for you. "
        "Each has been scored against your budget and preferences. "
        "Check the results panel to see the full list."
    ),
    "activities": (
        "Here are some amazing activities I discovered for your trip! "
        "I've curated these based on your interests and the local weather forecast."
    ),
    "weather": (
        "Here's the weather forecast for your travel dates. "
        "I've analyzed the conditions to help you plan outdoor vs indoor activities accordingly."
    ),
    "budget": (
        "Looking at your budget, the current plan looks good. "
        "I've optimized spending across hotels and activities to stay within your limits."
    ),
    "default": (
        "I'd be happy to help! Based on your preferences, I've put together some great options. "
        "Take a look at the results and let me know if you'd like any changes."
    ),
}


def _pick_chat_response(user_content: str) -> str:
    """Pick a contextual mock response based on keywords in the user message."""
    lower = user_content.lower()
    if any(w in lower for w in ("hi", "hello", "hey", "oi", "olá")):
        return _MOCK_RESPONSES["greeting"]
    if any(w in lower for w in ("hotel", "hospedagem", "accommodation", "stay")):
        return _MOCK_RESPONSES["hotels"]
    if any(w in lower for w in ("activit", "atividad", "things to do", "attraction")):
        return _MOCK_RESPONSES["activities"]
    if any(w in lower for w in ("weather", "clima", "forecast", "tempo")):
        return _MOCK_RESPONSES["weather"]
    if any(w in lower for w in ("budget", "orçamento", "custo", "cost", "price")):
        return _MOCK_RESPONSES["budget"]

    # If there's trip data, enrich the response
    if _trips:
        latest = list(_trips.values())[-1]
        dest = latest.get("destination", "")
        if dest:
            return (
                f"Based on your {dest} trip plan, I can help you refine the itinerary. "
                "Check the results panel for full details, or ask me about specific aspects "
                "like hotels, activities, or weather."
            )

    return _MOCK_RESPONSES["default"]


@app.websocket("/ws/chat")
async def ws_chat(websocket: WebSocket) -> None:
    """Chat streaming WebSocket. Receives user messages and streams responses."""
    await manager.connect("chat", websocket)

    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
            except json.JSONDecodeError:
                continue

            user_content = msg.get("content", "")
            if not user_content:
                continue

            # Send status
            await manager.send_personal(websocket, {
                "type": "status",
                "message": "Understanding your request...",
            })

            await asyncio.sleep(0.3)

            # Pick a contextual response
            response_text = _pick_chat_response(user_content)

            # Stream token by token
            for char in response_text:
                await manager.send_personal(websocket, {
                    "type": "token",
                    "content": char,
                })
                await asyncio.sleep(0.02)

            # Send done
            ts = int(time.time() * 1000)
            await manager.send_personal(websocket, {
                "type": "done",
                "message": ChatMessage(
                    role="assistant",
                    content=response_text,
                    timestamp=ts,
                ).model_dump(),
            })

    except WebSocketDisconnect:
        await manager.disconnect("chat", websocket)


# ---------------------------------------------------------------------------
# SPA fallback (optional — mount static dir if it exists)
# ---------------------------------------------------------------------------

if _STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

    @app.get("/", response_class=HTMLResponse)
    async def index() -> str:
        """Serve the single-page application."""
        index_file = _STATIC_DIR / "index.html"
        if index_file.is_file():
            return index_file.read_text(encoding="utf-8")
        return "<p>Frontend not built</p>"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _state_to_trip_plan(
    state: dict[str, Any],
    *,
    map_url: str = "",
    pdf_url: str = "",
) -> dict[str, Any]:
    """Convert a raw LangGraph state dict into a TripPlan-shaped dict."""
    plan_id = state.get("plan_id", "")
    dates = state.get("dates", {})
    budget = state.get("budget", {})

    # Hotels
    hotels = []
    for h in state.get("hotel_options", []):
        coords = h.get("coordinates")
        hotels.append({
            "id": h.get("id", ""),
            "name": h.get("name", ""),
            "address": h.get("address", ""),
            "stars": h.get("stars", 0),
            "price_per_night": h.get("price_per_night", h.get("nightly_price_avg", 0)),
            "currency": h.get("currency", budget.get("currency", "USD")),
            "reviews_score": h.get("reviews_score", 0),
            "score": h.get("score", 0),
            "amenities": h.get("amenities", []),
            "coordinates": {"lat": coords["lat"], "lng": coords["lng"]} if coords else None,
        })

    # Activities
    activities = []
    for a in state.get("activity_options", []):
        coords = a.get("coordinates")
        activities.append({
            "place_id": a.get("id", ""),
            "name": a.get("name", ""),
            "type": a.get("category", ""),
            "duration": a.get("duration_minutes", 60),
            "cost": a.get("price", 0),
            "currency": a.get("currency", budget.get("currency", "USD")),
            "rating": a.get("score", 0),
            "coordinates": {"lat": coords["lat"], "lng": coords["lng"]} if coords else None,
        })

    # Days
    days = []
    itinerary = state.get("optimized_itinerary")
    if itinerary and isinstance(itinerary, dict):
        for day_data in itinerary.get("days", []):
            days.append({
                "date": day_data.get("date", ""),
                "day_number": day_data.get("day_number", day_data.get("day", 0)),
                "theme": day_data.get("theme", ""),
                "activities": [],
                "hotel": None,
                "weather": None,
                "transport_segments": [],
            })

    # Weather summary
    weather_summary = None
    analysis = state.get("destination_analysis")
    if analysis and isinstance(analysis, dict):
        ws = analysis.get("weather_summary")
        if ws:
            weather_summary = {
                "avg_temp_max": ws.get("avg_temp_max", 0),
                "avg_temp_min": ws.get("avg_temp_min", 0),
                "dominant_condition": ws.get("dominant_condition", "unknown"),
                "packing_suggestions": ws.get("packing_suggestions", []),
            }

    return {
        "plan_id": plan_id,
        "destination": state.get("destination", ""),
        "start_date": dates.get("start_date", ""),
        "end_date": dates.get("end_date", ""),
        "days": days,
        "hotels": hotels,
        "activities": activities,
        "total_cost": state.get("current_cost", 0.0),
        "currency": budget.get("currency", "USD"),
        "weather_summary": weather_summary,
        "approval_status": state.get("approval_status", "pending"),
        "map_url": map_url,
        "pdf_url": pdf_url,
    }


async def _save_upload(upload: UploadFile) -> str:
    """Save an uploaded file to a temp path and return the path."""
    suffix = Path(upload.filename or "file").suffix
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as f:
        content = await upload.read()
        f.write(content)
        return f.name
