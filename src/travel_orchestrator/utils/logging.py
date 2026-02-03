"""Structured logging setup using structlog.

Provides JSON output in production and colorized console output in
development.  All log entries automatically include timestamp, level,
and logger name.  Graph-node decorators inject plan_id and timing.
"""

from __future__ import annotations

import asyncio
import functools
import logging
import sys
import time
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, ParamSpec, TypeVar

import structlog

if TYPE_CHECKING:
    from collections.abc import Callable, Generator

    from structlog.stdlib import BoundLogger

P = ParamSpec("P")
T = TypeVar("T")

_configured = False


def setup_logging(*, log_level: str = "INFO", environment: str = "development") -> None:
    """Configure structlog and stdlib logging for the whole process.

    Call once at application startup.  Subsequent calls are no-ops.

    Args:
        log_level: Root log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        environment: When ``"development"`` renders colored console output;
            otherwise emits JSON lines.
    """
    global _configured  # noqa: PLW0603
    if _configured:
        return
    _configured = True

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    if environment == "development":
        renderer: structlog.types.Processor = structlog.dev.ConsoleRenderer(colors=True)
    else:
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
        foreign_pre_chain=shared_processors,
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(log_level.upper())


def get_logger(name: str) -> BoundLogger:
    """Return a structlog bound logger for the given module name.

    Ensures ``setup_logging`` has been called at least once (using
    defaults or settings when available).
    """
    if not _configured:
        _setup_from_settings()
    return structlog.stdlib.get_logger(name)


def _setup_from_settings() -> None:
    """Bootstrap logging from Settings, falling back to defaults."""
    try:
        from travel_orchestrator.config.settings import get_settings

        settings = get_settings()
        setup_logging(log_level=settings.log_level, environment=settings.environment)
    except Exception:  # noqa: BLE001
        setup_logging()


# ---------------------------------------------------------------------------
# Context helpers
# ---------------------------------------------------------------------------


@contextmanager
def add_context(**kwargs: Any) -> Generator[None, None, None]:
    """Temporarily bind key-value pairs to every log entry in this scope.

    Uses structlog's contextvars integration so the bindings propagate
    through ``await`` boundaries inside the block.

    Example::

        with add_context(plan_id="abc-123", user_id="u-1"):
            logger.info("processing")  # includes plan_id and user_id
    """
    ctx = structlog.contextvars.bind_contextvars(**kwargs)
    try:
        yield
    finally:
        structlog.contextvars.unbind_contextvars(*kwargs.keys())


# ---------------------------------------------------------------------------
# Decorators
# ---------------------------------------------------------------------------


def log_execution(fn: Callable[P, T]) -> Callable[P, T]:
    """Decorator that logs function entry, duration, and outcome.

    Works with both sync and async functions.  On success logs
    ``function_name``, ``duration_ms``, and ``success=True``; on
    exception logs the error and re-raises.
    """
    logger = structlog.stdlib.get_logger(fn.__qualname__)

    if asyncio.iscoroutinefunction(fn):

        @functools.wraps(fn)
        async def _async_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            logger.info("node_started", function=fn.__qualname__)
            start = time.perf_counter()
            try:
                result = await fn(*args, **kwargs)
                duration_ms = (time.perf_counter() - start) * 1000
                logger.info(
                    "node_finished",
                    function=fn.__qualname__,
                    duration_ms=round(duration_ms, 2),
                    success=True,
                )
                return result
            except Exception:
                duration_ms = (time.perf_counter() - start) * 1000
                logger.exception(
                    "node_failed",
                    function=fn.__qualname__,
                    duration_ms=round(duration_ms, 2),
                    success=False,
                )
                raise

        return _async_wrapper  # type: ignore[return-value]

    @functools.wraps(fn)
    def _sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        logger.info("node_started", function=fn.__qualname__)
        start = time.perf_counter()
        try:
            result = fn(*args, **kwargs)
            duration_ms = (time.perf_counter() - start) * 1000
            logger.info(
                "node_finished",
                function=fn.__qualname__,
                duration_ms=round(duration_ms, 2),
                success=True,
            )
            return result
        except Exception:
            duration_ms = (time.perf_counter() - start) * 1000
            logger.exception(
                "node_failed",
                function=fn.__qualname__,
                duration_ms=round(duration_ms, 2),
                success=False,
            )
            raise

    return _sync_wrapper  # type: ignore[return-value]


def log_node_execution(
    node_name: str,
    *,
    extract_plan_id: bool = True,
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Decorator for LangGraph nodes that auto-binds ``plan_id`` from state.

    Wraps async node functions, extracting ``plan_id`` from the first
    positional argument (the state dict) and binding it as log context
    for the duration of the call.

    Args:
        node_name: Human-readable node label used in log events.
        extract_plan_id: If True, reads ``plan_id`` from the state dict
            passed as the first argument.
    """

    def decorator(fn: Callable[P, T]) -> Callable[P, T]:
        logger = structlog.stdlib.get_logger(node_name)

        if asyncio.iscoroutinefunction(fn):

            @functools.wraps(fn)
            async def _wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
                ctx_kwargs: dict[str, Any] = {"node": node_name}
                if extract_plan_id and args:
                    state = args[0]
                    if isinstance(state, dict) and "plan_id" in state:
                        ctx_kwargs["plan_id"] = state["plan_id"]

                with add_context(**ctx_kwargs):
                    logger.info("node_started")
                    start = time.perf_counter()
                    try:
                        result = await fn(*args, **kwargs)
                        duration_ms = (time.perf_counter() - start) * 1000
                        logger.info(
                            "node_finished",
                            duration_ms=round(duration_ms, 2),
                            success=True,
                        )
                        return result
                    except Exception:
                        duration_ms = (time.perf_counter() - start) * 1000
                        logger.exception(
                            "node_failed",
                            duration_ms=round(duration_ms, 2),
                            success=False,
                        )
                        raise

            return _wrapper  # type: ignore[return-value]

        @functools.wraps(fn)
        def _sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            ctx_kwargs: dict[str, Any] = {"node": node_name}
            if extract_plan_id and args:
                state = args[0]
                if isinstance(state, dict) and "plan_id" in state:
                    ctx_kwargs["plan_id"] = state["plan_id"]

            with add_context(**ctx_kwargs):
                logger.info("node_started")
                start = time.perf_counter()
                try:
                    result = fn(*args, **kwargs)
                    duration_ms = (time.perf_counter() - start) * 1000
                    logger.info(
                        "node_finished",
                        duration_ms=round(duration_ms, 2),
                        success=True,
                    )
                    return result
                except Exception:
                    duration_ms = (time.perf_counter() - start) * 1000
                    logger.exception(
                        "node_failed",
                        duration_ms=round(duration_ms, 2),
                        success=False,
                    )
                    raise

        return _sync_wrapper  # type: ignore[return-value]

    return decorator
