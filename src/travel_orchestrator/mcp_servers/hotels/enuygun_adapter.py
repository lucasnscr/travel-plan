"""MCP-to-MCP client adapter for the Enuygun hotel search upstream.

Connects to the Enuygun MCP endpoint via Streamable HTTP transport,
discovers available tools, and invokes the hotel-search tool.
"""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any

import httpx
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from travel_orchestrator.mcp_servers.hotels.retry import RetryableError, with_retry
from travel_orchestrator.utils.logging import get_logger

logger = get_logger(__name__)

# Concurrency limiter shared across the adapter.
_semaphore = asyncio.Semaphore(5)

# Tool name cache (populated on first call).
_cached_hotel_tool_name: str | None = None

# Default request timeout (seconds).
_REQUEST_TIMEOUT = 15.0


# ---------------------------------------------------------------------------
# OAuth helpers
# ---------------------------------------------------------------------------


async def _obtain_oauth_token() -> str | None:
    """Perform client-credentials OAuth flow if configured.

    Returns the access token, or *None* when OAuth env vars are absent.
    """
    client_id = os.environ.get("ENUYGUN_OAUTH_CLIENT_ID")
    client_secret = os.environ.get("ENUYGUN_OAUTH_CLIENT_SECRET")
    token_url = os.environ.get("ENUYGUN_OAUTH_TOKEN_URL")

    if not (client_id and client_secret and token_url):
        return None

    scope = os.environ.get("ENUYGUN_OAUTH_SCOPE", "")

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            token_url,
            data={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
                "scope": scope,
            },
        )
        resp.raise_for_status()
        return resp.json()["access_token"]


def _build_headers() -> dict[str, str]:
    """Build HTTP headers, including OAuth bearer token when available."""
    headers: dict[str, str] = {}
    # Token is obtained synchronously from cache / env for header construction.
    token = os.environ.get("ENUYGUN_OAUTH_ACCESS_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


# ---------------------------------------------------------------------------
# MCP client helpers
# ---------------------------------------------------------------------------


async def _discover_hotel_tool(session: ClientSession) -> str:
    """List upstream tools and return the name of the hotel-search tool.

    Caches the result so subsequent calls skip discovery.
    """
    global _cached_hotel_tool_name  # noqa: PLW0603
    if _cached_hotel_tool_name is not None:
        return _cached_hotel_tool_name

    result = await session.list_tools()

    # Heuristic: pick the first tool whose name contains "hotel"
    for tool in result.tools:
        if "hotel" in tool.name.lower():
            _cached_hotel_tool_name = tool.name
            logger.info("upstream_hotel_tool_discovered", tool_name=tool.name)
            return tool.name

    # Fallback: list all tool names for debugging and use a sensible default
    names = [t.name for t in result.tools]
    logger.warning("no_hotel_tool_found", available_tools=names)

    # Try common names
    for candidate in ("searchHotels", "search_hotels", "hotel_search"):
        if candidate in names:
            _cached_hotel_tool_name = candidate
            return candidate

    raise RuntimeError(
        f"No hotel-search tool found on upstream MCP. Available: {names}"
    )


async def _call_upstream(
    mcp_url: str,
    tool_name: str,
    arguments: dict[str, Any],
) -> list[dict[str, Any]]:
    """Open a transient MCP session and invoke *tool_name*.

    Raises :class:`RetryableError` on network / 429 / 5xx failures
    so the retry wrapper can handle them.
    """
    headers = _build_headers()

    try:
        async with streamablehttp_client(
            url=mcp_url,
            headers=headers,
            timeout=_REQUEST_TIMEOUT,
        ) as (read_stream, write_stream, _get_url):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()

                resolved_name = tool_name or await _discover_hotel_tool(session)

                call_result = await session.call_tool(resolved_name, arguments)

                # Parse TextContent items into dicts
                raw_items: list[dict[str, Any]] = []
                for content in call_result.content:
                    if hasattr(content, "text"):
                        parsed = json.loads(content.text)
                        if isinstance(parsed, list):
                            raw_items.extend(parsed)
                        elif isinstance(parsed, dict):
                            raw_items.append(parsed)

                return raw_items

    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        if status in (429, 408) or status >= 500:
            retry_after_hdr = exc.response.headers.get("Retry-After")
            retry_after = float(retry_after_hdr) if retry_after_hdr else None
            raise RetryableError(
                f"HTTP {status} from upstream",
                status_code=status,
                retry_after=retry_after,
            ) from exc
        raise

    except (httpx.TimeoutException, httpx.ConnectError, OSError) as exc:
        raise RetryableError(f"Network error: {exc}") from exc


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def search_hotels(
    destination: str,
    check_in: str,
    check_out: str,
    guests: int = 1,
    *,
    mcp_url: str | None = None,
    tool_name: str | None = None,
    extra_args: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Search hotels via the Enuygun upstream MCP with retry.

    Returns a list of raw hotel dicts as received from the upstream.
    """
    url = mcp_url or os.environ.get(
        "ENUYGUN_MCP_URL", "https://mcp.enuygun.com/mcp"
    )

    arguments: dict[str, Any] = {
        "destination": destination,
        "checkIn": check_in,
        "checkOut": check_out,
        "guests": guests,
    }
    if extra_args:
        arguments.update(extra_args)

    async with _semaphore:
        import time

        start = time.perf_counter()
        try:
            results = await with_retry(
                _call_upstream,
                url,
                tool_name,
                arguments,
                operation="enuygun_search_hotels",
            )
            latency_ms = (time.perf_counter() - start) * 1000
            logger.info(
                "upstream_search_completed",
                destination=destination,
                check_in=check_in,
                check_out=check_out,
                guests=guests,
                result_count=len(results),
                latency_ms=round(latency_ms, 1),
            )
            return results
        except Exception:
            latency_ms = (time.perf_counter() - start) * 1000
            logger.exception(
                "upstream_search_failed",
                destination=destination,
                latency_ms=round(latency_ms, 1),
            )
            raise
