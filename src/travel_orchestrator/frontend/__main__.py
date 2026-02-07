"""Allow running the frontend with: python -m travel_orchestrator.frontend"""

import uvicorn

uvicorn.run(
    "travel_orchestrator.api.main:app",
    host="0.0.0.0",
    port=8000,
    log_level="info",
)
