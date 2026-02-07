"""LangGraph callbacks that emit real-time events via WebSocket.

An ``OrchestratorCallbacks`` instance is passed into the planning
pipeline so that each graph node can broadcast its progress to
connected frontend clients through the :mod:`ws_manager`.
"""

from __future__ import annotations

import time
import uuid
from typing import Any

from travel_orchestrator.api.ws_manager import ConnectionManager


class OrchestratorCallbacks:
    """Emits orchestrator events through the WebSocket manager."""

    CHANNEL = "orchestrator"

    def __init__(self, manager: ConnectionManager) -> None:
        self.manager = manager
        self._counter = 0

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _next_id(self, prefix: str = "evt") -> str:
        self._counter += 1
        return f"{prefix}-{uuid.uuid4().hex[:8]}"

    @staticmethod
    def _ts() -> int:
        return int(time.time() * 1000)

    # ------------------------------------------------------------------
    # Node lifecycle
    # ------------------------------------------------------------------

    async def on_node_start(self, node_name: str) -> None:
        """Broadcast node_status=running and an agent_log entry."""
        ts = self._ts()

        await self.manager.broadcast(self.CHANNEL, {
            "type": "node_status",
            "payload": {"node": node_name, "status": "running", "timestamp": ts},
        })

        await self.manager.broadcast(self.CHANNEL, {
            "type": "agent_log",
            "payload": {
                "id": self._next_id("log"),
                "node": node_name,
                "type": "node_started",
                "message": f"Starting {node_name.replace('_', ' ')}",
                "timestamp": ts,
            },
        })

    async def on_node_end(
        self,
        node_name: str,
        result: dict[str, Any] | None = None,
        duration_ms: float = 0.0,
    ) -> None:
        """Broadcast node_status=completed, agent_log, and optional state."""
        ts = self._ts()

        await self.manager.broadcast(self.CHANNEL, {
            "type": "node_status",
            "payload": {"node": node_name, "status": "completed", "timestamp": ts},
        })

        await self.manager.broadcast(self.CHANNEL, {
            "type": "agent_log",
            "payload": {
                "id": self._next_id("log"),
                "node": node_name,
                "type": "node_completed",
                "message": f"Completed {node_name.replace('_', ' ')}",
                "timestamp": ts,
                "duration_ms": round(duration_ms, 1),
            },
        })

    # ------------------------------------------------------------------
    # Tool calls
    # ------------------------------------------------------------------

    async def on_tool_call(
        self,
        *,
        node: str,
        tool_name: str,
        server: str,
        input_params: dict[str, Any],
        output: Any = None,
        latency_ms: float = 0.0,
        status: str = "success",
        error: str | None = None,
    ) -> None:
        """Broadcast a tool_call event and corresponding agent_log."""
        ts = self._ts()
        tool_id = self._next_id("tc")

        await self.manager.broadcast(self.CHANNEL, {
            "type": "tool_call",
            "payload": {
                "id": tool_id,
                "node": node,
                "tool": tool_name,
                "server": server,
                "params": input_params,
                "result": output,
                "status": status,
                "error": error,
                "startedAt": ts,
                "duration_ms": round(latency_ms, 1),
            },
        })

        await self.manager.broadcast(self.CHANNEL, {
            "type": "agent_log",
            "payload": {
                "id": self._next_id("log"),
                "node": node,
                "type": "tool_call",
                "message": f"Calling {tool_name} on {server}",
                "timestamp": ts,
                "duration_ms": round(latency_ms, 1),
            },
        })

    # ------------------------------------------------------------------
    # State snapshots
    # ------------------------------------------------------------------

    async def on_state_update(
        self,
        node: str,
        new_state: dict[str, Any],
        changed_keys: list[str],
    ) -> None:
        """Broadcast a state_update snapshot and agent_log."""
        ts = self._ts()

        await self.manager.broadcast(self.CHANNEL, {
            "type": "state_update",
            "payload": {
                "node": node,
                "timestamp": ts,
                "state": new_state,
                "changedKeys": changed_keys,
            },
        })

        await self.manager.broadcast(self.CHANNEL, {
            "type": "agent_log",
            "payload": {
                "id": self._next_id("log"),
                "node": node,
                "type": "state_update",
                "message": f"State updated: {', '.join(changed_keys)}",
                "timestamp": ts,
            },
        })

    # ------------------------------------------------------------------
    # Human-in-the-loop
    # ------------------------------------------------------------------

    async def on_hitl_required(
        self,
        plan_id: str,
        options: dict[str, Any] | None = None,
    ) -> None:
        """Broadcast an agent_log entry when HITL approval is needed."""
        ts = self._ts()

        await self.manager.broadcast(self.CHANNEL, {
            "type": "agent_log",
            "payload": {
                "id": self._next_id("log"),
                "node": "present_for_approval",
                "type": "node_started",
                "message": f"Plan {plan_id} requires human approval",
                "timestamp": ts,
                "metadata": {"hitl": True, "options": options or {}},
            },
        })
