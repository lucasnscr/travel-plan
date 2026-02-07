"""WebSocket endpoint for real-time orchestrator observability.

Broadcasts node transitions, MCP tool calls, and state snapshots
to connected frontend clients.  Includes a demo simulation mode
for presentations.
"""

from __future__ import annotations

import asyncio
import json
import random
import time
import uuid
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

from travel_orchestrator.utils.logging import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Connected clients
# ---------------------------------------------------------------------------

_clients: set[WebSocket] = set()

# ---------------------------------------------------------------------------
# WebSocket handler
# ---------------------------------------------------------------------------


async def orchestrator_ws(websocket: WebSocket) -> None:
    """Handle a WebSocket connection for orchestrator events."""
    await websocket.accept()
    _clients.add(websocket)
    logger.info("ws_client_connected", total_clients=len(_clients))

    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
            except json.JSONDecodeError:
                continue

            action = msg.get("action")
            if action == "start_demo":
                asyncio.create_task(_run_demo_simulation())
    except WebSocketDisconnect:
        _clients.discard(websocket)
        logger.info("ws_client_disconnected", total_clients=len(_clients))


# ---------------------------------------------------------------------------
# Broadcast helper
# ---------------------------------------------------------------------------


async def broadcast(event: dict[str, Any]) -> None:
    """Broadcast an event to all connected WebSocket clients."""
    if not _clients:
        return

    payload = json.dumps(event, default=str)
    disconnected: set[WebSocket] = set()

    for ws in _clients:
        try:
            await ws.send_text(payload)
        except Exception:  # noqa: BLE001
            disconnected.add(ws)

    _clients -= disconnected


# ---------------------------------------------------------------------------
# Convenience emitters for use from graph nodes
# ---------------------------------------------------------------------------


async def emit_node_status(node: str, status: str) -> None:
    """Emit a node status transition event."""
    await broadcast({
        "type": "node_status",
        "payload": {
            "node": node,
            "status": status,
            "timestamp": int(time.time() * 1000),
        },
    })


async def emit_tool_call(
    *,
    node: str,
    tool: str,
    server: str,
    params: dict[str, Any],
    result: Any = None,
    status: str = "success",
    duration_ms: float | None = None,
    error: str | None = None,
) -> None:
    """Emit a tool call event."""
    await broadcast({
        "type": "tool_call",
        "payload": {
            "id": f"tc-{uuid.uuid4().hex[:8]}",
            "node": node,
            "tool": tool,
            "server": server,
            "params": params,
            "result": result,
            "status": status,
            "error": error,
            "startedAt": int(time.time() * 1000),
            "duration_ms": duration_ms,
        },
    })


async def emit_state_update(
    node: str,
    state: dict[str, Any],
    changed_keys: list[str],
) -> None:
    """Emit a state snapshot after a node completes."""
    await broadcast({
        "type": "state_update",
        "payload": {
            "node": node,
            "timestamp": int(time.time() * 1000),
            "state": state,
            "changedKeys": changed_keys,
        },
    })


async def emit_agent_log(
    *,
    node: str,
    log_type: str,
    message: str,
    duration_ms: float | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Emit an agent activity log entry."""
    await broadcast({
        "type": "agent_log",
        "payload": {
            "id": f"log-{uuid.uuid4().hex[:8]}",
            "node": node,
            "type": log_type,
            "message": message,
            "timestamp": int(time.time() * 1000),
            "duration_ms": duration_ms,
            "metadata": metadata,
        },
    })


# ---------------------------------------------------------------------------
# Demo simulation
# ---------------------------------------------------------------------------

_PIPELINE = [
    "gather_requirements",
    "analyze_destination",
    "search_flights",
    "search_hotels",
    "search_activities",
    "optimize_itinerary",
    "calculate_budget",
    "risk_and_policy_check",
    "present_for_approval",
    "book_services",
    "generate_documents",
]

_DEMO_TOOLS: dict[str, list[dict[str, Any]]] = {
    "analyze_destination": [
        {
            "tool": "get_weather",
            "server": "weather-mcp",
            "params": {"destination": "Tokyo", "start_date": "2026-04-01", "end_date": "2026-04-05"},
            "result": {"forecast": [{"date": "2026-04-01", "temp_max": 18, "condition": "partly_cloudy"}]},
        },
    ],
    "search_flights": [
        {
            "tool": "search_flights",
            "server": "flights-mcp",
            "params": {"origin": "GRU", "destination": "NRT", "date": "2026-04-01", "passengers": 2},
            "result": {"flights": [{"airline": "ANA", "price": 1200, "duration": "14h30m"}]},
        },
    ],
    "search_hotels": [
        {
            "tool": "search_hotels",
            "server": "hotels-mcp",
            "params": {"destination": "Tokyo", "checkin": "2026-04-01", "checkout": "2026-04-05", "guests": 2},
            "result": {"hotels": [{"name": "Tokyo Garden Hotel", "price": 180}, {"name": "Shinjuku Grand", "price": 220}]},
        },
    ],
    "search_activities": [
        {
            "tool": "discover_activities",
            "server": "activities-mcp",
            "params": {"destination": "Tokyo", "interests": ["culture", "gastronomy"]},
            "result": {"activities": [{"name": "Senso-ji Temple"}, {"name": "Tsukiji Market Tour"}]},
        },
        {
            "tool": "text_search",
            "server": "activities-mcp",
            "params": {"query": "temples in Tokyo"},
            "result": {"places": [{"name": "Meiji Shrine"}, {"name": "Senso-ji"}]},
        },
    ],
}

_STATE_CHANGES: dict[str, list[str]] = {
    "gather_requirements": ["destination", "dates", "budget", "traveler_profile"],
    "analyze_destination": ["destination_analysis"],
    "search_hotels": ["hotel_options"],
    "search_activities": ["activity_options"],
    "optimize_itinerary": ["optimized_itinerary"],
    "calculate_budget": ["current_cost"],
    "present_for_approval": ["approval_status"],
}


async def _run_demo_simulation() -> None:
    """Run a simulated pipeline emitting realistic events."""
    logger.info("demo_simulation_started")

    for node in _PIPELINE:
        # Node started
        await emit_node_status(node, "running")
        await emit_agent_log(node=node, log_type="node_started", message=f"Starting {node.replace('_', ' ')}")

        # Tool calls for this node
        tools = _DEMO_TOOLS.get(node, [])
        for tool_def in tools:
            await emit_agent_log(
                node=node,
                log_type="tool_call",
                message=f"Calling {tool_def['tool']} on {tool_def['server']}",
            )
            tool_duration = 200 + random.random() * 600  # noqa: S311
            await asyncio.sleep(tool_duration / 1000)
            await emit_tool_call(
                node=node,
                tool=tool_def["tool"],
                server=tool_def["server"],
                params=tool_def["params"],
                result=tool_def.get("result"),
                status="success",
                duration_ms=round(tool_duration, 1),
            )

        # Simulate processing time
        duration = 0.8 + random.random() * 1.2  # noqa: S311
        await asyncio.sleep(duration)

        # Node completed
        await emit_node_status(node, "completed")
        await emit_agent_log(
            node=node,
            log_type="node_completed",
            message=f"Completed {node.replace('_', ' ')}",
            duration_ms=round(duration * 1000, 1),
        )

        # State snapshot
        changed = _STATE_CHANGES.get(node)
        if changed:
            await emit_state_update(node, _build_demo_state(node), changed)
            await emit_agent_log(
                node=node,
                log_type="state_update",
                message=f"State updated: {', '.join(changed)}",
            )

        # Brief pause between nodes
        await asyncio.sleep(0.2)

    logger.info("demo_simulation_completed")


def _build_demo_state(after_node: str) -> dict[str, Any]:
    """Build a mock state snapshot for the demo."""
    state: dict[str, Any] = {
        "plan_id": "plan_demo_001",
        "destination": "Tokyo",
        "dates": {"start_date": "2026-04-01", "end_date": "2026-04-05"},
        "budget": {"total": 5000, "currency": "USD", "flexibility": 0.1},
        "traveler_profile": {"interests": ["culture", "gastronomy"], "pace": "moderate", "group_size": 2},
        "revision_count": 0,
        "approval_status": "pending",
        "risk_flags": [],
    }

    idx = _PIPELINE.index(after_node) if after_node in _PIPELINE else -1

    if idx >= 1:
        state["destination_analysis"] = {
            "forecast": [
                {"date": "2026-04-01", "temp_max": 18, "temp_min": 10, "condition": "partly_cloudy"},
                {"date": "2026-04-02", "temp_max": 20, "temp_min": 12, "condition": "sunny"},
            ],
            "events": ["Cherry Blossom Festival"],
        }
    if idx >= 3:
        state["hotel_options"] = [
            {"id": "h1", "name": "Tokyo Garden Hotel", "score": 87, "nightly_price_avg": 180},
            {"id": "h2", "name": "Shinjuku Grand", "score": 92, "nightly_price_avg": 220},
        ]
    if idx >= 4:
        state["activity_options"] = [
            {"id": "a1", "name": "Senso-ji Temple", "category": "culture", "price": 0},
            {"id": "a2", "name": "Tsukiji Market Tour", "category": "gastronomy", "price": 45},
        ]
    if idx >= 5:
        state["optimized_itinerary"] = {
            "days": [
                {"day": 1, "activities": ["Senso-ji Temple", "Tsukiji Market Tour"]},
                {"day": 2, "activities": ["Meiji Shrine", "Harajuku Walk"]},
            ]
        }
    if idx >= 6:
        state["current_cost"] = 2850

    return state
