#!/bin/bash
set -e

echo "Starting Travel Orchestrator on :7860 ..."
exec uvicorn travel_orchestrator.frontend.server:app \
    --host 0.0.0.0 --port 7860 --log-level warning
