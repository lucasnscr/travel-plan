"""Unit tests for the user preferences context server."""

from __future__ import annotations

import json

import pytest
from pydantic import AnyUrl

from travel_orchestrator.mcp_servers.context.preferences_server import (
    _parse_uri,
    _build_uri,
    _store,
    app,
    call_tool,
    list_resource_templates,
    list_resources,
    list_tools,
    read_resource,
)
from travel_orchestrator.mcp_servers.context.store import (
    RESOURCE_TYPES,
    InMemoryStore,
    get_default,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
async def _reset_store() -> None:
    """Clear the global in-memory store before every test."""
    _store._data.clear()


# ===================================================================
# Store — InMemoryStore
# ===================================================================


class TestInMemoryStore:
    async def test_get_returns_default_for_new_user(self) -> None:
        store = InMemoryStore()
        result = await store.get("user_1", "travel_style")
        assert result == {"style": "cultural", "pace": "moderate"}

    async def test_set_then_get(self) -> None:
        store = InMemoryStore()
        await store.set("user_1", "travel_style", {"style": "adventure", "pace": "fast"})
        result = await store.get("user_1", "travel_style")
        assert result == {"style": "adventure", "pace": "fast"}

    async def test_set_unknown_resource_type_raises(self) -> None:
        store = InMemoryStore()
        with pytest.raises(KeyError, match="Unknown resource type"):
            await store.set("user_1", "nonexistent", {})

    async def test_list_for_user_includes_all_types(self) -> None:
        store = InMemoryStore()
        result = await store.list_for_user("user_1")
        assert set(result.keys()) == set(RESOURCE_TYPES)

    async def test_list_for_user_merges_custom_and_defaults(self) -> None:
        store = InMemoryStore()
        await store.set("user_1", "dietary_restrictions", ["vegan"])
        result = await store.list_for_user("user_1")
        assert result["dietary_restrictions"] == ["vegan"]
        assert result["travel_style"] == get_default("travel_style")

    async def test_delete_existing(self) -> None:
        store = InMemoryStore()
        await store.set("user_1", "travel_style", {"style": "luxury", "pace": "slow"})
        deleted = await store.delete("user_1", "travel_style")
        assert deleted is True
        # After delete, returns default
        result = await store.get("user_1", "travel_style")
        assert result == get_default("travel_style")

    async def test_delete_nonexistent(self) -> None:
        store = InMemoryStore()
        deleted = await store.delete("user_1", "travel_style")
        assert deleted is False

    async def test_get_returns_deep_copy(self) -> None:
        store = InMemoryStore()
        await store.set("user_1", "dietary_restrictions", ["vegetarian"])
        result1 = await store.get("user_1", "dietary_restrictions")
        result1.append("gluten-free")
        result2 = await store.get("user_1", "dietary_restrictions")
        assert result2 == ["vegetarian"]  # Not mutated

    async def test_set_stores_deep_copy(self) -> None:
        store = InMemoryStore()
        original = ["vegetarian"]
        await store.set("user_1", "dietary_restrictions", original)
        original.append("vegan")
        result = await store.get("user_1", "dietary_restrictions")
        assert result == ["vegetarian"]  # Not mutated


# ===================================================================
# Defaults
# ===================================================================


class TestDefaults:
    def test_all_resource_types_have_defaults(self) -> None:
        for rt in RESOURCE_TYPES:
            default = get_default(rt)
            assert default is not None

    def test_unknown_type_raises(self) -> None:
        with pytest.raises(KeyError):
            get_default("nonexistent")

    def test_travel_style_default(self) -> None:
        d = get_default("travel_style")
        assert d["style"] == "cultural"
        assert d["pace"] == "moderate"

    def test_dietary_restrictions_default(self) -> None:
        assert get_default("dietary_restrictions") == []

    def test_past_trips_default(self) -> None:
        assert get_default("past_trips") == []

    def test_accommodation_default(self) -> None:
        d = get_default("accommodation_preferences")
        assert d["type"] == "hotel"
        assert "wifi" in d["amenities"]


# ===================================================================
# URI parsing
# ===================================================================


class TestURIParsing:
    def test_parse_valid_uri(self) -> None:
        user_id, rt = _parse_uri(AnyUrl("preferences://user_42/travel_style"))
        assert user_id == "user_42"
        assert rt == "travel_style"

    def test_parse_string_uri(self) -> None:
        user_id, rt = _parse_uri("preferences://user_abc/dietary_restrictions")
        assert user_id == "user_abc"
        assert rt == "dietary_restrictions"

    def test_build_uri(self) -> None:
        uri = _build_uri("user_42", "travel_style")
        assert uri == "preferences://user_42/travel_style"

    def test_roundtrip(self) -> None:
        for rt in RESOURCE_TYPES:
            uri = _build_uri("user_99", rt)
            user_id, parsed_rt = _parse_uri(uri)
            assert user_id == "user_99"
            assert parsed_rt == rt


# ===================================================================
# MCP resource handlers
# ===================================================================


class TestResourceHandlers:
    async def test_list_resource_templates_returns_four(self) -> None:
        templates = await list_resource_templates()
        assert len(templates) == 4
        template_names = {t.name for t in templates}
        assert "Travel Style Preferences" in template_names
        assert "Dietary Restrictions" in template_names
        assert "Past Trips" in template_names
        assert "Accommodation Preferences" in template_names

    async def test_list_resources_returns_defaults(self) -> None:
        resources = await list_resources()
        assert len(resources) == len(RESOURCE_TYPES)
        for r in resources:
            assert "user_default" in str(r.uri)

    async def test_read_resource_returns_default(self) -> None:
        uri = AnyUrl("preferences://user_new/travel_style")
        result = await read_resource(uri)
        data = json.loads(result)
        assert data == {"style": "cultural", "pace": "moderate"}

    async def test_read_resource_after_set(self) -> None:
        await _store.set("user_55", "dietary_restrictions", ["vegan", "nut-free"])
        uri = AnyUrl("preferences://user_55/dietary_restrictions")
        result = await read_resource(uri)
        data = json.loads(result)
        assert data == ["vegan", "nut-free"]


# ===================================================================
# MCP tool handlers
# ===================================================================


class TestToolHandlers:
    async def test_list_tools_returns_three(self) -> None:
        tools = await list_tools()
        assert len(tools) == 3
        names = {t.name for t in tools}
        assert names == {"set_user_preference", "delete_user_preference", "list_user_preferences"}

    async def test_set_preference(self) -> None:
        result = await call_tool(
            "set_user_preference",
            {
                "user_id": "user_10",
                "resource_type": "travel_style",
                "value": {"style": "luxury", "pace": "slow"},
            },
        )
        assert len(result) == 1
        data = json.loads(result[0].text)
        assert data["status"] == "ok"
        assert "user_10" in data["uri"]

        # Verify it was stored
        stored = await _store.get("user_10", "travel_style")
        assert stored == {"style": "luxury", "pace": "slow"}

    async def test_delete_preference(self) -> None:
        await _store.set("user_10", "travel_style", {"style": "adventure", "pace": "fast"})

        result = await call_tool(
            "delete_user_preference",
            {"user_id": "user_10", "resource_type": "travel_style"},
        )
        data = json.loads(result[0].text)
        assert data["deleted"] is True

        # Back to default
        stored = await _store.get("user_10", "travel_style")
        assert stored == get_default("travel_style")

    async def test_list_user_preferences(self) -> None:
        await _store.set("user_77", "dietary_restrictions", ["halal"])

        result = await call_tool(
            "list_user_preferences",
            {"user_id": "user_77"},
        )
        data = json.loads(result[0].text)
        assert data["dietary_restrictions"] == ["halal"]
        assert data["travel_style"] == get_default("travel_style")

    async def test_unknown_tool_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown tool"):
            await call_tool("nonexistent", {})

    async def test_set_then_read_resource_roundtrip(self) -> None:
        """Full roundtrip: set via tool, read via resource."""
        await call_tool(
            "set_user_preference",
            {
                "user_id": "user_rt",
                "resource_type": "accommodation_preferences",
                "value": {"type": "airbnb", "amenities": ["kitchen", "pool"]},
            },
        )
        uri = AnyUrl("preferences://user_rt/accommodation_preferences")
        result = await read_resource(uri)
        data = json.loads(result)
        assert data == {"type": "airbnb", "amenities": ["kitchen", "pool"]}
