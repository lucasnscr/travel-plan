"""Retry logic with exponential backoff and jitter.

Retries on network errors, HTTP 429, and 5xx responses.
Respects ``Retry-After`` headers when present.
"""

from __future__ import annotations

import asyncio
import random
from typing import TYPE_CHECKING, TypeVar

from travel_orchestrator.utils.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

logger = get_logger(__name__)

T = TypeVar("T")

# Defaults
MAX_RETRIES = 3
BASE_DELAY_S = 0.5
MAX_JITTER_S = 0.2


class RetryableError(Exception):
    """Raised to signal a retryable failure.

    Attributes:
        retry_after: Optional delay in seconds from ``Retry-After`` header.
        status_code: HTTP status that triggered the retry.
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        retry_after: float | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.retry_after = retry_after


async def with_retry(
    fn: Callable[..., Awaitable[T]],
    *args: object,
    max_retries: int = MAX_RETRIES,
    base_delay: float = BASE_DELAY_S,
    max_jitter: float = MAX_JITTER_S,
    operation: str = "request",
) -> T:
    """Execute *fn* with automatic retries on :class:`RetryableError`.

    Uses exponential backoff: ``base_delay * 2^attempt + jitter``.
    If the error carries a ``retry_after`` value it is used instead.
    """
    last_exc: Exception | None = None

    for attempt in range(max_retries + 1):
        try:
            return await fn(*args)
        except RetryableError as exc:
            last_exc = exc
            if attempt >= max_retries:
                break

            if exc.retry_after is not None:
                delay = exc.retry_after
            else:
                delay = base_delay * (2**attempt) + random.uniform(0, max_jitter)

            logger.warning(
                "retry_scheduled",
                operation=operation,
                attempt=attempt + 1,
                max_retries=max_retries,
                delay_s=round(delay, 3),
                status_code=exc.status_code,
            )
            await asyncio.sleep(delay)
        except Exception as exc:
            last_exc = exc
            if attempt >= max_retries:
                break

            delay = base_delay * (2**attempt) + random.uniform(0, max_jitter)
            logger.warning(
                "retry_scheduled_on_error",
                operation=operation,
                attempt=attempt + 1,
                error=str(exc),
                delay_s=round(delay, 3),
            )
            await asyncio.sleep(delay)

    raise last_exc  # type: ignore[misc]
