"""Client helper for the activities/places MCP server.

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
    geocode_impl,
    get_directions_impl,
    get_place_details_impl,
    get_place_photos_impl,
    nearby_search_impl,
    reverse_geocode_impl,
    search_activities_impl,
    search_restaurants_impl,
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


async def search_activities(
    query: str,
    location: str,
    *,
    language: str = "pt-BR",
    max_results: int = 20,
) -> list[dict[str, Any]]:
    """Search for activities/attractions by text query at a location."""
    logger.info("search_activities", query=query, location=location)
    return await search_activities_impl(
        query=query,
        location=location,
        language=language,
        max_results=max_results,
    )


async def search_restaurants(
    location: str,
    *,
    cuisine: str | None = None,
    price_level: int | None = None,
    language: str = "pt-BR",
    max_results: int = 20,
) -> list[dict[str, Any]]:
    """Search for restaurants at a location."""
    logger.info("search_restaurants", location=location, cuisine=cuisine)
    return await search_restaurants_impl(
        location=location,
        cuisine=cuisine,
        price_level=price_level,
        language=language,
        max_results=max_results,
    )


async def get_place_details(
    place_id: str,
    *,
    language: str = "pt-BR",
) -> dict[str, Any]:
    """Get full details for a place by ID."""
    logger.info("get_place_details", place_id=place_id)
    return await get_place_details_impl(
        place_id=place_id,
        language=language,
    )


async def get_place_photos(
    place_id: str,
    *,
    max_photos: int = 5,
) -> list[dict[str, Any]]:
    """Get photo URLs for a place."""
    logger.info("get_place_photos", place_id=place_id)
    return await get_place_photos_impl(
        place_id=place_id,
        max_photos=max_photos,
    )


async def nearby_search(
    latitude: float,
    longitude: float,
    radius_meters: int = 1000,
    *,
    place_type: str = "tourist_attraction",
    language: str = "pt-BR",
    max_results: int = 20,
) -> list[dict[str, Any]]:
    """Search for places near specific coordinates."""
    logger.info("nearby_search", lat=latitude, lng=longitude, radius=radius_meters)
    return await nearby_search_impl(
        latitude=latitude,
        longitude=longitude,
        radius_meters=radius_meters,
        place_type=place_type,
        language=language,
        max_results=max_results,
    )


async def get_directions(
    origin: str,
    destination: str,
    *,
    mode: str = "walking",
    language: str = "pt-BR",
) -> dict[str, Any]:
    """Get directions between two locations."""
    logger.info("get_directions", origin=origin, destination=destination, mode=mode)
    return await get_directions_impl(
        origin=origin,
        destination=destination,
        mode=mode,
        language=language,
    )


async def geocode(
    address: str,
    *,
    language: str = "pt-BR",
) -> list[dict[str, Any]]:
    """Forward geocode: address to coordinates."""
    logger.info("geocode", address=address)
    return await geocode_impl(address=address, language=language)


async def reverse_geocode(
    latitude: float,
    longitude: float,
    *,
    language: str = "pt-BR",
) -> list[dict[str, Any]]:
    """Reverse geocode: coordinates to address."""
    logger.info("reverse_geocode", lat=latitude, lng=longitude)
    return await reverse_geocode_impl(
        latitude=latitude,
        longitude=longitude,
        language=language,
    )
