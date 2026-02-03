"""Client helper for searching hotels via the hotel MCP server.

In the current architecture the hotel server and the graph run in the
same process, so the client calls the server implementation function
directly -- no MCP transport overhead.

When the system moves to a separate hotel-server process, swap this
implementation for one that connects via ``streamablehttp_client``.
"""

from __future__ import annotations

from typing import Any

from travel_orchestrator.mcp_servers.hotels.server import search_hotels_impl
from travel_orchestrator.utils.logging import get_logger

logger = get_logger(__name__)


async def search_hotels(
    destination: str,
    check_in: str,
    check_out: str,
    guests: int = 1,
    *,
    location_centrality: float = 0.5,
    min_stars: int | None = None,
    amenities: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Search hotels for *destination* over the date range.

    Dispatches to the Enuygun upstream or mock provider depending on
    availability.
    """
    logger.info(
        "searching_hotels",
        destination=destination,
        check_in=check_in,
        check_out=check_out,
        guests=guests,
        min_stars=min_stars,
    )
    return await search_hotels_impl(
        destination=destination,
        check_in=check_in,
        check_out=check_out,
        guests=guests,
        location_centrality=location_centrality,
        min_stars=min_stars,
        amenities=amenities,
    )
