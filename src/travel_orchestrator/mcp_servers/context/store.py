"""In-memory preference store with a backend-swappable interface.

Stores user preferences keyed by ``(user_id, resource_type)``.
The current implementation is a plain dict; the abstract base class
:class:`PreferenceBackend` defines the contract for a future
PostgreSQL (or Redis) backend.
"""

from __future__ import annotations

import abc
import copy
from typing import Any


# ---------------------------------------------------------------------------
# Resource types recognised by the context server
# ---------------------------------------------------------------------------

RESOURCE_TYPES: list[str] = [
    "travel_style",
    "dietary_restrictions",
    "past_trips",
    "accommodation_preferences",
]


# ---------------------------------------------------------------------------
# Sensible defaults for each resource type
# ---------------------------------------------------------------------------

_DEFAULTS: dict[str, Any] = {
    "travel_style": {
        "style": "cultural",
        "pace": "moderate",
    },
    "dietary_restrictions": [],
    "past_trips": [],
    "accommodation_preferences": {
        "type": "hotel",
        "amenities": ["wifi"],
    },
}


def get_default(resource_type: str) -> Any:
    """Return a deep-copied default for *resource_type*."""
    if resource_type not in _DEFAULTS:
        raise KeyError(f"Unknown resource type: {resource_type}")
    return copy.deepcopy(_DEFAULTS[resource_type])


# ---------------------------------------------------------------------------
# Abstract backend
# ---------------------------------------------------------------------------


class PreferenceBackend(abc.ABC):
    """Interface that any concrete preference store must implement."""

    @abc.abstractmethod
    async def get(self, user_id: str, resource_type: str) -> Any: ...

    @abc.abstractmethod
    async def set(self, user_id: str, resource_type: str, value: Any) -> None: ...

    @abc.abstractmethod
    async def list_for_user(self, user_id: str) -> dict[str, Any]: ...

    @abc.abstractmethod
    async def delete(self, user_id: str, resource_type: str) -> bool: ...


# ---------------------------------------------------------------------------
# In-memory implementation
# ---------------------------------------------------------------------------


class InMemoryStore(PreferenceBackend):
    """Dict-backed preference store suitable for development and tests."""

    def __init__(self) -> None:
        self._data: dict[str, dict[str, Any]] = {}

    async def get(self, user_id: str, resource_type: str) -> Any:
        """Return stored value or the default for *resource_type*."""
        user_prefs = self._data.get(user_id, {})
        if resource_type in user_prefs:
            return copy.deepcopy(user_prefs[resource_type])
        return get_default(resource_type)

    async def set(self, user_id: str, resource_type: str, value: Any) -> None:
        if resource_type not in RESOURCE_TYPES:
            raise KeyError(f"Unknown resource type: {resource_type}")
        self._data.setdefault(user_id, {})[resource_type] = copy.deepcopy(value)

    async def list_for_user(self, user_id: str) -> dict[str, Any]:
        """Return all preferences for *user_id*, filling in defaults."""
        result: dict[str, Any] = {}
        for rt in RESOURCE_TYPES:
            result[rt] = await self.get(user_id, rt)
        return result

    async def delete(self, user_id: str, resource_type: str) -> bool:
        user_prefs = self._data.get(user_id, {})
        if resource_type in user_prefs:
            del user_prefs[resource_type]
            return True
        return False
