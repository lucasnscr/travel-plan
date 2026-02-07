"""FastAPI server for the Travel Orchestrator SPA (backward compat).

This module re-exports the FastAPI ``app`` from the new
:mod:`travel_orchestrator.api.main` module.  Existing imports like
``from travel_orchestrator.frontend.server import app`` continue
to work.

For new code, import from ``travel_orchestrator.api.main`` instead.

Run with::

    uvicorn travel_orchestrator.api.main:app --port 8000
"""

from travel_orchestrator.api.main import app  # noqa: F401

__all__ = ["app"]
