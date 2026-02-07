"""MCP tool server for activity/place discovery.

Exposes 9 tools:
- discover_activities (existing, backward compatible)
- search_activities
- search_restaurants
- get_place_details
- get_place_photos
- nearby_search
- get_directions
- geocode
- reverse_geocode

Primary provider: Google Places API (New).
Fallback: deterministic mock provider (no API key needed).
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from travel_orchestrator.mcp_servers.activities.google_places_provider import (
    GooglePlacesProvider,
)
from travel_orchestrator.mcp_servers.activities.mock_provider import (
    discover_activities,
    generate_directions,
    generate_geocode,
    generate_nearby_search,
    generate_place_details,
    generate_place_photos,
    generate_restaurant_search,
    generate_reverse_geocode,
    generate_text_search,
)
from travel_orchestrator.mcp_servers.weather.cache import TTLCache
from travel_orchestrator.utils.logging import get_logger

logger = get_logger(__name__)

app = Server("activities-server")

# ---------------------------------------------------------------------------
# Module-level singletons
# ---------------------------------------------------------------------------

_cache = TTLCache(default_ttl_seconds=3600)
_google_provider = GooglePlacesProvider(cache=_cache)


# ---------------------------------------------------------------------------
# Implementation — existing tool (backward compatible)
# ---------------------------------------------------------------------------


async def discover_activities_impl(
    destination: str,
    interests: list[str],
    date_range: dict[str, str],
    budget_per_day: float,
) -> list[dict[str, Any]]:
    """Validate, query mock provider, return dicts."""
    if not destination:
        raise ValueError("destination is required")
    if budget_per_day < 0:
        raise ValueError("budget_per_day must be >= 0")

    start_date = date_range.get("start", date_range.get("start_date", ""))
    end_date = date_range.get("end", date_range.get("end_date", ""))
    if not start_date or not end_date:
        raise ValueError("date_range must include 'start' and 'end'")

    logger.info(
        "discover_activities_started",
        destination=destination,
        interests=interests,
        start_date=start_date,
        end_date=end_date,
        budget_per_day=budget_per_day,
    )

    activities = discover_activities(
        destination=destination,
        interests=interests,
        start_date=start_date,
        end_date=end_date,
        budget_per_day=budget_per_day,
    )

    logger.info(
        "discover_activities_completed",
        destination=destination,
        count=len(activities),
    )

    return [dict(a) for a in activities]


# ---------------------------------------------------------------------------
# Implementation — new tools
# ---------------------------------------------------------------------------


async def search_activities_impl(
    query: str,
    location: str,
    *,
    language: str = "pt-BR",
    max_results: int = 20,
) -> list[dict[str, Any]]:
    """Search for activities/attractions via Google Places or mock."""
    if not query:
        raise ValueError("query is required")
    if not location:
        raise ValueError("location is required")

    if _google_provider.is_configured:
        try:
            places = await _google_provider.text_search(
                f"{query} in {location}",
                language=language,
                max_results=max_results,
            )
            return [p.model_dump() for p in places]
        except Exception:
            logger.warning("google_text_search_failed_fallback_mock", query=query)

    return generate_text_search(query, location, max_results=max_results)


async def search_restaurants_impl(
    location: str,
    *,
    cuisine: str | None = None,
    price_level: int | None = None,
    language: str = "pt-BR",
    max_results: int = 20,
) -> list[dict[str, Any]]:
    """Search for restaurants via Google Places or mock."""
    if not location:
        raise ValueError("location is required")

    if _google_provider.is_configured:
        try:
            query = f"restaurants in {location}"
            if cuisine:
                query = f"{cuisine} restaurants in {location}"
            places = await _google_provider.text_search(
                query,
                language=language,
                max_results=max_results,
            )
            results = [p.model_dump() for p in places]
            if price_level is not None:
                results = [
                    r for r in results
                    if r.get("price_level") is None
                    or r["price_level"] <= price_level
                ]
            return results
        except Exception:
            logger.warning("google_restaurant_search_failed_fallback_mock")

    return generate_restaurant_search(
        location,
        cuisine=cuisine,
        price_level=price_level,
        max_results=max_results,
    )


async def get_place_details_impl(
    place_id: str,
    *,
    language: str = "pt-BR",
) -> dict[str, Any]:
    """Get full place details via Google Places or mock."""
    if not place_id:
        raise ValueError("place_id is required")

    if _google_provider.is_configured:
        try:
            detail = await _google_provider.get_place_details(
                place_id, language=language,
            )
            return detail.model_dump()
        except Exception:
            logger.warning("google_place_details_failed_fallback_mock", place_id=place_id)

    return generate_place_details(place_id)


async def get_place_photos_impl(
    place_id: str,
    *,
    max_photos: int = 5,
) -> list[dict[str, Any]]:
    """Get place photos via Google Places or mock."""
    if not place_id:
        raise ValueError("place_id is required")

    if _google_provider.is_configured:
        try:
            photos = await _google_provider.get_place_photos(
                place_id, max_photos=max_photos,
            )
            return [p.model_dump() for p in photos]
        except Exception:
            logger.warning("google_place_photos_failed_fallback_mock", place_id=place_id)

    return generate_place_photos(place_id, max_photos=max_photos)


async def nearby_search_impl(
    latitude: float,
    longitude: float,
    radius_meters: int = 1000,
    *,
    place_type: str = "tourist_attraction",
    language: str = "pt-BR",
    max_results: int = 20,
) -> list[dict[str, Any]]:
    """Search nearby places via Google Places or mock."""
    if _google_provider.is_configured:
        try:
            places = await _google_provider.nearby_search(
                latitude, longitude, radius_meters,
                place_type=place_type,
                language=language,
                max_results=max_results,
            )
            return [p.model_dump() for p in places]
        except Exception:
            logger.warning("google_nearby_search_failed_fallback_mock")

    return generate_nearby_search(
        latitude, longitude, radius_meters,
        place_type=place_type,
        max_results=max_results,
    )


async def get_directions_impl(
    origin: str,
    destination: str,
    *,
    mode: str = "walking",
    language: str = "pt-BR",
) -> dict[str, Any]:
    """Get directions via Google Maps or mock."""
    if not origin:
        raise ValueError("origin is required")
    if not destination:
        raise ValueError("destination is required")

    if _google_provider.is_configured:
        try:
            route = await _google_provider.get_directions(
                origin, destination, mode=mode, language=language,
            )
            return route.model_dump()
        except Exception:
            logger.warning("google_directions_failed_fallback_mock")

    return generate_directions(origin, destination, mode=mode)


async def geocode_impl(
    address: str,
    *,
    language: str = "pt-BR",
) -> list[dict[str, Any]]:
    """Forward geocode via Google Maps or mock."""
    if not address:
        raise ValueError("address is required")

    if _google_provider.is_configured:
        try:
            results = await _google_provider.geocode(
                address, language=language,
            )
            return [r.model_dump() for r in results]
        except Exception:
            logger.warning("google_geocode_failed_fallback_mock")

    return generate_geocode(address)


async def reverse_geocode_impl(
    latitude: float,
    longitude: float,
    *,
    language: str = "pt-BR",
) -> list[dict[str, Any]]:
    """Reverse geocode via Google Maps or mock."""
    if _google_provider.is_configured:
        try:
            results = await _google_provider.reverse_geocode(
                latitude, longitude, language=language,
            )
            return [r.model_dump() for r in results]
        except Exception:
            logger.warning("google_reverse_geocode_failed_fallback_mock")

    return generate_reverse_geocode(latitude, longitude)


# ---------------------------------------------------------------------------
# MCP handlers
# ---------------------------------------------------------------------------


@app.list_tools()
async def list_tools() -> list[Tool]:
    """Advertise all 9 activity/place tools."""
    return [
        Tool(
            name="discover_activities",
            description=(
                "Discover activities and attractions at a travel destination. "
                "Returns up to 50 scored options filtered by interests, budget, "
                "and category diversity. Includes seasonal events."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "destination": {
                        "type": "string",
                        "description": "City name (e.g. 'Paris', 'Rio de Janeiro')",
                    },
                    "interests": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "Traveler interests — e.g. ['history','food','nature']. "
                            "Used to score and filter activities."
                        ),
                    },
                    "date_range": {
                        "type": "object",
                        "properties": {
                            "start": {
                                "type": "string",
                                "format": "date",
                                "description": "Start date (YYYY-MM-DD)",
                            },
                            "end": {
                                "type": "string",
                                "format": "date",
                                "description": "End date (YYYY-MM-DD)",
                            },
                        },
                        "required": ["start", "end"],
                    },
                    "budget_per_day": {
                        "type": "number",
                        "minimum": 0,
                        "description": "Maximum price per activity in local currency",
                    },
                },
                "required": ["destination", "interests", "date_range", "budget_per_day"],
            },
        ),
        Tool(
            name="search_activities",
            description=(
                "Search for activities, attractions, and points of interest "
                "by text query at a location. Uses Google Places API when "
                "available, falls back to curated mock data."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search text (e.g. 'museums in Paris')",
                    },
                    "location": {
                        "type": "string",
                        "description": "City or area name",
                    },
                    "language": {
                        "type": "string",
                        "default": "pt-BR",
                        "description": "Language code for results",
                    },
                    "max_results": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 60,
                        "default": 20,
                    },
                },
                "required": ["query", "location"],
            },
        ),
        Tool(
            name="search_restaurants",
            description=(
                "Search for restaurants at a location, optionally filtered "
                "by cuisine type and price level."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "City or area name",
                    },
                    "cuisine": {
                        "type": "string",
                        "description": "Cuisine filter (e.g. 'japanese', 'italian')",
                    },
                    "price_level": {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 4,
                        "description": "Max price level (0=free, 4=very expensive)",
                    },
                    "language": {
                        "type": "string",
                        "default": "pt-BR",
                    },
                    "max_results": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 60,
                        "default": 20,
                    },
                },
                "required": ["location"],
            },
        ),
        Tool(
            name="get_place_details",
            description=(
                "Get full details for a place including reviews, photos, "
                "opening hours, contact info, and editorial summary."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "place_id": {
                        "type": "string",
                        "description": "Google Place ID or mock place ID",
                    },
                    "language": {
                        "type": "string",
                        "default": "pt-BR",
                    },
                },
                "required": ["place_id"],
            },
        ),
        Tool(
            name="get_place_photos",
            description=(
                "Get photo URLs for a place. Returns up to 10 photos "
                "with URLs at 800px width."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "place_id": {
                        "type": "string",
                        "description": "Google Place ID or mock place ID",
                    },
                    "max_photos": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 10,
                        "default": 5,
                    },
                },
                "required": ["place_id"],
            },
        ),
        Tool(
            name="nearby_search",
            description=(
                "Search for places near specific coordinates within a "
                "given radius. Useful for finding attractions near a hotel."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "latitude": {"type": "number", "description": "Center latitude"},
                    "longitude": {"type": "number", "description": "Center longitude"},
                    "radius_meters": {
                        "type": "integer",
                        "minimum": 100,
                        "maximum": 50000,
                        "default": 1000,
                        "description": "Search radius in meters",
                    },
                    "place_type": {
                        "type": "string",
                        "default": "tourist_attraction",
                        "description": "Google place type filter",
                    },
                    "language": {"type": "string", "default": "pt-BR"},
                    "max_results": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 60,
                        "default": 20,
                    },
                },
                "required": ["latitude", "longitude"],
            },
        ),
        Tool(
            name="get_directions",
            description=(
                "Get directions between two locations with distance and "
                "duration. Supports walking, driving, transit, bicycling."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "origin": {
                        "type": "string",
                        "description": "Origin address or place name",
                    },
                    "destination": {
                        "type": "string",
                        "description": "Destination address or place name",
                    },
                    "mode": {
                        "type": "string",
                        "enum": ["walking", "driving", "transit", "bicycling"],
                        "default": "walking",
                    },
                    "language": {"type": "string", "default": "pt-BR"},
                },
                "required": ["origin", "destination"],
            },
        ),
        Tool(
            name="geocode",
            description=(
                "Convert an address or place name to geographic coordinates "
                "(latitude/longitude)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "address": {
                        "type": "string",
                        "description": "Address to geocode",
                    },
                    "language": {"type": "string", "default": "pt-BR"},
                },
                "required": ["address"],
            },
        ),
        Tool(
            name="reverse_geocode",
            description=(
                "Convert geographic coordinates to a human-readable address."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "latitude": {"type": "number"},
                    "longitude": {"type": "number"},
                    "language": {"type": "string", "default": "pt-BR"},
                },
                "required": ["latitude", "longitude"],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Dispatch tool call."""
    if name == "discover_activities":
        result = await discover_activities_impl(
            destination=arguments["destination"],
            interests=arguments["interests"],
            date_range=arguments["date_range"],
            budget_per_day=arguments["budget_per_day"],
        )
        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False))]

    if name == "search_activities":
        result = await search_activities_impl(
            query=arguments["query"],
            location=arguments["location"],
            language=arguments.get("language", "pt-BR"),
            max_results=arguments.get("max_results", 20),
        )
        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False))]

    if name == "search_restaurants":
        result = await search_restaurants_impl(
            location=arguments["location"],
            cuisine=arguments.get("cuisine"),
            price_level=arguments.get("price_level"),
            language=arguments.get("language", "pt-BR"),
            max_results=arguments.get("max_results", 20),
        )
        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False))]

    if name == "get_place_details":
        result = await get_place_details_impl(
            place_id=arguments["place_id"],
            language=arguments.get("language", "pt-BR"),
        )
        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False))]

    if name == "get_place_photos":
        result = await get_place_photos_impl(
            place_id=arguments["place_id"],
            max_photos=arguments.get("max_photos", 5),
        )
        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False))]

    if name == "nearby_search":
        result = await nearby_search_impl(
            latitude=arguments["latitude"],
            longitude=arguments["longitude"],
            radius_meters=arguments.get("radius_meters", 1000),
            place_type=arguments.get("place_type", "tourist_attraction"),
            language=arguments.get("language", "pt-BR"),
            max_results=arguments.get("max_results", 20),
        )
        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False))]

    if name == "get_directions":
        result = await get_directions_impl(
            origin=arguments["origin"],
            destination=arguments["destination"],
            mode=arguments.get("mode", "walking"),
            language=arguments.get("language", "pt-BR"),
        )
        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False))]

    if name == "geocode":
        result = await geocode_impl(
            address=arguments["address"],
            language=arguments.get("language", "pt-BR"),
        )
        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False))]

    if name == "reverse_geocode":
        result = await reverse_geocode_impl(
            latitude=arguments["latitude"],
            longitude=arguments["longitude"],
            language=arguments.get("language", "pt-BR"),
        )
        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False))]

    raise ValueError(f"Unknown tool: {name}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


async def run_server() -> None:
    """Start the MCP server over stdio."""
    logger.info("activities_server_starting")
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options(),
        )


def main() -> None:
    """CLI entry point."""
    asyncio.run(run_server())


if __name__ == "__main__":
    main()
