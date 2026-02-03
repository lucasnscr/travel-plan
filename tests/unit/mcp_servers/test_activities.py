"""Unit tests for the activity discovery MCP server and mock provider."""

from __future__ import annotations

import json

import pytest

from travel_orchestrator.mcp_servers.activities.mock_provider import (
    INTEREST_TO_CATEGORIES,
    discover_activities,
)
from travel_orchestrator.mcp_servers.activities.server import (
    call_tool,
    discover_activities_impl,
    list_tools,
)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_RIO = "Rio de Janeiro"
_PARIS = "Paris"
_TOKYO = "Tokyo"
_LISBON = "Lisbon"


def _summer_dates() -> tuple[str, str]:
    """Northern hemisphere summer / southern hemisphere winter."""
    return ("2025-07-01", "2025-07-10")


def _carnival_dates() -> tuple[str, str]:
    """Rio Carnival window."""
    return ("2025-02-25", "2025-03-05")


def _cherry_blossom_dates() -> tuple[str, str]:
    """Tokyo cherry blossom season."""
    return ("2025-03-25", "2025-04-05")


# ===================================================================
# Mock provider — basic queries
# ===================================================================


class TestDiscoverActivitiesBasic:
    def test_returns_activities_for_known_city(self) -> None:
        results = discover_activities(
            _RIO, ["history", "food"], *_summer_dates(), budget_per_day=500
        )
        assert len(results) > 0
        assert all(r["id"].startswith("act-") for r in results)

    def test_unknown_city_returns_empty(self) -> None:
        results = discover_activities(
            "Atlantis", ["history"], *_summer_dates(), budget_per_day=500
        )
        assert results == []

    def test_deterministic(self) -> None:
        a = discover_activities(_PARIS, ["art"], *_summer_dates(), budget_per_day=200)
        b = discover_activities(_PARIS, ["art"], *_summer_dates(), budget_per_day=200)
        assert a == b

    def test_activity_fields_complete(self) -> None:
        results = discover_activities(
            _PARIS, ["history"], *_summer_dates(), budget_per_day=200
        )
        act = results[0]
        assert isinstance(act["id"], str)
        assert isinstance(act["name"], str)
        assert isinstance(act["category"], str)
        assert isinstance(act["address"], str)
        assert "lat" in act["coordinates"] and "lng" in act["coordinates"]
        assert isinstance(act["duration_minutes"], int)
        assert isinstance(act["price"], (int, float))
        assert isinstance(act["currency"], str)
        assert isinstance(act["opening_hours"], dict)
        assert isinstance(act["requires_booking"], bool)
        assert isinstance(act["indoor"], bool)
        assert isinstance(act["description"], str)
        assert 0 <= act["score"] <= 1.5  # base_score + boosts can exceed 1.0

    def test_max_50_results(self) -> None:
        results = discover_activities(
            _PARIS, ["history", "food", "art", "nature", "shopping", "nightlife"],
            *_summer_dates(),
            budget_per_day=99999,
        )
        assert len(results) <= 50

    def test_scores_descending(self) -> None:
        results = discover_activities(
            _TOKYO, ["food", "culture"], *_summer_dates(), budget_per_day=99999
        )
        scores = [r["score"] for r in results]
        assert scores == sorted(scores, reverse=True)


# ===================================================================
# Filtering
# ===================================================================


class TestFiltering:
    def test_budget_filter_excludes_expensive(self) -> None:
        results = discover_activities(
            _PARIS, ["art", "food"], *_summer_dates(), budget_per_day=10
        )
        for r in results:
            assert r["price"] <= 10 or r["price"] == 0

    def test_zero_budget_returns_free_only(self) -> None:
        results = discover_activities(
            _RIO, ["nature", "culture"], *_summer_dates(), budget_per_day=0
        )
        for r in results:
            assert r["price"] == 0

    def test_interest_relevance_boosts_matching(self) -> None:
        food_results = discover_activities(
            _RIO, ["food"], *_summer_dates(), budget_per_day=500
        )
        # Restaurants should appear near the top
        top_categories = [r["category"] for r in food_results[:5]]
        assert "restaurant" in top_categories

    def test_category_diversity(self) -> None:
        results = discover_activities(
            _PARIS,
            ["history", "food", "art", "nature", "shopping", "nightlife"],
            *_summer_dates(),
            budget_per_day=99999,
        )
        categories = {r["category"] for r in results}
        # Should have at least 3 different categories
        assert len(categories) >= 3


# ===================================================================
# Seasonal events
# ===================================================================


class TestSeasonalEvents:
    def test_carnival_appears_in_feb(self) -> None:
        results = discover_activities(
            _RIO, ["culture", "music"], *_carnival_dates(), budget_per_day=500
        )
        names = [r["name"] for r in results]
        assert "Carnaval do Rio" in names

    def test_carnival_absent_in_july(self) -> None:
        results = discover_activities(
            _RIO, ["culture", "music"], *_summer_dates(), budget_per_day=500
        )
        names = [r["name"] for r in results]
        assert "Carnaval do Rio" not in names

    def test_cherry_blossom_in_spring(self) -> None:
        results = discover_activities(
            _TOKYO, ["nature", "photography"], *_cherry_blossom_dates(), budget_per_day=99999
        )
        names = [r["name"] for r in results]
        assert "Hanami — Cherry Blossom" in names

    def test_cherry_blossom_absent_in_summer(self) -> None:
        results = discover_activities(
            _TOKYO, ["nature"], *_summer_dates(), budget_per_day=99999
        )
        names = [r["name"] for r in results]
        assert "Hanami — Cherry Blossom" not in names

    def test_lisbon_santos_in_june(self) -> None:
        results = discover_activities(
            _LISBON, ["culture", "food"], "2025-06-10", "2025-06-20", budget_per_day=99999
        )
        names = [r["name"] for r in results]
        assert "Festas de Santo António" in names


# ===================================================================
# Climate-aware filtering
# ===================================================================


class TestClimateAware:
    def test_beach_available_in_warm_season(self) -> None:
        # Rio in December (southern summer)
        results = discover_activities(
            _RIO, ["beach"], "2025-12-15", "2025-12-20", budget_per_day=500
        )
        names = [r["name"] for r in results]
        beach_names = [n for n in names if "praia" in n.lower() or "beach" in n.lower()]
        assert len(beach_names) > 0

    def test_beach_filtered_in_cold_season(self) -> None:
        # Paris in January — no beach activities
        results = discover_activities(
            _PARIS, ["beach"], "2025-01-10", "2025-01-15", budget_per_day=500
        )
        names = [r["name"] for r in results]
        # Lisbon's Cascais or Paris shouldn't have beach in Jan
        beach_names = [n for n in names if "praia" in n.lower() or "plage" in n.lower()]
        assert len(beach_names) == 0


# ===================================================================
# Interest mapping
# ===================================================================


class TestInterestMapping:
    def test_all_interests_have_categories(self) -> None:
        for interest, cats in INTEREST_TO_CATEGORIES.items():
            assert len(cats) > 0, f"{interest} has no mapped categories"

    def test_history_maps_to_museum_and_tour(self) -> None:
        cats = INTEREST_TO_CATEGORIES["history"]
        assert "museum" in cats
        assert "tour" in cats


# ===================================================================
# MCP server handlers
# ===================================================================


class TestMCPHandlers:
    async def test_list_tools(self) -> None:
        tools = await list_tools()
        assert len(tools) == 1
        assert tools[0].name == "discover_activities"
        schema = tools[0].inputSchema
        assert "destination" in schema["properties"]
        assert "interests" in schema["properties"]
        assert "date_range" in schema["properties"]
        assert "budget_per_day" in schema["properties"]

    async def test_call_tool_success(self) -> None:
        result = await call_tool(
            "discover_activities",
            {
                "destination": "Paris",
                "interests": ["art", "food"],
                "date_range": {"start": "2025-07-01", "end": "2025-07-05"},
                "budget_per_day": 100,
            },
        )
        assert len(result) == 1
        assert result[0].type == "text"
        data = json.loads(result[0].text)
        assert isinstance(data, list)
        assert len(data) > 0
        assert "name" in data[0]
        assert "score" in data[0]

    async def test_call_tool_unknown_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown tool"):
            await call_tool("nonexistent", {})


# ===================================================================
# Implementation validation
# ===================================================================


class TestImplValidation:
    async def test_empty_destination_raises(self) -> None:
        with pytest.raises(ValueError, match="destination"):
            await discover_activities_impl(
                destination="",
                interests=["food"],
                date_range={"start": "2025-07-01", "end": "2025-07-05"},
                budget_per_day=100,
            )

    async def test_negative_budget_raises(self) -> None:
        with pytest.raises(ValueError, match="budget_per_day"):
            await discover_activities_impl(
                destination="Paris",
                interests=["food"],
                date_range={"start": "2025-07-01", "end": "2025-07-05"},
                budget_per_day=-10,
            )

    async def test_missing_date_range_raises(self) -> None:
        with pytest.raises(ValueError, match="date_range"):
            await discover_activities_impl(
                destination="Paris",
                interests=["food"],
                date_range={},
                budget_per_day=100,
            )

    async def test_impl_returns_list_of_dicts(self) -> None:
        result = await discover_activities_impl(
            destination="Tokyo",
            interests=["food", "culture"],
            date_range={"start": "2025-07-01", "end": "2025-07-05"},
            budget_per_day=99999,
        )
        assert isinstance(result, list)
        assert all(isinstance(r, dict) for r in result)
