"""Unit tests for the frontend application."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from travel_orchestrator.frontend.app import (
    _build_initial_state,
    _empty_state,
    handle_approval,
    plan_trip,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_audio_file(tmp_path: Any) -> str:
    f = tmp_path / "voice.mp3"
    f.write_bytes(b"\x00" * 1024)
    return str(f)


def _make_image_file(tmp_path: Any) -> str:
    f = tmp_path / "photo.jpg"
    f.write_bytes(b"\x00" * 1024)
    return str(f)


def _make_pdf_file(tmp_path: Any) -> str:
    f = tmp_path / "offer.pdf"
    f.write_bytes(b"%PDF-1.4\n" + b"\x00" * 1024)
    return str(f)


def _make_audio_state(**overrides: Any) -> dict[str, Any]:
    base = _empty_state()
    base["destination"] = "Paris"
    base["dates"] = {"start_date": "2026-07-01", "end_date": "2026-07-08"}
    base["budget"] = {"total": 5000.0, "currency": "EUR", "flexibility": 0.1}
    base["traveler_profile"] = {
        "interests": ["museum", "gastronomy"],
        "pace": "moderate",
        "group_size": 2,
    }
    base.update(overrides)
    return base


def _make_image_vibe(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "destination_suggestions": ["Barcelona", "Madrid"],
        "vibe_tags": ["sunny", "vibrant"],
        "budget_tier_guess": "mid",
        "season_preference": "summer",
        "activity_bias": ["beach", "food"],
    }
    base.update(overrides)
    return base


def _make_competitor_data(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "destination": "Lisboa",
        "price": 4500.0,
        "currency": "BRL",
        "duration_days": 7,
        "highlights": ["Sintra", "Fado"],
        "hotel_name": "Hotel Avenida",
        "raw_text": "(mock)",
    }
    base.update(overrides)
    return base


# ===================================================================
# TestEmptyState
# ===================================================================


class TestEmptyState:
    def test_has_all_17_keys(self) -> None:
        state = _empty_state()
        expected_keys = {
            "plan_id", "destination", "dates", "budget", "traveler_profile",
            "selected_flight_id", "selected_hotel_id", "selected_activity_ids",
            "current_cost", "revision_count", "approval_status", "risk_flags",
            "alternative_plans", "destination_analysis", "hotel_options",
            "activity_options", "optimized_itinerary",
        }
        assert expected_keys == set(state.keys())

    def test_default_values(self) -> None:
        state = _empty_state()
        assert state["plan_id"] == ""
        assert state["destination"] == ""
        assert state["current_cost"] == 0.0
        assert state["approval_status"] == "pending"
        assert state["risk_flags"] == []
        assert state["selected_flight_id"] is None
        assert state["optimized_itinerary"] is None


# ===================================================================
# TestBuildInitialState
# ===================================================================


class TestBuildInitialState:
    def test_minimal_text_inputs(self) -> None:
        state = _build_initial_state(
            destination="Paris",
            start_date="2026-07-01",
            end_date="2026-07-08",
            budget_total=5000.0,
            currency="EUR",
            group_size=2,
            interests=["museum"],
        )
        assert state["destination"] == "Paris"
        assert state["dates"]["start_date"] == "2026-07-01"
        assert state["budget"]["total"] == 5000.0
        assert state["budget"]["currency"] == "EUR"
        assert state["traveler_profile"]["interests"] == ["museum"]
        assert state["traveler_profile"]["group_size"] == 2
        assert state["plan_id"].startswith("plan_")

    def test_audio_state_merge(self) -> None:
        audio = _make_audio_state(destination="Tokyo")
        state = _build_initial_state(
            destination="",
            start_date="2026-08-01",
            end_date="2026-08-10",
            budget_total=8000.0,
            currency="USD",
            group_size=4,
            interests=["temples"],
            audio_state=audio,
        )
        # Audio destination preserved when text is empty
        assert state["destination"] == "Tokyo"
        # Budget comes from text inputs (overrides audio)
        assert state["budget"]["total"] == 8000.0

    def test_image_vibe_enriches_interests(self) -> None:
        vibe = _make_image_vibe(activity_bias=["beach", "diving"])
        state = _build_initial_state(
            destination="Bali",
            start_date="2026-07-01",
            end_date="2026-07-08",
            budget_total=3000.0,
            currency="USD",
            group_size=2,
            interests=["beach", "nature"],
            image_vibe=vibe,
        )
        # "beach" already exists, "diving" is added
        assert "beach" in state["traveler_profile"]["interests"]
        assert "diving" in state["traveler_profile"]["interests"]
        assert "nature" in state["traveler_profile"]["interests"]

    def test_image_vibe_destination_fallback(self) -> None:
        vibe = _make_image_vibe(destination_suggestions=["Barcelona", "Madrid"])
        state = _build_initial_state(
            destination="",
            start_date="2026-07-01",
            end_date="2026-07-08",
            budget_total=3000.0,
            currency="EUR",
            group_size=2,
            interests=[],
            image_vibe=vibe,
        )
        assert state["destination"] == "Barcelona"

    def test_competitor_data_in_alternative_plans(self) -> None:
        competitor = _make_competitor_data()
        state = _build_initial_state(
            destination="Lisboa",
            start_date="2026-09-01",
            end_date="2026-09-08",
            budget_total=5000.0,
            currency="BRL",
            group_size=2,
            interests=["culture"],
            competitor_data=competitor,
        )
        assert "competitor_offer" in state["alternative_plans"]
        assert state["alternative_plans"]["competitor_offer"]["destination"] == "Lisboa"

    def test_text_overrides_audio(self) -> None:
        audio = _make_audio_state(destination="Tokyo")
        state = _build_initial_state(
            destination="Paris",
            start_date="2026-07-01",
            end_date="2026-07-08",
            budget_total=5000.0,
            currency="EUR",
            group_size=2,
            interests=["museum"],
            audio_state=audio,
        )
        # Text destination overrides audio destination
        assert state["destination"] == "Paris"


# ===================================================================
# TestPlanTrip
# ===================================================================


class TestPlanTrip:
    @pytest.mark.asyncio
    async def test_graph_success(self) -> None:
        mock_result = _empty_state()
        mock_result["destination"] = "Paris"
        mock_result["plan_id"] = "plan_test123"

        mock_graph = AsyncMock()
        mock_graph.ainvoke = AsyncMock(return_value=mock_result)

        mock_progress = MagicMock()

        with patch(
            "travel_orchestrator.graph.planner_graph.compile_graph",
            return_value=mock_graph,
        ), patch(
            "travel_orchestrator.frontend.app.generate_map_from_state",
            return_value="",
        ), patch(
            "travel_orchestrator.frontend.app.generate_pdf_from_state",
            return_value="",
        ):
            plan_json, map_html, pdf_path = await plan_trip(
                "Paris", "2026-07-01", "2026-07-08",
                5000.0, "EUR", 2, "museum",
                None, None, None,
                mock_progress,
            )

        data = json.loads(plan_json)
        assert data["destination"] == "Paris"

    @pytest.mark.asyncio
    async def test_graph_failure_returns_state_with_error(self) -> None:
        mock_progress = MagicMock()

        with patch(
            "travel_orchestrator.graph.planner_graph.compile_graph",
            side_effect=Exception("No API key"),
        ), patch(
            "travel_orchestrator.frontend.app.generate_map_from_state",
            return_value="",
        ), patch(
            "travel_orchestrator.frontend.app.generate_pdf_from_state",
            return_value="",
        ):
            plan_json, _, _ = await plan_trip(
                "Paris", "2026-07-01", "2026-07-08",
                5000.0, "EUR", 2, "museum",
                None, None, None,
                mock_progress,
            )

        data = json.loads(plan_json)
        assert data["destination"] == "Paris"
        assert any("graph_error" in f for f in data["risk_flags"])

    @pytest.mark.asyncio
    async def test_audio_failure_non_fatal(self, tmp_path: Any) -> None:
        audio_path = _make_audio_file(tmp_path)
        mock_progress = MagicMock()

        with patch(
            "travel_orchestrator.frontend.app.populate_state_from_audio",
            side_effect=Exception("Audio error"),
        ), patch(
            "travel_orchestrator.graph.planner_graph.compile_graph",
            side_effect=Exception("No API key"),
        ), patch(
            "travel_orchestrator.frontend.app.generate_map_from_state",
            return_value="",
        ), patch(
            "travel_orchestrator.frontend.app.generate_pdf_from_state",
            return_value="",
        ):
            plan_json, _, _ = await plan_trip(
                "Paris", "2026-07-01", "2026-07-08",
                5000.0, "EUR", 2, "museum",
                audio_path, None, None,
                mock_progress,
            )

        # Should still return a valid plan despite audio error
        data = json.loads(plan_json)
        assert data["destination"] == "Paris"

    @pytest.mark.asyncio
    async def test_image_failure_non_fatal(self, tmp_path: Any) -> None:
        image_path = _make_image_file(tmp_path)
        mock_progress = MagicMock()

        with patch(
            "travel_orchestrator.frontend.app.analyze_inspiration_image",
            side_effect=Exception("Image error"),
        ), patch(
            "travel_orchestrator.graph.planner_graph.compile_graph",
            side_effect=Exception("No API key"),
        ), patch(
            "travel_orchestrator.frontend.app.generate_map_from_state",
            return_value="",
        ), patch(
            "travel_orchestrator.frontend.app.generate_pdf_from_state",
            return_value="",
        ):
            plan_json, _, _ = await plan_trip(
                "Paris", "2026-07-01", "2026-07-08",
                5000.0, "EUR", 2, "museum",
                None, image_path, None,
                mock_progress,
            )

        data = json.loads(plan_json)
        assert data["destination"] == "Paris"

    @pytest.mark.asyncio
    async def test_pdf_failure_non_fatal(self, tmp_path: Any) -> None:
        pdf_path = _make_pdf_file(tmp_path)
        mock_progress = MagicMock()

        with patch(
            "travel_orchestrator.frontend.app.parse_competitor_offer_pdf",
            side_effect=Exception("PDF error"),
        ), patch(
            "travel_orchestrator.graph.planner_graph.compile_graph",
            side_effect=Exception("No API key"),
        ), patch(
            "travel_orchestrator.frontend.app.generate_map_from_state",
            return_value="",
        ), patch(
            "travel_orchestrator.frontend.app.generate_pdf_from_state",
            return_value="",
        ):
            plan_json, _, _ = await plan_trip(
                "Paris", "2026-07-01", "2026-07-08",
                5000.0, "EUR", 2, "museum",
                None, None, pdf_path,
                mock_progress,
            )

        data = json.loads(plan_json)
        assert data["destination"] == "Paris"


# ===================================================================
# TestHandleApproval
# ===================================================================


class TestHandleApproval:
    @pytest.mark.asyncio
    async def test_approve(self) -> None:
        import travel_orchestrator.frontend.app as app_mod

        app_mod._last_result_state = _make_audio_state()

        result = await handle_approval("approved", "")
        assert "approved" in result
        assert app_mod._last_result_state["approval_status"] == "approved"

    @pytest.mark.asyncio
    async def test_reject_with_feedback(self) -> None:
        import travel_orchestrator.frontend.app as app_mod

        app_mod._last_result_state = _make_audio_state()

        result = await handle_approval("rejected", "Hotel too expensive")
        assert "rejected" in result
        assert "Hotel too expensive" in result
        assert app_mod._last_result_state["approval_status"] == "rejected"
        assert any(
            "feedback: Hotel too expensive" in f
            for f in app_mod._last_result_state["risk_flags"]
        )

    @pytest.mark.asyncio
    async def test_no_plan_returns_message(self) -> None:
        import travel_orchestrator.frontend.app as app_mod

        app_mod._last_result_state = {}

        result = await handle_approval("approved", "")
        assert "No plan" in result


# ===================================================================
# TestServer
# ===================================================================


class TestServer:
    def test_app_is_fastapi(self) -> None:
        from fastapi import FastAPI

        from travel_orchestrator.frontend.server import app

        assert isinstance(app, FastAPI)

    def test_health_endpoint(self) -> None:
        from starlette.testclient import TestClient

        from travel_orchestrator.frontend.server import app

        client = TestClient(app)
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"
