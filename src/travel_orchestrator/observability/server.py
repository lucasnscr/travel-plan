"""FastAPI application that exposes Prometheus ``/metrics`` and ``/health``.

Run standalone::

    uvicorn travel_orchestrator.observability.server:app --port 9090

This server runs on a **separate port** from the Gradio frontend (7860)
so that scraping tools like Prometheus can poll it independently.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, Response

from travel_orchestrator.observability.metrics import get_metrics

_DASHBOARD_PATH = Path(__file__).resolve().parent.parent / "frontend" / "dashboard.html"

app = FastAPI(title="Travel Orchestrator Observability", docs_url=None, redoc_url=None)


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
