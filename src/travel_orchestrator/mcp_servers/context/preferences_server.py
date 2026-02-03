"""MCP context server for user travel preferences.

Exposes four resource templates under the ``preferences://`` scheme:

- ``preferences://user_{id}/travel_style``
- ``preferences://user_{id}/dietary_restrictions``
- ``preferences://user_{id}/past_trips``
- ``preferences://user_{id}/accommodation_preferences``

Also exposes two tools for mutating preferences:

- ``set_user_preference`` — upsert a resource value
- ``delete_user_preference`` — reset a resource to its default
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    Resource,
    ResourceTemplate,
    TextContent,
    Tool,
)
from pydantic import AnyUrl

from travel_orchestrator.mcp_servers.context.store import (
    RESOURCE_TYPES,
    InMemoryStore,
)
from travel_orchestrator.utils.logging import get_logger

logger = get_logger(__name__)

app = Server("user-preferences-context")
_store = InMemoryStore()


# ---------------------------------------------------------------------------
# URI helpers
# ---------------------------------------------------------------------------


def _parse_uri(uri: AnyUrl | str) -> tuple[str, str]:
    """Extract ``(user_id, resource_type)`` from a preferences URI.

    Expected format: ``preferences://user_{id}/{resource_type}``
    With pydantic AnyUrl: ``host`` = ``user_{id}``, ``path`` = ``/{resource_type}``
    """
    if isinstance(uri, str):
        uri = AnyUrl(uri)
    user_id = uri.host or ""
    resource_type = (uri.path or "").lstrip("/")
    if not user_id or not resource_type:
        raise ValueError(f"Invalid preference URI: {uri}")
    return user_id, resource_type


def _build_uri(user_id: str, resource_type: str) -> str:
    return f"preferences://{user_id}/{resource_type}"


# ---------------------------------------------------------------------------
# MCP resource handlers
# ---------------------------------------------------------------------------


@app.list_resource_templates()
async def list_resource_templates() -> list[ResourceTemplate]:
    """Advertise parameterised resource templates."""
    return [
        ResourceTemplate(
            uriTemplate="preferences://user_{user_id}/travel_style",
            name="Travel Style Preferences",
            description="Style (adventure/cultural/relaxation/luxury) and pace (slow/moderate/fast)",
            mimeType="application/json",
        ),
        ResourceTemplate(
            uriTemplate="preferences://user_{user_id}/dietary_restrictions",
            name="Dietary Restrictions",
            description="List of dietary restrictions (vegetarian, gluten-free, etc.)",
            mimeType="application/json",
        ),
        ResourceTemplate(
            uriTemplate="preferences://user_{user_id}/past_trips",
            name="Past Trips",
            description="Previous trips used for personalised recommendations",
            mimeType="application/json",
        ),
        ResourceTemplate(
            uriTemplate="preferences://user_{user_id}/accommodation_preferences",
            name="Accommodation Preferences",
            description="Preferred accommodation type and desired amenities",
            mimeType="application/json",
        ),
    ]


@app.list_resources()
async def list_resources() -> list[Resource]:
    """Return concrete resource instances for all stored users.

    Also includes a placeholder ``user_default`` that always resolves
    to built-in defaults.
    """
    resources: list[Resource] = []
    for rt in RESOURCE_TYPES:
        resources.append(
            Resource(
                uri=AnyUrl(_build_uri("user_default", rt)),
                name=f"Default — {rt}",
                mimeType="application/json",
            )
        )
    return resources


@app.read_resource()
async def read_resource(uri: AnyUrl) -> str:
    """Read a preference resource and return its JSON representation."""
    user_id, resource_type = _parse_uri(uri)

    logger.info(
        "read_preference",
        user_id=user_id,
        resource_type=resource_type,
    )

    value = await _store.get(user_id, resource_type)
    return json.dumps(value, ensure_ascii=False)


# ---------------------------------------------------------------------------
# MCP tool handlers (for writes)
# ---------------------------------------------------------------------------


@app.list_tools()
async def list_tools() -> list[Tool]:
    """Advertise preference-mutation tools."""
    return [
        Tool(
            name="set_user_preference",
            description=(
                "Set or update a user preference resource. "
                "resource_type is one of: travel_style, dietary_restrictions, "
                "past_trips, accommodation_preferences."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "User identifier (e.g. 'user_42')",
                    },
                    "resource_type": {
                        "type": "string",
                        "enum": RESOURCE_TYPES,
                    },
                    "value": {
                        "description": "The preference value (object, array, or string)",
                    },
                },
                "required": ["user_id", "resource_type", "value"],
            },
        ),
        Tool(
            name="delete_user_preference",
            description="Delete a user preference, resetting it to its default value.",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_id": {"type": "string"},
                    "resource_type": {
                        "type": "string",
                        "enum": RESOURCE_TYPES,
                    },
                },
                "required": ["user_id", "resource_type"],
            },
        ),
        Tool(
            name="list_user_preferences",
            description="List all preferences for a user, including defaults for unset values.",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_id": {"type": "string"},
                },
                "required": ["user_id"],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Dispatch tool call."""
    if name == "set_user_preference":
        user_id = arguments["user_id"]
        resource_type = arguments["resource_type"]
        value = arguments["value"]

        await _store.set(user_id, resource_type, value)
        logger.info(
            "preference_set",
            user_id=user_id,
            resource_type=resource_type,
        )
        return [TextContent(
            type="text",
            text=json.dumps({"status": "ok", "uri": _build_uri(user_id, resource_type)}),
        )]

    if name == "delete_user_preference":
        user_id = arguments["user_id"]
        resource_type = arguments["resource_type"]
        deleted = await _store.delete(user_id, resource_type)
        logger.info(
            "preference_deleted",
            user_id=user_id,
            resource_type=resource_type,
            was_present=deleted,
        )
        return [TextContent(
            type="text",
            text=json.dumps({"status": "ok", "deleted": deleted}),
        )]

    if name == "list_user_preferences":
        user_id = arguments["user_id"]
        all_prefs = await _store.list_for_user(user_id)
        return [TextContent(
            type="text",
            text=json.dumps(all_prefs, ensure_ascii=False),
        )]

    raise ValueError(f"Unknown tool: {name}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


async def run_server() -> None:
    """Start the context server over stdio."""
    logger.info("preferences_server_starting")
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
