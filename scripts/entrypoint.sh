#!/bin/bash
set -e

echo "Starting metrics server on :8000 ..."
uvicorn travel_orchestrator.observability.server:app \
    --host 0.0.0.0 --port 8000 --log-level warning &

echo "Starting Gradio frontend on :7860 ..."
exec python -m travel_orchestrator.frontend.app
