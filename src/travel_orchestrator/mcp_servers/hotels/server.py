"""MCP tool server for hotel search.

Proxies search requests to the Enuygun upstream MCP, normalises
results into ``HotelResult`` models, scores them, and returns the
top 15 options.
"""

from __future__ import annotations

import asyncio
import datetime
import json
from typing import Any

from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from travel_orchestrator.mcp_servers.hotels.enuygun_adapter import search_hotels
from travel_orchestrator.mcp_servers.hotels.mock_provider import generate_hotels
from travel_orchestrator.mcp_servers.hotels.models import (
    HotelLocation,
    HotelResult,
    HotelSearchInput,
)
from travel_orchestrator.mcp_servers.hotels.scoring import compute_scores
from travel_orchestrator.utils.logging import get_logger

logger = get_logger(__name__)

MAX_RESULTS = 15

app = Server("hotels-server")


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
    if price_total is not None and nights > 0:
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

    return HotelResult(
        provider="enuygun",
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
        score=0.0,
        raw=raw,
    )


# ---------------------------------------------------------------------------
# Core implementation
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
    # Validate via pydantic
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

    # Call upstream (fall back to mock provider on failure)
    try:
        raw_results = await search_hotels(
            destination=validated.destination,
            check_in=validated.check_in,
            check_out=validated.check_out,
            guests=validated.guests,
        )
    except Exception:
        logger.warning("upstream_failed_using_mock", destination=validated.destination)
        raw_results = generate_hotels(
            destination=validated.destination,
            check_in=validated.check_in,
            check_out=validated.check_out,
            guests=validated.guests,
        )

    # Normalise
    hotels = [normalise_raw(r, nights) for r in raw_results]
    count_before_filter = len(hotels)

    # Filter: min_stars
    if validated.min_stars is not None:
        hotels = [
            h for h in hotels if h.stars is not None and h.stars >= validated.min_stars
        ]

    # Score (amenities used as boost inside scoring)
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


# ---------------------------------------------------------------------------
# MCP handlers
# ---------------------------------------------------------------------------


@app.list_tools()
async def list_tools() -> list[Tool]:
    """Advertise the search_hotels tool."""
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
        )
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Dispatch tool call."""
    if name == "search_hotels":
        result = await search_hotels_impl(**arguments)
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
