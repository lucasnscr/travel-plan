"""Unit tests for the search_hotels graph node."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from travel_orchestrator.graph.nodes.search_hotels import (
    _ACCOMMODATION_MIN_STARS,
    _HOTEL_BUDGET_RATIO,
    _MAX_OPTIONS,
    _PACE_CENTRALITY,
    _to_hotel_option,
    search_hotels_node,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _base_state(**overrides: Any) -> dict[str, Any]:
    """Return a minimal valid state as produced by earlier nodes."""
    state: dict[str, Any] = {
        "plan_id": "plan_test1234",
        "destination": "Paris",
        "dates": {"start_date": "2025-07-01", "end_date": "2025-07-10"},
        "budget": {"total": 5000.0, "currency": "EUR", "flexibility": 0.1},
        "traveler_profile": {
            "interests": ["culture", "food"],
            "pace": "moderate",
            "group_size": 2,
            "accommodation_type": "hotel",
        },
        "selected_flight_id": None,
        "selected_hotel_id": None,
        "selected_activity_ids": [],
        "current_cost": 0.0,
        "revision_count": 0,
        "approval_status": "pending",
        "risk_flags": [],
        "alternative_plans": {},
        "destination_analysis": None,
        "hotel_options": [],
    }
    state.update(overrides)
    return state


def _mock_hotel(
    *,
    name: str = "Hotel Test",
    stars: int = 4,
    review_score: float = 8.5,
    nightly_price_avg: float = 150.0,
    price_total: float = 1350.0,
    currency: str = "EUR",
    distance_to_center_km: float = 1.0,
    amenities: list[str] | None = None,
    score: float = 0.85,
    area: str = "Centre",
) -> dict[str, Any]:
    """Build a single scored hotel result dict as returned by server."""
    return {
        "provider": "enuygun",
        "name": name,
        "stars": stars,
        "review_score": review_score,
        "price_total": price_total,
        "currency": currency,
        "nightly_price_avg": nightly_price_avg,
        "location": {"lat": 48.856, "lng": 2.352, "area": area},
        "distance_to_center_km": distance_to_center_km,
        "amenities": amenities or ["wifi", "breakfast"],
        "deep_link": None,
        "score": score,
        "raw": {},
    }


def _mock_hotels_list(count: int = 8, base_nightly: float = 100.0) -> list[dict[str, Any]]:
    """Build a list of mock hotels with varying prices and scores."""
    hotels = []
    for i in range(count):
        hotels.append(
            _mock_hotel(
                name=f"Hotel {chr(65 + i)}",
                stars=max(2, 5 - (i % 4)),
                nightly_price_avg=base_nightly + i * 30,
                price_total=(base_nightly + i * 30) * 9,
                score=round(0.95 - i * 0.05, 2),
                distance_to_center_km=0.5 + i * 0.5,
            )
        )
    return hotels


# ===================================================================
# Budget computation
# ===================================================================


class TestBudgetComputation:
    async def test_hotel_budget_is_35_percent(self) -> None:
        hotels = [_mock_hotel(nightly_price_avg=100.0)]
        state = _base_state(budget={"total": 10000.0, "currency": "EUR", "flexibility": 0.1})
        with patch(
            "travel_orchestrator.graph.nodes.search_hotels.search_hotels",
            new_callable=AsyncMock,
            return_value=hotels,
        ):
            result = await search_hotels_node(state)
        # 10000 * 0.35 = 3500 budget, 100/night fits well within
        assert len(result["hotel_options"]) == 1

    async def test_expensive_hotels_filtered_out(self) -> None:
        """Hotels more than 120% of budget per night should be excluded."""
        # Budget: 5000 total, 35% = 1750, 9 nights → ~194/night
        # 120% threshold = ~233/night
        hotels = [
            _mock_hotel(name="Cheap", nightly_price_avg=150.0, score=0.9),
            _mock_hotel(name="Expensive", nightly_price_avg=300.0, score=0.95),
        ]
        state = _base_state()
        with patch(
            "travel_orchestrator.graph.nodes.search_hotels.search_hotels",
            new_callable=AsyncMock,
            return_value=hotels,
        ):
            result = await search_hotels_node(state)
        names = [h["name"] for h in result["hotel_options"]]
        assert "Cheap" in names
        assert "Expensive" not in names

    async def test_zero_budget_still_works(self) -> None:
        state = _base_state(budget={"total": 0.0, "currency": "EUR", "flexibility": 0.0})
        hotels = [_mock_hotel(nightly_price_avg=100.0)]
        with patch(
            "travel_orchestrator.graph.nodes.search_hotels.search_hotels",
            new_callable=AsyncMock,
            return_value=hotels,
        ):
            result = await search_hotels_node(state)
        # budget_per_night is 0, so the 1.2 * 0 = 0 check passes (condition skipped)
        assert len(result["hotel_options"]) == 1


# ===================================================================
# Star filtering based on profile
# ===================================================================


class TestStarFiltering:
    async def test_luxury_profile_requests_4_stars(self) -> None:
        state = _base_state(
            traveler_profile={
                "interests": ["shopping"],
                "pace": "slow",
                "group_size": 1,
                "accommodation_type": "luxury",
            }
        )
        with patch(
            "travel_orchestrator.graph.nodes.search_hotels.search_hotels",
            new_callable=AsyncMock,
            return_value=[],
        ) as mock_search:
            await search_hotels_node(state)
        _, kwargs = mock_search.call_args
        assert kwargs["min_stars"] == 4

    async def test_hotel_profile_requests_3_stars(self) -> None:
        state = _base_state(
            traveler_profile={
                "interests": ["culture"],
                "pace": "moderate",
                "group_size": 1,
                "accommodation_type": "hotel",
            }
        )
        with patch(
            "travel_orchestrator.graph.nodes.search_hotels.search_hotels",
            new_callable=AsyncMock,
            return_value=[],
        ) as mock_search:
            await search_hotels_node(state)
        _, kwargs = mock_search.call_args
        assert kwargs["min_stars"] == 3

    async def test_budget_profile_no_star_filter(self) -> None:
        state = _base_state(
            traveler_profile={
                "interests": ["adventure"],
                "pace": "fast",
                "group_size": 1,
                "accommodation_type": "budget",
            }
        )
        with patch(
            "travel_orchestrator.graph.nodes.search_hotels.search_hotels",
            new_callable=AsyncMock,
            return_value=[],
        ) as mock_search:
            await search_hotels_node(state)
        _, kwargs = mock_search.call_args
        assert kwargs["min_stars"] is None


# ===================================================================
# Location preference from pace
# ===================================================================


class TestLocationPreference:
    async def test_fast_pace_high_centrality(self) -> None:
        state = _base_state(
            traveler_profile={
                "interests": ["culture"],
                "pace": "fast",
                "group_size": 1,
                "accommodation_type": "hotel",
            }
        )
        with patch(
            "travel_orchestrator.graph.nodes.search_hotels.search_hotels",
            new_callable=AsyncMock,
            return_value=[],
        ) as mock_search:
            await search_hotels_node(state)
        _, kwargs = mock_search.call_args
        assert kwargs["location_centrality"] == 0.8

    async def test_slow_pace_low_centrality(self) -> None:
        state = _base_state(
            traveler_profile={
                "interests": ["wellness"],
                "pace": "slow",
                "group_size": 1,
                "accommodation_type": "hotel",
            }
        )
        with patch(
            "travel_orchestrator.graph.nodes.search_hotels.search_hotels",
            new_callable=AsyncMock,
            return_value=[],
        ) as mock_search:
            await search_hotels_node(state)
        _, kwargs = mock_search.call_args
        assert kwargs["location_centrality"] == 0.3


# ===================================================================
# Option selection & cost
# ===================================================================


class TestOptionSelectionAndCost:
    async def test_selects_best_hotel(self) -> None:
        hotels = _mock_hotels_list(count=3, base_nightly=100.0)
        state = _base_state()
        with patch(
            "travel_orchestrator.graph.nodes.search_hotels.search_hotels",
            new_callable=AsyncMock,
            return_value=hotels,
        ):
            result = await search_hotels_node(state)
        assert result["selected_hotel_id"] == "htl-000"
        assert result["hotel_options"][0]["name"] == "Hotel A"

    async def test_current_cost_updated(self) -> None:
        hotels = [_mock_hotel(nightly_price_avg=100.0)]
        state = _base_state(current_cost=500.0)  # e.g. from flight
        with patch(
            "travel_orchestrator.graph.nodes.search_hotels.search_hotels",
            new_callable=AsyncMock,
            return_value=hotels,
        ):
            result = await search_hotels_node(state)
        # 9 nights * 100/night = 900 + existing 500 = 1400
        assert result["current_cost"] == 1400.0

    async def test_max_5_options_kept(self) -> None:
        hotels = _mock_hotels_list(count=10, base_nightly=50.0)
        state = _base_state()
        with patch(
            "travel_orchestrator.graph.nodes.search_hotels.search_hotels",
            new_callable=AsyncMock,
            return_value=hotels,
        ):
            result = await search_hotels_node(state)
        assert len(result["hotel_options"]) <= _MAX_OPTIONS

    async def test_no_results_preserves_state(self) -> None:
        state = _base_state(selected_hotel_id=None, current_cost=200.0)
        with patch(
            "travel_orchestrator.graph.nodes.search_hotels.search_hotels",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await search_hotels_node(state)
        assert result["selected_hotel_id"] is None
        assert result["current_cost"] == 200.0
        assert result["hotel_options"] == []

    async def test_preserves_existing_state_fields(self) -> None:
        hotels = [_mock_hotel()]
        state = _base_state(plan_id="plan_keep_me", approval_status="pending")
        with patch(
            "travel_orchestrator.graph.nodes.search_hotels.search_hotels",
            new_callable=AsyncMock,
            return_value=hotels,
        ):
            result = await search_hotels_node(state)
        assert result["plan_id"] == "plan_keep_me"
        assert result["approval_status"] == "pending"


# ===================================================================
# Graceful degradation
# ===================================================================


class TestGracefulDegradation:
    async def test_continues_when_search_fails(self) -> None:
        state = _base_state()
        with patch(
            "travel_orchestrator.graph.nodes.search_hotels.search_hotels",
            new_callable=AsyncMock,
            side_effect=RuntimeError("upstream down"),
        ):
            result = await search_hotels_node(state)
        assert result["hotel_options"] == []
        assert result["selected_hotel_id"] is None
        assert result["current_cost"] == 0.0


# ===================================================================
# _to_hotel_option helper
# ===================================================================


class TestToHotelOption:
    def test_maps_all_fields(self) -> None:
        raw = _mock_hotel(
            name="Grand Test",
            stars=5,
            review_score=9.2,
            nightly_price_avg=250.0,
            currency="EUR",
            distance_to_center_km=0.5,
            amenities=["wifi", "pool", "spa"],
            score=0.95,
            area="Le Marais",
        )
        option = _to_hotel_option(raw, 0)
        assert option["id"] == "htl-000"
        assert option["name"] == "Grand Test"
        assert option["stars"] == 5
        assert option["price_per_night"] == 250.0
        assert option["currency"] == "EUR"
        assert option["reviews_score"] == 9.2
        assert option["distance_to_center_km"] == 0.5
        assert option["amenities"] == ["wifi", "pool", "spa"]
        assert option["score"] == 0.95
        assert option["address"] == "Le Marais"

    def test_handles_missing_fields(self) -> None:
        raw: dict[str, Any] = {"name": "Minimal", "score": 0.5}
        option = _to_hotel_option(raw, 7)
        assert option["id"] == "htl-007"
        assert option["name"] == "Minimal"
        assert option["stars"] == 0
        assert option["price_per_night"] == 0.0


# ===================================================================
# Constants sanity checks
# ===================================================================


class TestConstants:
    def test_budget_ratio(self) -> None:
        assert _HOTEL_BUDGET_RATIO == 0.35

    def test_max_options(self) -> None:
        assert _MAX_OPTIONS == 5

    def test_luxury_min_stars(self) -> None:
        assert _ACCOMMODATION_MIN_STARS["luxury"] == 4

    def test_pace_centrality_values(self) -> None:
        assert _PACE_CENTRALITY["fast"] > _PACE_CENTRALITY["slow"]


# ===================================================================
# Graph integration
# ===================================================================


class TestGraphIntegration:
    async def test_node_runs_inside_graph(self) -> None:
        """Verify the real node works when invoked via the compiled graph."""
        from travel_orchestrator.graph.planner_graph import compile_graph

        compiled = compile_graph()
        initial_state = _base_state()
        config = {"configurable": {"thread_id": "test-search-hotels"}}
        result = await compiled.ainvoke(initial_state, config=config)

        # search_hotels should have run and produced options
        assert "hotel_options" in result
        assert isinstance(result["hotel_options"], list)

    async def test_mock_provider_returns_hotels_for_paris(self) -> None:
        """End-to-end with mock provider (no Enuygun)."""
        from travel_orchestrator.graph.planner_graph import compile_graph

        compiled = compile_graph()
        initial_state = _base_state(destination="Paris")
        config = {"configurable": {"thread_id": "test-search-hotels-paris"}}
        result = await compiled.ainvoke(initial_state, config=config)

        options = result.get("hotel_options", [])
        assert len(options) > 0
        assert result["selected_hotel_id"] is not None
        assert result["current_cost"] > 0.0
