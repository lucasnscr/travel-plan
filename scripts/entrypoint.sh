#!/bin/bash
set -e

echo "Starting Travel Orchestrator API on :8000 ..."
exec uvicorn travel_orchestrator.api.main:app \
    --host 0.0.0.0 --port 8000 --log-level warning
