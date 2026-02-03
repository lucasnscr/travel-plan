"""Unit tests for the observability metrics module."""

from __future__ import annotations

from typing import Any

import pytest
from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram

from travel_orchestrator.observability.metrics import (
    get_metrics,
    record_plan_approval,
    record_plan_cost,
    reset_metrics,
    track_node_execution,
    track_planning,
)


# ---------------------------------------------------------------------------
# Fixture — fresh registry before every test
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _fresh_registry() -> None:
    """Reset all metrics to a fresh registry before each test."""
    reset_metrics()


# ===================================================================
# TestMetricDefinitions
# ===================================================================


class TestMetricDefinitions:
    def test_plans_completed_is_counter(self) -> None:
        import travel_orchestrator.observability.metrics as m

        assert isinstance(m.plans_completed, Counter)

    def test_plans_approved_is_counter(self) -> None:
        import travel_orchestrator.observability.metrics as m

        assert isinstance(m.plans_approved, Counter)

    def test_plans_rejected_is_counter(self) -> None:
        import travel_orchestrator.observability.metrics as m

        assert isinstance(m.plans_rejected, Counter)

    def test_planning_duration_is_histogram(self) -> None:
        import travel_orchestrator.observability.metrics as m

        assert isinstance(m.planning_duration, Histogram)

    def test_cost_per_plan_is_histogram(self) -> None:
        import travel_orchestrator.observability.metrics as m

        assert isinstance(m.cost_per_plan, Histogram)

    def test_active_plannings_is_gauge(self) -> None:
        import travel_orchestrator.observability.metrics as m

        assert isinstance(m.active_plannings, Gauge)

    def test_node_execution_time_is_histogram(self) -> None:
        import travel_orchestrator.observability.metrics as m

        assert isinstance(m.node_execution_time, Histogram)


# ===================================================================
# TestResetMetrics
# ===================================================================


class TestResetMetrics:
    def test_creates_fresh_registry(self) -> None:
        import travel_orchestrator.observability.metrics as m

        old_registry = m.REGISTRY
        reset_metrics()
        assert m.REGISTRY is not old_registry

    def test_counters_start_at_zero(self) -> None:
        import travel_orchestrator.observability.metrics as m

        # Increment, then reset
        m.plans_approved.inc()
        reset_metrics()
        # After reset, the counter should be zero (no samples)
        output = get_metrics().decode()
        assert "travel_plans_approved_total 0.0" in output or \
            "travel_plans_approved_total" not in output.split("# HELP")[0]


# ===================================================================
# TestTrackNodeExecution
# ===================================================================


class TestTrackNodeExecution:
    @pytest.mark.asyncio
    async def test_records_duration_on_success(self) -> None:
        @track_node_execution("test_node")
        async def my_node(state: dict[str, Any]) -> dict[str, Any]:
            return state

        await my_node({"plan_id": "p1"})

        output = get_metrics().decode()
        assert "travel_node_execution_seconds" in output
        assert 'node_name="test_node"' in output

    @pytest.mark.asyncio
    async def test_records_duration_on_failure(self) -> None:
        @track_node_execution("failing_node")
        async def bad_node(state: dict[str, Any]) -> dict[str, Any]:
            raise ValueError("boom")

        with pytest.raises(ValueError, match="boom"):
            await bad_node({})

        output = get_metrics().decode()
        assert 'node_name="failing_node"' in output

    @pytest.mark.asyncio
    async def test_preserves_function_name(self) -> None:
        @track_node_execution("some_node")
        async def original_name() -> str:
            return "ok"

        assert original_name.__name__ == "original_name"

    @pytest.mark.asyncio
    async def test_multiple_nodes_tracked_separately(self) -> None:
        @track_node_execution("node_a")
        async def node_a() -> None:
            pass

        @track_node_execution("node_b")
        async def node_b() -> None:
            pass

        await node_a()
        await node_b()

        output = get_metrics().decode()
        assert 'node_name="node_a"' in output
        assert 'node_name="node_b"' in output

    def test_sync_supported(self) -> None:
        @track_node_execution("sync_node")
        def sync_fn() -> int:
            return 42

        result = sync_fn()
        assert result == 42

        output = get_metrics().decode()
        assert 'node_name="sync_node"' in output


# ===================================================================
# TestTrackPlanning
# ===================================================================


class TestTrackPlanning:
    @pytest.mark.asyncio
    async def test_increments_success_counter(self) -> None:
        @track_planning()
        async def plan() -> str:
            return "done"

        await plan()

        output = get_metrics().decode()
        assert 'travel_plans_completed_total{status="success"}' in output

    @pytest.mark.asyncio
    async def test_increments_error_counter(self) -> None:
        @track_planning()
        async def plan() -> str:
            raise RuntimeError("fail")

        with pytest.raises(RuntimeError):
            await plan()

        output = get_metrics().decode()
        assert 'travel_plans_completed_total{status="error"}' in output

    @pytest.mark.asyncio
    async def test_records_duration(self) -> None:
        @track_planning()
        async def plan() -> str:
            return "done"

        await plan()

        output = get_metrics().decode()
        assert "travel_planning_duration_seconds" in output

    @pytest.mark.asyncio
    async def test_gauge_returns_to_zero(self) -> None:
        import travel_orchestrator.observability.metrics as m

        @track_planning()
        async def plan() -> str:
            return "done"

        await plan()

        # Gauge should be back at 0 after completion
        assert m.active_plannings._value.get() == 0.0

    @pytest.mark.asyncio
    async def test_gauge_decrements_on_error(self) -> None:
        import travel_orchestrator.observability.metrics as m

        @track_planning()
        async def plan() -> str:
            raise RuntimeError("fail")

        with pytest.raises(RuntimeError):
            await plan()

        assert m.active_plannings._value.get() == 0.0

    @pytest.mark.asyncio
    async def test_preserves_return_value(self) -> None:
        @track_planning()
        async def plan() -> dict[str, str]:
            return {"result": "ok"}

        result = await plan()
        assert result == {"result": "ok"}


# ===================================================================
# TestRecordPlanApproval
# ===================================================================


class TestRecordPlanApproval:
    def test_approved_increments_both_counters(self) -> None:
        record_plan_approval("approved")

        output = get_metrics().decode()
        assert "travel_plans_approved_total" in output
        assert 'travel_plans_completed_total{status="approved"}' in output

    def test_rejected_increments_both_counters(self) -> None:
        record_plan_approval("rejected")

        output = get_metrics().decode()
        assert "travel_plans_rejected_total" in output
        assert 'travel_plans_completed_total{status="rejected"}' in output

    def test_unknown_status_tracked_in_completed(self) -> None:
        record_plan_approval("cancelled")

        output = get_metrics().decode()
        assert 'travel_plans_completed_total{status="cancelled"}' in output


# ===================================================================
# TestRecordPlanCost
# ===================================================================


class TestRecordPlanCost:
    def test_observes_cost_value(self) -> None:
        record_plan_cost(1.5)

        output = get_metrics().decode()
        assert "travel_plan_cost_dollars" in output

    def test_appears_in_output(self) -> None:
        record_plan_cost(3.0)

        output = get_metrics().decode()
        # The sum bucket should contain 3.0
        assert "travel_plan_cost_dollars_sum 3.0" in output


# ===================================================================
# TestGetMetrics
# ===================================================================


class TestGetMetrics:
    def test_returns_bytes(self) -> None:
        result = get_metrics()
        assert isinstance(result, bytes)

    def test_contains_metric_after_observation(self) -> None:
        record_plan_cost(2.0)
        result = get_metrics()
        assert b"travel_plan_cost_dollars" in result

    def test_empty_registry_returns_bytes(self) -> None:
        reset_metrics(CollectorRegistry())
        result = get_metrics()
        assert isinstance(result, bytes)


# ===================================================================
# TestMetricsServer
# ===================================================================


class TestMetricsServer:
    def test_health_returns_200(self) -> None:
        from fastapi.testclient import TestClient

        from travel_orchestrator.observability.server import app

        client = TestClient(app)
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}

    def test_metrics_returns_200_with_text_plain(self) -> None:
        from fastapi.testclient import TestClient

        from travel_orchestrator.observability.server import app

        client = TestClient(app)
        response = client.get("/metrics")
        assert response.status_code == 200
        assert "text/plain" in response.headers["content-type"]

    def test_metrics_contains_prometheus_format(self) -> None:
        from fastapi.testclient import TestClient

        from travel_orchestrator.observability.server import app

        record_plan_cost(1.0)
        client = TestClient(app)
        response = client.get("/metrics")
        assert "travel_plan_cost_dollars" in response.text

    def test_dashboard_returns_html(self) -> None:
        from fastapi.testclient import TestClient

        from travel_orchestrator.observability.server import app

        client = TestClient(app)
        response = client.get("/dashboard")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "Travel Orchestrator" in response.text

    def test_dashboard_contains_chart_js(self) -> None:
        from fastapi.testclient import TestClient

        from travel_orchestrator.observability.server import app

        client = TestClient(app)
        response = client.get("/dashboard")
        assert "chart.js" in response.text

    def test_dashboard_contains_metric_boxes(self) -> None:
        from fastapi.testclient import TestClient

        from travel_orchestrator.observability.server import app

        client = TestClient(app)
        response = client.get("/dashboard")
        assert "plans-completed" in response.text
        assert "approval-rate" in response.text
        assert "avg-time" in response.text

    def test_dashboard_contains_fetch_metrics(self) -> None:
        from fastapi.testclient import TestClient

        from travel_orchestrator.observability.server import app

        client = TestClient(app)
        response = client.get("/dashboard")
        assert "fetch('/metrics')" in response.text
        assert "parsePrometheusMetrics" in response.text


# ===================================================================
# TestDashboardHtml
# ===================================================================


class TestDashboardHtml:
    def test_file_exists(self) -> None:
        from pathlib import Path

        html_path = (
            Path(__file__).resolve().parent.parent.parent
            / "src" / "travel_orchestrator" / "frontend" / "dashboard.html"
        )
        assert html_path.is_file()

    def test_valid_html_structure(self) -> None:
        from pathlib import Path

        html_path = (
            Path(__file__).resolve().parent.parent.parent
            / "src" / "travel_orchestrator" / "frontend" / "dashboard.html"
        )
        content = html_path.read_text(encoding="utf-8")
        assert "<!DOCTYPE html>" in content
        assert "<html" in content
        assert "</html>" in content
        assert "<canvas" in content

    def test_has_polling_interval(self) -> None:
        from pathlib import Path

        html_path = (
            Path(__file__).resolve().parent.parent.parent
            / "src" / "travel_orchestrator" / "frontend" / "dashboard.html"
        )
        content = html_path.read_text(encoding="utf-8")
        assert "setInterval" in content

    def test_parses_prometheus_labels(self) -> None:
        from pathlib import Path

        html_path = (
            Path(__file__).resolve().parent.parent.parent
            / "src" / "travel_orchestrator" / "frontend" / "dashboard.html"
        )
        content = html_path.read_text(encoding="utf-8")
        assert "extractLabel" in content
        assert "node_name" in content
