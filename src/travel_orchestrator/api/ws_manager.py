"""WebSocket connection manager with named channels.

Provides a clean abstraction over raw WebSocket sets so that any
part of the backend can broadcast events to specific frontend
channels (``orchestrator``, ``chat``, etc.) without managing
connections directly.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import WebSocket

from travel_orchestrator.utils.logging import get_logger

logger = get_logger(__name__)


class ConnectionManager:
    """Manages WebSocket connections across named channels."""

    def __init__(self) -> None:
        self._channels: dict[str, set[WebSocket]] = {}

    async def connect(self, channel: str, ws: WebSocket) -> None:
        """Accept *ws* and register it under *channel*."""
        await ws.accept()
        if channel not in self._channels:
            self._channels[channel] = set()
        self._channels[channel].add(ws)
        logger.info(
            "ws_connected",
            channel=channel,
            clients=len(self._channels[channel]),
        )

    async def disconnect(self, channel: str, ws: WebSocket) -> None:
        """Remove *ws* from *channel*."""
        clients = self._channels.get(channel)
        if clients:
            clients.discard(ws)
            logger.info(
                "ws_disconnected",
                channel=channel,
                clients=len(clients),
            )

    async def broadcast(self, channel: str, message: dict[str, Any]) -> None:
        """Send *message* to every client on *channel*."""
        clients = self._channels.get(channel)
        if not clients:
            return

        payload = json.dumps(message, default=str)
        disconnected: set[WebSocket] = set()

        for ws in clients:
            try:
                await ws.send_text(payload)
            except Exception:  # noqa: BLE001
                disconnected.add(ws)

        clients -= disconnected

    async def send_personal(self, ws: WebSocket, message: dict[str, Any]) -> None:
        """Send *message* to a single client."""
        payload = json.dumps(message, default=str)
        await ws.send_text(payload)

    def client_count(self, channel: str) -> int:
        """Return the number of connected clients on *channel*."""
        return len(self._channels.get(channel, set()))


# Module-level singleton used across the application.
manager = ConnectionManager()
