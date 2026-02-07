"""Simple in-memory TTL cache for weather API responses.

Avoids hitting the Open-Meteo API on every request during demos.
Default TTL is 30 minutes — weather data doesn't change that fast.
"""

from __future__ import annotations

import hashlib
import time
from typing import Any


class TTLCache:
    """Thread-safe in-memory cache with per-entry TTL."""

    def __init__(self, default_ttl_seconds: int = 1800) -> None:
        self._default_ttl = default_ttl_seconds
        self._store: dict[str, tuple[Any, float]] = {}

    def get(self, key: str) -> Any | None:
        """Return cached value if present and not expired, else ``None``."""
        entry = self._store.get(key)
        if entry is None:
            return None
        value, expires_at = entry
        if time.monotonic() > expires_at:
            del self._store[key]
            return None
        return value

    def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """Store *value* under *key* with a TTL in seconds."""
        actual_ttl = ttl if ttl is not None else self._default_ttl
        expires_at = time.monotonic() + actual_ttl
        self._store[key] = (value, expires_at)

    def clear(self) -> None:
        """Remove all entries."""
        self._store.clear()

    @property
    def size(self) -> int:
        """Number of entries (including expired ones not yet evicted)."""
        return len(self._store)

    @staticmethod
    def make_key(*args: object) -> str:
        """Build a deterministic cache key from arbitrary arguments."""
        raw = ":".join(str(a) for a in args)
        return hashlib.sha256(raw.encode()).hexdigest()[:16]
