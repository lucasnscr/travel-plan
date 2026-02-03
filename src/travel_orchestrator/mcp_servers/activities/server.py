"""MCP tool server for activity discovery.

Exposes ``discover_activities`` — returns scored, filtered, and
category-diverse activities for a destination using the mock provider.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from travel_orchestrator.mcp_servers.activities.mock_provider import (
    discover_activities,
)
from travel_orchestrator.utils.logging import get_logger

logger = get_logger(__name__)

app = Server("activities-server")


# ---------------------------------------------------------------------------
# Implementation
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
# MCP handlers
# ---------------------------------------------------------------------------


@app.list_tools()
async def list_tools() -> list[Tool]:
    """Advertise the discover_activities tool."""
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
        )
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
