"""Allow running the frontend with: python -m travel_orchestrator.frontend"""

import uvicorn

uvicorn.run(
    "travel_orchestrator.frontend.server:app",
    host="0.0.0.0",
    port=7860,
    log_level="info",
)
