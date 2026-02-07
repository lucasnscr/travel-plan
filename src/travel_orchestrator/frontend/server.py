"""FastAPI server for the Travel Orchestrator SPA.

Serves the single-page application, REST API endpoints, and
observability routes (health, metrics, dashboard) on a single port.

Run with::

    uvicorn travel_orchestrator.frontend.server:app --port 7860
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles

from travel_orchestrator.api.ws_orchestrator import orchestrator_ws
from travel_orchestrator.frontend.app import handle_approval, plan_trip
from travel_orchestrator.observability.metrics import get_metrics
from travel_orchestrator.utils.logging import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_THIS_DIR = Path(__file__).resolve().parent
_STATIC_DIR = _THIS_DIR / "static"
_DASHBOARD_PATH = _THIS_DIR / "dashboard.html"

# Temp directory for generated artifacts (maps, PDFs)
_ARTIFACTS_DIR = Path(tempfile.mkdtemp(prefix="travel_artifacts_"))

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(title="Travel Orchestrator", docs_url=None, redoc_url=None)

# WebSocket endpoint for orchestrator observability
app.add_api_websocket_route("/ws/orchestrator", orchestrator_ws)

# Mount static files
app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")


# ---------------------------------------------------------------------------
# SPA
# ---------------------------------------------------------------------------


@app.get("/", response_class=HTMLResponse)
async def index() -> str:
    """Serve the single-page application."""
    return (_STATIC_DIR / "index.html").read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------------


@app.post("/api/plan")
async def api_plan(
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
    """Run the planning pipeline and return results."""
    # Save uploaded files to temp paths
    audio_path = await _save_upload(audio_file) if audio_file and audio_file.filename else None
    image_path = await _save_upload(image_file) if image_file and image_file.filename else None
    pdf_path = await _save_upload(pdf_file) if pdf_file and pdf_file.filename else None

    plan_json, map_html, generated_pdf_path = await plan_trip(
        destination=destination,
        start_date=start_date,
        end_date=end_date,
        budget=budget,
        currency=currency,
        group_size=group_size,
        interests_text=interests,
        audio_file=audio_path,
        image_file=image_path,
        pdf_file=pdf_path,
    )

    # Copy map to artifacts dir
    map_url = ""
    if map_html:
        import json as _json

        plan_data = _json.loads(plan_json)
        plan_id = plan_data.get("plan_id", "unknown")
        map_filename = f"map_{plan_id}.html"
        # Extract raw HTML from the iframe srcdoc
        import html as html_lib

        if 'srcdoc="' in map_html:
            start = map_html.index('srcdoc="') + len('srcdoc="')
            end = map_html.index('" width=')
            raw_escaped = map_html[start:end]
            raw_html = html_lib.unescape(raw_escaped)
            (_ARTIFACTS_DIR / map_filename).write_text(raw_html, encoding="utf-8")
            map_url = f"/api/map/{map_filename}"

    # Copy PDF to artifacts dir
    pdf_url = ""
    if generated_pdf_path and os.path.isfile(generated_pdf_path):
        import json as _json
        import shutil

        plan_data = _json.loads(plan_json)
        plan_id = plan_data.get("plan_id", "unknown")
        pdf_filename = f"itinerary_{plan_id}.pdf"
        shutil.copy2(generated_pdf_path, _ARTIFACTS_DIR / pdf_filename)
        pdf_url = f"/api/pdf/{pdf_filename}"

    import json as _json

    return {
        "plan": _json.loads(plan_json),
        "map_url": map_url,
        "pdf_url": pdf_url,
    }


@app.post("/api/approve")
async def api_approve(
    decision: str = Form("approved"),
    feedback: str = Form(""),
) -> dict[str, str]:
    """Handle plan approval or rejection."""
    msg = await handle_approval(decision, feedback)
    return {"message": msg}


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
        return FileResponse(path="/dev/null", status_code=404)
    return FileResponse(
        path=str(filepath),
        media_type="application/pdf",
        filename=filename,
    )


# ---------------------------------------------------------------------------
# Observability endpoints (merged from observability/server.py)
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
    """Serve the static monitoring dashboard."""
    return _DASHBOARD_PATH.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _save_upload(upload: UploadFile) -> str:
    """Save an uploaded file to a temp path and return the path."""
    suffix = Path(upload.filename or "file").suffix
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as f:
        content = await upload.read()
        f.write(content)
        return f.name
