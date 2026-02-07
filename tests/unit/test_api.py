"""Unit tests for the new API layer (api/main.py, schemas, ws_manager, callbacks)."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.testclient import TestClient

from travel_orchestrator.api.main import app, _trips, _state_to_trip_plan
from travel_orchestrator.api.schemas import (
    ApprovalRequest,
    ChatMessage,
    Coordinates,
    DayPlan,
    HotelSchema,
    ItineraryUpdate,
    OrchestratorEventSchema,
    PlanRequest,
    TripPlan,
    WeatherSummarySchema,
)
from travel_orchestrator.api.ws_manager import ConnectionManager
from travel_orchestrator.api.callbacks import OrchestratorCallbacks


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_state(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "plan_id": "plan_test_001",
        "destination": "Tokyo",
        "dates": {"start_date": "2026-04-01", "end_date": "2026-04-05"},
        "budget": {"total": 5000, "currency": "USD", "flexibility": 0.1},
        "traveler_profile": {"interests": ["culture"], "pace": "moderate", "group_size": 2},
        "current_cost": 2000.0,
        "approval_status": "pending",
        "risk_flags": [],
        "hotel_options": [
            {
                "id": "h1",
                "name": "Test Hotel",
                "address": "123 St",
                "coordinates": {"lat": 35.6, "lng": 139.7},
                "stars": 4,
                "price_per_night": 150,
                "currency": "USD",
                "amenities": ["wifi"],
                "reviews_score": 8.5,
                "distance_to_center_km": 2.0,
                "score": 85,
            },
        ],
        "activity_options": [
            {
                "id": "a1",
                "name": "Temple Visit",
                "category": "culture",
                "address": "456 Ave",
                "coordinates": {"lat": 35.7, "lng": 139.8},
                "duration_minutes": 90,
                "price": 0,
                "currency": "USD",
                "opening_hours": {},
                "requires_booking": False,
                "indoor": False,
                "description": "Beautiful temple",
                "score": 90,
            },
        ],
        "optimized_itinerary": {
            "days": [
                {"date": "2026-04-01", "day_number": 1, "theme": "Culture Day"},
            ]
        },
        "destination_analysis": {
            "weather_summary": {
                "avg_temp_max": 20,
                "avg_temp_min": 10,
                "dominant_condition": "sunny",
                "packing_suggestions": ["light jacket"],
            }
        },
    }
    base.update(overrides)
    return base


# ===================================================================
# TestSchemas
# ===================================================================


class TestSchemas:
    def test_plan_request_defaults(self) -> None:
        req = PlanRequest(destination="Paris", start_date="2026-07-01", end_date="2026-07-08")
        assert req.budget == 5000.0
        assert req.currency == "USD"
        assert req.num_travelers == 2
        assert req.preferences == []

    def test_trip_plan_defaults(self) -> None:
        tp = TripPlan()
        assert tp.plan_id == ""
        assert tp.days == []
        assert tp.hotels == []
        assert tp.approval_status == "pending"

    def test_hotel_schema_from_dict(self) -> None:
        h = HotelSchema(
            id="h1", name="Test", address="123 St", stars=4,
            price_per_night=200, currency="USD", reviews_score=8.5,
            score=85, coordinates=Coordinates(lat=35.6, lng=139.7),
        )
        assert h.name == "Test"
        assert h.coordinates is not None
        assert h.coordinates.lat == 35.6

    def test_day_plan_defaults(self) -> None:
        dp = DayPlan()
        assert dp.activities == []
        assert dp.hotel is None

    def test_approval_request_literal(self) -> None:
        ar = ApprovalRequest(decision="approved")
        assert ar.decision == "approved"
        assert ar.feedback == ""

    def test_chat_message(self) -> None:
        msg = ChatMessage(role="assistant", content="Hello", timestamp=123)
        assert msg.role == "assistant"
        assert msg.rich_content is None

    def test_orchestrator_event(self) -> None:
        evt = OrchestratorEventSchema(node="search_hotels", action="node_started", status="running")
        assert evt.latency is None
        assert evt.data == {}

    def test_itinerary_update(self) -> None:
        iu = ItineraryUpdate(days=[DayPlan(date="2026-04-01", day_number=1)])
        assert len(iu.days) == 1

    def test_weather_summary(self) -> None:
        ws = WeatherSummarySchema(avg_temp_max=25, avg_temp_min=15, dominant_condition="sunny")
        assert ws.packing_suggestions == []


# ===================================================================
# TestConnectionManager
# ===================================================================


class TestConnectionManager:
    def test_initial_state(self) -> None:
        mgr = ConnectionManager()
        assert mgr.client_count("orchestrator") == 0
        assert mgr.client_count("nonexistent") == 0

    @pytest.mark.asyncio
    async def test_broadcast_no_clients(self) -> None:
        mgr = ConnectionManager()
        # Should not raise
        await mgr.broadcast("orchestrator", {"type": "test"})


# ===================================================================
# TestOrchestratorCallbacks
# ===================================================================


class TestOrchestratorCallbacks:
    @pytest.mark.asyncio
    async def test_on_node_start(self) -> None:
        mgr = ConnectionManager()
        mgr.broadcast = AsyncMock()  # type: ignore[assignment]
        cb = OrchestratorCallbacks(mgr)

        await cb.on_node_start("search_hotels")

        assert mgr.broadcast.call_count == 2
        # First call: node_status
        first_call = mgr.broadcast.call_args_list[0]
        assert first_call[0][0] == "orchestrator"
        assert first_call[0][1]["type"] == "node_status"
        assert first_call[0][1]["payload"]["status"] == "running"
        # Second call: agent_log
        second_call = mgr.broadcast.call_args_list[1]
        assert second_call[0][1]["type"] == "agent_log"
        assert second_call[0][1]["payload"]["type"] == "node_started"

    @pytest.mark.asyncio
    async def test_on_node_end(self) -> None:
        mgr = ConnectionManager()
        mgr.broadcast = AsyncMock()  # type: ignore[assignment]
        cb = OrchestratorCallbacks(mgr)

        await cb.on_node_end("search_hotels", duration_ms=500)

        assert mgr.broadcast.call_count == 2
        first_call = mgr.broadcast.call_args_list[0]
        assert first_call[0][1]["payload"]["status"] == "completed"

    @pytest.mark.asyncio
    async def test_on_tool_call(self) -> None:
        mgr = ConnectionManager()
        mgr.broadcast = AsyncMock()  # type: ignore[assignment]
        cb = OrchestratorCallbacks(mgr)

        await cb.on_tool_call(
            node="search_hotels",
            tool_name="search_hotels",
            server="hotels-mcp",
            input_params={"destination": "Tokyo"},
            latency_ms=250,
        )

        assert mgr.broadcast.call_count == 2
        tc_call = mgr.broadcast.call_args_list[0]
        assert tc_call[0][1]["type"] == "tool_call"
        assert tc_call[0][1]["payload"]["tool"] == "search_hotels"

    @pytest.mark.asyncio
    async def test_on_state_update(self) -> None:
        mgr = ConnectionManager()
        mgr.broadcast = AsyncMock()  # type: ignore[assignment]
        cb = OrchestratorCallbacks(mgr)

        await cb.on_state_update("search_hotels", {"key": "val"}, ["key"])

        assert mgr.broadcast.call_count == 2
        state_call = mgr.broadcast.call_args_list[0]
        assert state_call[0][1]["type"] == "state_update"
        assert state_call[0][1]["payload"]["changedKeys"] == ["key"]

    @pytest.mark.asyncio
    async def test_on_hitl_required(self) -> None:
        mgr = ConnectionManager()
        mgr.broadcast = AsyncMock()  # type: ignore[assignment]
        cb = OrchestratorCallbacks(mgr)

        await cb.on_hitl_required("plan_001")

        mgr.broadcast.assert_called_once()
        call = mgr.broadcast.call_args_list[0]
        payload = call[0][1]["payload"]
        assert "human approval" in payload["message"]


# ===================================================================
# TestStateToTripPlan
# ===================================================================


class TestStateToTripPlan:
    def test_basic_conversion(self) -> None:
        state = _make_state()
        result = _state_to_trip_plan(state, map_url="/api/map/test.html")

        assert result["plan_id"] == "plan_test_001"
        assert result["destination"] == "Tokyo"
        assert result["total_cost"] == 2000.0
        assert len(result["hotels"]) == 1
        assert result["hotels"][0]["name"] == "Test Hotel"
        assert len(result["activities"]) == 1
        assert result["activities"][0]["name"] == "Temple Visit"
        assert len(result["days"]) == 1
        assert result["weather_summary"]["dominant_condition"] == "sunny"
        assert result["map_url"] == "/api/map/test.html"

    def test_empty_state(self) -> None:
        state = {"plan_id": "empty", "dates": {}, "budget": {}}
        result = _state_to_trip_plan(state)

        assert result["plan_id"] == "empty"
        assert result["hotels"] == []
        assert result["activities"] == []
        assert result["days"] == []
        assert result["weather_summary"] is None

    def test_hotel_price_fallback(self) -> None:
        state = _make_state()
        # Use nightly_price_avg instead of price_per_night
        state["hotel_options"] = [
            {"id": "h2", "name": "Budget Hotel", "nightly_price_avg": 100},
        ]
        result = _state_to_trip_plan(state)
        assert result["hotels"][0]["price_per_night"] == 100


# ===================================================================
# TestHealthEndpoint
# ===================================================================


class TestHealthEndpoint:
    def test_health(self) -> None:
        client = TestClient(app)
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "healthy"}


# ===================================================================
# TestTripCRUD
# ===================================================================


class TestTripCRUD:
    def setup_method(self) -> None:
        _trips.clear()

    def test_get_trip_not_found(self) -> None:
        client = TestClient(app)
        resp = client.get("/api/trip/nonexistent")
        assert resp.status_code == 404

    def test_get_trip_found(self) -> None:
        _trips["plan_001"] = {"plan_id": "plan_001", "destination": "Tokyo"}
        client = TestClient(app)
        resp = client.get("/api/trip/plan_001")
        assert resp.status_code == 200
        assert resp.json()["destination"] == "Tokyo"

    def test_update_itinerary(self) -> None:
        _trips["plan_001"] = {"plan_id": "plan_001", "days": []}
        client = TestClient(app)
        resp = client.patch(
            "/api/trip/plan_001/itinerary",
            json={"days": [{"date": "2026-04-01", "day_number": 1}]},
        )
        assert resp.status_code == 200
        assert len(resp.json()["days"]) == 1

    def test_update_itinerary_not_found(self) -> None:
        client = TestClient(app)
        resp = client.patch(
            "/api/trip/nonexistent/itinerary",
            json={"days": []},
        )
        assert resp.status_code == 404

    def test_approve_trip(self) -> None:
        import travel_orchestrator.frontend.app as app_mod

        app_mod._last_result_state = _make_state()
        _trips["plan_test_001"] = {"plan_id": "plan_test_001", "approval_status": "pending"}

        client = TestClient(app)
        resp = client.post(
            "/api/trip/plan_test_001/approve",
            json={"decision": "approved", "feedback": ""},
        )
        assert resp.status_code == 200
        assert "approved" in resp.json()["message"]
        assert _trips["plan_test_001"]["approval_status"] == "approved"

    def test_approve_legacy_form(self) -> None:
        import travel_orchestrator.frontend.app as app_mod

        app_mod._last_result_state = _make_state()

        client = TestClient(app)
        resp = client.post(
            "/api/approve",
            data={"decision": "rejected", "feedback": "Too expensive"},
        )
        assert resp.status_code == 200
        assert "rejected" in resp.json()["message"]


# ===================================================================
# TestMapAndPdf
# ===================================================================


class TestMapAndPdf:
    def test_map_not_found(self) -> None:
        client = TestClient(app)
        resp = client.get("/api/map/nonexistent.html")
        assert resp.status_code == 404

    def test_pdf_not_found(self) -> None:
        client = TestClient(app)
        resp = client.get("/api/pdf/nonexistent.pdf")
        assert resp.status_code == 404


# ===================================================================
# TestWebSocketOrchestrator
# ===================================================================


class TestWebSocketOrchestrator:
    def test_connect_and_receive(self) -> None:
        client = TestClient(app)
        with client.websocket_connect("/ws/orchestrator") as ws:
            # Just connect and disconnect — no crash
            ws.close()

    def test_malformed_json_ignored(self) -> None:
        client = TestClient(app)
        with client.websocket_connect("/ws/orchestrator") as ws:
            ws.send_text("not json")
            ws.close()


# ===================================================================
# TestWebSocketChat
# ===================================================================


class TestWebSocketChat:
    def test_connect(self) -> None:
        client = TestClient(app)
        with client.websocket_connect("/ws/chat") as ws:
            ws.close()

    def test_empty_content_ignored(self) -> None:
        client = TestClient(app)
        with client.websocket_connect("/ws/chat") as ws:
            ws.send_json({"content": ""})
            ws.close()
