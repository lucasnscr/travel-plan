"""MCP tool server for hotel search.

Dispatches to the Booking.com RapidAPI provider when configured,
falls back to Enuygun upstream MCP, and ultimately to the mock
provider. All responses include a ``data_source`` field for
transparency.
"""

from __future__ import annotations

import asyncio
import datetime
import json
from typing import Any

from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from travel_orchestrator.mcp_servers.hotels.booking_provider import BookingProvider
from travel_orchestrator.mcp_servers.hotels.mock_provider import (
    generate_facilities,
    generate_hotel_details,
    generate_hotels,
    generate_nearby_hotels,
)
from travel_orchestrator.mcp_servers.hotels.models import (
    HotelCompareInput,
    HotelLocation,
    HotelResult,
    HotelSearchByCoordinatesInput,
    HotelSearchInput,
)
from travel_orchestrator.mcp_servers.hotels.scoring import compute_scores
from travel_orchestrator.mcp_servers.weather.cache import TTLCache
from travel_orchestrator.utils.logging import get_logger

logger = get_logger(__name__)

MAX_RESULTS = 15

app = Server("hotels-server")

# Module-level singletons
_cache = TTLCache(default_ttl_seconds=3600)  # 1 hour
_booking_provider = BookingProvider(cache=_cache)


# ---------------------------------------------------------------------------
# Raw → HotelResult normalisation
# ---------------------------------------------------------------------------


def normalise_raw(raw: dict[str, Any], nights: int) -> HotelResult:
    """Convert an upstream raw dict into a typed :class:`HotelResult`.

    Field names vary between providers so we attempt multiple keys
    for each attribute.
    """
    name = (
        raw.get("name")
        or raw.get("hotelName")
        or raw.get("hotel_name")
        or "Unknown"
    )

    stars = raw.get("stars") or raw.get("star_rating") or raw.get("starRating")
    if stars is not None:
        stars = int(stars)

    review_score = (
        raw.get("review_score")
        or raw.get("reviewScore")
        or raw.get("rating")
        or raw.get("guestRating")
    )
    if review_score is not None:
        review_score = float(review_score)

    price_total = (
        raw.get("price_total")
        or raw.get("totalPrice")
        or raw.get("total_price")
        or raw.get("price")
    )
    if price_total is not None:
        price_total = float(price_total)

    currency = raw.get("currency") or raw.get("priceCurrency")

    nightly_avg: float | None = None
    if raw.get("nightly_price_avg") is not None:
        nightly_avg = float(raw["nightly_price_avg"])
    elif price_total is not None and nights > 0:
        nightly_avg = round(price_total / nights, 2)

    # Location
    lat = raw.get("latitude") or raw.get("lat") or 0.0
    lng = raw.get("longitude") or raw.get("lng") or raw.get("lon") or 0.0
    area = raw.get("area") or raw.get("neighborhood") or raw.get("district")
    location = HotelLocation(lat=float(lat), lng=float(lng), area=area)

    distance = raw.get("distance_to_center_km") or raw.get("distanceToCenter")
    if distance is not None:
        distance = float(distance)

    amenities_raw = raw.get("amenities") or raw.get("facilities") or []
    if isinstance(amenities_raw, str):
        amenities_raw = [a.strip() for a in amenities_raw.split(",")]
    amenities_list: list[str] = [str(a) for a in amenities_raw]

    deep_link = raw.get("deep_link") or raw.get("deepLink") or raw.get("url")

    photos = raw.get("photos") or []
    if isinstance(photos, str):
        photos = [photos]

    data_source = raw.get("data_source", "mock")
    provider = "booking" if data_source == "booking" else "enuygun"

    return HotelResult(
        provider=provider,
        name=name,
        stars=stars,
        review_score=review_score,
        price_total=price_total,
        currency=currency,
        nightly_price_avg=nightly_avg,
        location=location,
        distance_to_center_km=distance,
        amenities=amenities_list,
        deep_link=deep_link,
        photos=list(photos),
        score=0.0,
        data_source=data_source,
        raw=raw,
    )


# ---------------------------------------------------------------------------
# Core implementations
# ---------------------------------------------------------------------------


async def search_hotels_impl(
    destination: str,
    check_in: str,
    check_out: str,
    guests: int = 1,
    preferences: dict[str, Any] | None = None,
    location_centrality: float = 0.5,
    min_stars: int | None = None,
    amenities: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Validate input, call upstream, normalise, score, and filter."""
    validated = HotelSearchInput(
        destination=destination,
        check_in=check_in,
        check_out=check_out,
        guests=guests,
        preferences=preferences or {},
        location_centrality=location_centrality,
        min_stars=min_stars,
        amenities=amenities or [],
    )

    nights = (
        datetime.date.fromisoformat(validated.check_out)
        - datetime.date.fromisoformat(validated.check_in)
    ).days
    if nights <= 0:
        raise ValueError("check_out must be after check_in")

    logger.info(
        "search_hotels_started",
        destination=validated.destination,
        check_in=validated.check_in,
        check_out=validated.check_out,
        guests=validated.guests,
        nights=nights,
    )

    raw_results = await _fetch_hotels(
        validated.destination, validated.check_in,
        validated.check_out, validated.guests,
    )

    # Normalise
    hotels = [normalise_raw(r, nights) for r in raw_results]
    count_before_filter = len(hotels)

    # Filter: min_stars
    if validated.min_stars is not None:
        hotels = [
            h for h in hotels if h.stars is not None and h.stars >= validated.min_stars
        ]

    # Score
    hotels = compute_scores(hotels, desired_amenities=validated.amenities)

    # Limit
    hotels = hotels[:MAX_RESULTS]

    logger.info(
        "search_hotels_completed",
        destination=validated.destination,
        count_raw=len(raw_results),
        count_before_filter=count_before_filter,
        count_after_filter=len(hotels),
    )

    return [h.model_dump(mode="json") for h in hotels]


async def get_hotel_details_impl(hotel_id: str) -> dict[str, Any]:
    """Get full hotel details by ID."""
    # Try Booking.com first
    if _booking_provider.is_configured:
        try:
            return await _booking_provider.get_hotel_details(hotel_id)
        except Exception:
            logger.warning("booking_details_failed_using_mock", hotel_id=hotel_id)

    return generate_hotel_details(hotel_id)


async def search_by_coordinates_impl(
    latitude: float,
    longitude: float,
    radius_km: float,
    check_in: str,
    check_out: str,
    adults: int = 1,
) -> list[dict[str, Any]]:
    """Search hotels near a coordinate point."""
    validated = HotelSearchByCoordinatesInput(
        latitude=latitude,
        longitude=longitude,
        radius_km=radius_km,
        check_in=check_in,
        check_out=check_out,
        adults=adults,
    )

    nights = (
        datetime.date.fromisoformat(validated.check_out)
        - datetime.date.fromisoformat(validated.check_in)
    ).days
    if nights <= 0:
        raise ValueError("check_out must be after check_in")

    # Try Booking.com first
    if _booking_provider.is_configured:
        try:
            raw = await _booking_provider.search_by_coordinates(
                validated.latitude, validated.longitude,
                validated.radius_km,
                validated.check_in, validated.check_out,
                validated.adults,
            )
            hotels = [normalise_raw(r, nights) for r in raw]
            hotels = compute_scores(hotels)
            return [h.model_dump(mode="json") for h in hotels[:MAX_RESULTS]]
        except Exception:
            logger.warning("booking_coords_failed_using_mock")

    raw = generate_nearby_hotels(
        validated.latitude, validated.longitude, validated.radius_km,
        validated.check_in, validated.check_out, validated.adults,
    )
    hotels = [normalise_raw(r, nights) for r in raw]
    hotels = compute_scores(hotels)
    return [h.model_dump(mode="json") for h in hotels[:MAX_RESULTS]]


async def get_hotel_facilities_impl(hotel_id: str) -> list[dict[str, Any]]:
    """Get the facility list for a hotel."""
    if _booking_provider.is_configured:
        try:
            return await _booking_provider.get_hotel_facilities(hotel_id)
        except Exception:
            logger.warning("booking_facilities_failed_using_mock", hotel_id=hotel_id)

    return generate_facilities(hotel_id)


async def compare_hotels_impl(hotel_ids: list[str]) -> list[dict[str, Any]]:
    """Compare multiple hotels side by side."""
    validated = HotelCompareInput(hotel_ids=hotel_ids)
    results: list[dict[str, Any]] = []
    for hid in validated.hotel_ids:
        detail = await get_hotel_details_impl(hid)
        results.append(detail)
    return results


# ---------------------------------------------------------------------------
# Fetch helpers (fallback chain)
# ---------------------------------------------------------------------------


async def _fetch_hotels(
    destination: str, check_in: str, check_out: str, guests: int,
) -> list[dict[str, Any]]:
    """Try Booking.com → Enuygun → mock, in order."""
    # 1. Booking.com via RapidAPI
    if _booking_provider.is_configured:
        try:
            return await _booking_provider.search_hotels(
                destination, check_in, check_out, guests,
            )
        except Exception:
            logger.warning("booking_search_failed", destination=destination)

    # 2. Enuygun upstream MCP
    try:
        from travel_orchestrator.mcp_servers.hotels.enuygun_adapter import (
            search_hotels as enuygun_search,
        )
        return await enuygun_search(
            destination=destination,
            check_in=check_in,
            check_out=check_out,
            guests=guests,
        )
    except Exception:
        logger.warning("enuygun_failed_using_mock", destination=destination)

    # 3. Mock provider
    return generate_hotels(
        destination=destination,
        check_in=check_in,
        check_out=check_out,
        guests=guests,
    )


# ---------------------------------------------------------------------------
# MCP handlers
# ---------------------------------------------------------------------------


@app.list_tools()
async def list_tools() -> list[Tool]:
    """Advertise hotel tools."""
    return [
        Tool(
            name="search_hotels",
            description=(
                "Search for hotel accommodations at a destination. "
                "Returns up to 15 options scored by price, location, "
                "reviews, and amenity match."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "destination": {
                        "type": "string",
                        "description": "City or region (e.g. 'Istanbul', 'Paris')",
                    },
                    "check_in": {
                        "type": "string",
                        "format": "date",
                        "description": "Check-in date (YYYY-MM-DD)",
                    },
                    "check_out": {
                        "type": "string",
                        "format": "date",
                        "description": "Check-out date (YYYY-MM-DD)",
                    },
                    "guests": {
                        "type": "integer",
                        "minimum": 1,
                        "default": 1,
                    },
                    "preferences": {
                        "type": "object",
                        "description": "Extra preferences dict",
                        "default": {},
                    },
                    "location_centrality": {
                        "type": "number",
                        "minimum": 0,
                        "maximum": 1,
                        "default": 0.5,
                    },
                    "min_stars": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 5,
                        "description": "Minimum star rating filter",
                    },
                    "amenities": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Desired amenities (e.g. ['wifi','pool'])",
                        "default": [],
                    },
                },
                "required": ["destination", "check_in", "check_out"],
            },
        ),
        Tool(
            name="get_hotel_details",
            description=(
                "Get full details for a hotel including description, rooms, "
                "rates, policies, photos, and reviews."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "hotel_id": {
                        "type": "string",
                        "description": "The hotel ID returned from search_hotels",
                    },
                },
                "required": ["hotel_id"],
            },
        ),
        Tool(
            name="search_by_coordinates",
            description=(
                "Search for hotels near a geographic point. "
                "Useful for finding hotels near landmarks or airports."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "latitude": {
                        "type": "number",
                        "minimum": -90,
                        "maximum": 90,
                    },
                    "longitude": {
                        "type": "number",
                        "minimum": -180,
                        "maximum": 180,
                    },
                    "radius_km": {
                        "type": "number",
                        "minimum": 0.1,
                        "maximum": 50,
                        "default": 5,
                        "description": "Search radius in kilometers",
                    },
                    "check_in": {
                        "type": "string",
                        "format": "date",
                        "description": "Check-in date (YYYY-MM-DD)",
                    },
                    "check_out": {
                        "type": "string",
                        "format": "date",
                        "description": "Check-out date (YYYY-MM-DD)",
                    },
                    "adults": {
                        "type": "integer",
                        "minimum": 1,
                        "default": 1,
                    },
                },
                "required": ["latitude", "longitude", "check_in", "check_out"],
            },
        ),
        Tool(
            name="get_hotel_facilities",
            description=(
                "Get the list of facilities and amenities for a hotel "
                "(wifi, pool, parking, spa, etc.)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "hotel_id": {
                        "type": "string",
                        "description": "The hotel ID",
                    },
                },
                "required": ["hotel_id"],
            },
        ),
        Tool(
            name="compare_hotels",
            description=(
                "Compare multiple hotels side by side. Returns full details "
                "for each hotel for easy comparison of prices and features."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "hotel_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 2,
                        "maxItems": 10,
                        "description": "List of hotel IDs to compare",
                    },
                },
                "required": ["hotel_ids"],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Dispatch tool call."""
    if name == "search_hotels":
        result = await search_hotels_impl(**arguments)
        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False))]

    if name == "get_hotel_details":
        result = await get_hotel_details_impl(**arguments)
        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False))]

    if name == "search_by_coordinates":
        result = await search_by_coordinates_impl(**arguments)
        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False))]

    if name == "get_hotel_facilities":
        result = await get_hotel_facilities_impl(**arguments)
        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False))]

    if name == "compare_hotels":
        result = await compare_hotels_impl(**arguments)
        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False))]

    raise ValueError(f"Unknown tool: {name}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


async def run_server() -> None:
    """Start the MCP server over stdio."""
    logger.info("hotels_server_starting")
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
