"""Client helper for searching hotels via the hotel MCP server.

In the current architecture the hotel server and the graph run in the
same process, so the client calls the server implementation function
directly -- no MCP transport overhead.

When the system moves to a separate hotel-server process, swap this
implementation for one that connects via ``streamablehttp_client``.
"""

from __future__ import annotations

from typing import Any

from travel_orchestrator.mcp_servers.hotels.server import (
    compare_hotels_impl,
    get_hotel_details_impl,
    get_hotel_facilities_impl,
    search_by_coordinates_impl,
    search_hotels_impl,
)
from travel_orchestrator.utils.logging import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Legacy client function (backward-compatible)
# ---------------------------------------------------------------------------


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

    Dispatches to the Booking.com, Enuygun, or mock provider
    depending on configuration and availability.
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


# ---------------------------------------------------------------------------
# New client functions
# ---------------------------------------------------------------------------


async def get_hotel_details(hotel_id: str) -> dict[str, Any]:
    """Get full details for a hotel by ID."""
    logger.info("fetching_hotel_details", hotel_id=hotel_id)
    return await get_hotel_details_impl(hotel_id)


async def search_by_coordinates(
    latitude: float,
    longitude: float,
    radius_km: float,
    check_in: str,
    check_out: str,
    adults: int = 1,
) -> list[dict[str, Any]]:
    """Search hotels near a geographic point."""
    logger.info(
        "searching_hotels_by_coordinates",
        latitude=latitude,
        longitude=longitude,
        radius_km=radius_km,
    )
    return await search_by_coordinates_impl(
        latitude=latitude,
        longitude=longitude,
        radius_km=radius_km,
        check_in=check_in,
        check_out=check_out,
        adults=adults,
    )


async def get_hotel_facilities(hotel_id: str) -> list[dict[str, Any]]:
    """Get the facility list for a hotel."""
    logger.info("fetching_hotel_facilities", hotel_id=hotel_id)
    return await get_hotel_facilities_impl(hotel_id)


async def compare_hotels(hotel_ids: list[str]) -> list[dict[str, Any]]:
    """Compare multiple hotels side by side."""
    logger.info("comparing_hotels", count=len(hotel_ids))
    return await compare_hotels_impl(hotel_ids)
