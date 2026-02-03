"""Prometheus metrics for the travel orchestrator.

Uses a custom ``CollectorRegistry`` so tests can call ``reset_metrics()``
to get a fresh set of counters/histograms/gauges without polluting the
global default registry.

Decorators (``track_node_execution``, ``track_planning``) reference the
module-level metric objects.  Python resolves these names at **call time**,
so ``reset_metrics()`` correctly swaps in new instances even for functions
already decorated.
"""

from __future__ import annotations

import asyncio
import functools
import time
from typing import Any, ParamSpec, TypeVar

from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

from travel_orchestrator.utils.logging import get_logger

logger = get_logger(__name__)

P = ParamSpec("P")
T = TypeVar("T")

# ---------------------------------------------------------------------------
# Registry & metric factory
# ---------------------------------------------------------------------------

REGISTRY = CollectorRegistry()


def _create_metrics(registry: CollectorRegistry) -> dict[str, Any]:
    """Create all metric objects on the given *registry* and return them."""
    return {
        "plans_completed": Counter(
            "travel_plans_completed_total",
            "Total travel plans completed",
            labelnames=["status"],
            registry=registry,
        ),
        "plans_approved": Counter(
            "travel_plans_approved_total",
            "Total travel plans approved",
            registry=registry,
        ),
        "plans_rejected": Counter(
            "travel_plans_rejected_total",
            "Total travel plans rejected",
            registry=registry,
        ),
        "planning_duration": Histogram(
            "travel_planning_duration_seconds",
            "Duration of the full planning pipeline",
            buckets=(10, 30, 60, 120, 300),
            registry=registry,
        ),
        "cost_per_plan": Histogram(
            "travel_plan_cost_dollars",
            "Cost per travel plan in dollars",
            buckets=(0.1, 0.5, 1.0, 2.0, 5.0),
            registry=registry,
        ),
        "active_plannings": Gauge(
            "travel_active_plannings",
            "Number of travel plans currently being generated",
            registry=registry,
        ),
        "node_execution_time": Histogram(
            "travel_node_execution_seconds",
            "Execution time per graph node",
            labelnames=["node_name"],
            buckets=(0.1, 0.5, 1.0, 5.0, 10.0, 30.0),
            registry=registry,
        ),
    }


# Bootstrap module-level metrics
_metrics = _create_metrics(REGISTRY)

plans_completed: Counter = _metrics["plans_completed"]
plans_approved: Counter = _metrics["plans_approved"]
plans_rejected: Counter = _metrics["plans_rejected"]
planning_duration: Histogram = _metrics["planning_duration"]
cost_per_plan: Histogram = _metrics["cost_per_plan"]
active_plannings: Gauge = _metrics["active_plannings"]
node_execution_time: Histogram = _metrics["node_execution_time"]


# ---------------------------------------------------------------------------
# Test isolation
# ---------------------------------------------------------------------------


def reset_metrics(registry: CollectorRegistry | None = None) -> None:
    """Replace all module-level metrics with fresh instances.

    If *registry* is ``None`` a new empty ``CollectorRegistry`` is created.
    This is intended for test fixtures so each test starts with zeroed
    counters.
    """
    global REGISTRY, plans_completed, plans_approved, plans_rejected  # noqa: PLW0603
    global planning_duration, cost_per_plan, active_plannings, node_execution_time  # noqa: PLW0603

    REGISTRY = registry or CollectorRegistry()
    m = _create_metrics(REGISTRY)

    plans_completed = m["plans_completed"]
    plans_approved = m["plans_approved"]
    plans_rejected = m["plans_rejected"]
    planning_duration = m["planning_duration"]
    cost_per_plan = m["cost_per_plan"]
    active_plannings = m["active_plannings"]
    node_execution_time = m["node_execution_time"]


# ---------------------------------------------------------------------------
# Decorators
# ---------------------------------------------------------------------------


def track_node_execution(node_name: str):
    """Decorator that records execution duration on the ``node_execution_time`` histogram.

    Works with both async and sync functions.  Duration is always
    recorded, even if the wrapped function raises.
    """

    def decorator(fn):
        if asyncio.iscoroutinefunction(fn):

            @functools.wraps(fn)
            async def _async_wrapper(*args: Any, **kwargs: Any) -> Any:
                import travel_orchestrator.observability.metrics as _mod

                start = time.perf_counter()
                try:
                    return await fn(*args, **kwargs)
                finally:
                    elapsed = time.perf_counter() - start
                    _mod.node_execution_time.labels(node_name=node_name).observe(elapsed)

            return _async_wrapper

        @functools.wraps(fn)
        def _sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            import travel_orchestrator.observability.metrics as _mod

            start = time.perf_counter()
            try:
                return fn(*args, **kwargs)
            finally:
                elapsed = time.perf_counter() - start
                _mod.node_execution_time.labels(node_name=node_name).observe(elapsed)

        return _sync_wrapper

    return decorator


def track_planning():
    """Decorator that tracks the full planning pipeline.

    * Increments / decrements ``active_plannings`` gauge.
    * Observes ``planning_duration`` histogram.
    * Increments ``plans_completed`` counter with a ``status`` label
      (``"success"`` or ``"error"``).

    Works with both async and sync functions.
    """

    def decorator(fn):
        if asyncio.iscoroutinefunction(fn):

            @functools.wraps(fn)
            async def _async_wrapper(*args: Any, **kwargs: Any) -> Any:
                import travel_orchestrator.observability.metrics as _mod

                _mod.active_plannings.inc()
                start = time.perf_counter()
                try:
                    result = await fn(*args, **kwargs)
                    elapsed = time.perf_counter() - start
                    _mod.planning_duration.observe(elapsed)
                    _mod.plans_completed.labels(status="success").inc()
                    return result
                except Exception:
                    elapsed = time.perf_counter() - start
                    _mod.planning_duration.observe(elapsed)
                    _mod.plans_completed.labels(status="error").inc()
                    raise
                finally:
                    _mod.active_plannings.dec()

            return _async_wrapper

        @functools.wraps(fn)
        def _sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            import travel_orchestrator.observability.metrics as _mod

            _mod.active_plannings.inc()
            start = time.perf_counter()
            try:
                result = fn(*args, **kwargs)
                elapsed = time.perf_counter() - start
                _mod.planning_duration.observe(elapsed)
                _mod.plans_completed.labels(status="success").inc()
                return result
            except Exception:
                elapsed = time.perf_counter() - start
                _mod.planning_duration.observe(elapsed)
                _mod.plans_completed.labels(status="error").inc()
                raise
            finally:
                _mod.active_plannings.dec()

        return _sync_wrapper

    return decorator


# ---------------------------------------------------------------------------
# Convenience helpers
# ---------------------------------------------------------------------------


def record_plan_approval(status: str) -> None:
    """Record a plan approval or rejection.

    Increments the appropriate convenience counter (``plans_approved``
    or ``plans_rejected``) **and** the ``plans_completed`` counter
    with the given *status* label.
    """
    import travel_orchestrator.observability.metrics as _mod

    if status == "approved":
        _mod.plans_approved.inc()
    elif status == "rejected":
        _mod.plans_rejected.inc()

    _mod.plans_completed.labels(status=status).inc()


def record_plan_cost(cost: float) -> None:
    """Observe the dollar cost of a completed plan."""
    import travel_orchestrator.observability.metrics as _mod

    _mod.cost_per_plan.observe(cost)


# ---------------------------------------------------------------------------
# Exposition
# ---------------------------------------------------------------------------


def get_metrics() -> bytes:
    """Return Prometheus exposition format for the current registry."""
    import travel_orchestrator.observability.metrics as _mod

    return generate_latest(_mod.REGISTRY)
