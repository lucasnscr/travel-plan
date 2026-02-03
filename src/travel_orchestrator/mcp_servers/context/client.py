"""Client helper for reading user preferences from the context store.

In the current architecture the context server and the graph run in the
same process, so the client reads directly from the shared
:class:`InMemoryStore` singleton — no MCP transport overhead.

When the system moves to a separate context-server process, swap this
implementation for one that connects via ``streamablehttp_client``.
"""

from __future__ import annotations

from typing import Any

from travel_orchestrator.mcp_servers.context.preferences_server import _store
from travel_orchestrator.utils.logging import get_logger

logger = get_logger(__name__)


async def get_user_preferences(user_id: str) -> dict[str, Any]:
    """Return all preferences for *user_id*, with defaults filled in.

    Returns a dict keyed by resource type::

        {
            "travel_style":               {"style": "...", "pace": "..."},
            "dietary_restrictions":        [...],
            "past_trips":                  [...],
            "accommodation_preferences":   {"type": "...", "amenities": [...]},
        }
    """
    logger.info("fetching_user_preferences", user_id=user_id)
    return await _store.list_for_user(user_id)


async def get_travel_style(user_id: str) -> dict[str, str]:
    """Shortcut: return only the travel-style preference."""
    return await _store.get(user_id, "travel_style")


async def get_accommodation_preferences(user_id: str) -> dict[str, Any]:
    """Shortcut: return only accommodation preferences."""
    return await _store.get(user_id, "accommodation_preferences")
