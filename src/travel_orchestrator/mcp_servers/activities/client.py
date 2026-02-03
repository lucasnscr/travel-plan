"""Client helper for discovering activities via the activities MCP server.

In the current architecture the activities server and the graph run in
the same process, so the client calls the server implementation function
directly -- no MCP transport overhead.

When the system moves to a separate activities-server process, swap this
implementation for one that connects via ``streamablehttp_client``.
"""

from __future__ import annotations

from typing import Any

from travel_orchestrator.mcp_servers.activities.server import (
    discover_activities_impl,
)
from travel_orchestrator.utils.logging import get_logger

logger = get_logger(__name__)


async def discover_activities(
    destination: str,
    interests: list[str],
    start_date: str,
    end_date: str,
    budget_per_day: float,
) -> list[dict[str, Any]]:
    """Discover scored activities at *destination* over the date range.

    Returns up to 50 activities sorted by score descending, filtered by
    interests, budget, and category diversity.
    """
    logger.info(
        "discovering_activities",
        destination=destination,
        interests=interests,
        start_date=start_date,
        end_date=end_date,
        budget_per_day=budget_per_day,
    )
    return await discover_activities_impl(
        destination=destination,
        interests=interests,
        date_range={"start": start_date, "end": end_date},
        budget_per_day=budget_per_day,
    )
