"""Unit tests for documentation files."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
DOCS = ROOT / "docs"


# ===================================================================
# TestDocsReadme
# ===================================================================


class TestDocsReadme:
    def test_file_exists(self) -> None:
        assert (DOCS / "README.md").is_file()

    def test_has_visao_geral(self) -> None:
        content = (DOCS / "README.md").read_text()
        assert "Visao Geral" in content

    def test_has_architecture_diagram(self) -> None:
        content = (DOCS / "README.md").read_text()
        assert "LangGraph State Machine" in content

    def test_has_quick_start(self) -> None:
        content = (DOCS / "README.md").read_text()
        assert "Quick Start" in content

    def test_has_project_structure(self) -> None:
        content = (DOCS / "README.md").read_text()
        assert "Estrutura do Projeto" in content

    def test_has_stack_table(self) -> None:
        content = (DOCS / "README.md").read_text()
        assert "Stack Tecnologica" in content

    def test_references_all_protocols(self) -> None:
        content = (DOCS / "README.md").read_text()
        assert "LangGraph" in content
        assert "MCP" in content
        assert "A2A" in content
        assert "UCP" in content

    def test_links_to_other_docs(self) -> None:
        content = (DOCS / "README.md").read_text()
        assert "architecture.md" in content
        assert "configuration.md" in content
        assert "deployment.md" in content
        assert "api-reference.md" in content


# ===================================================================
# TestDocsArchitecture
# ===================================================================


class TestDocsArchitecture:
    def test_file_exists(self) -> None:
        assert (DOCS / "architecture.md").is_file()

    def test_has_graph_flow(self) -> None:
        content = (DOCS / "architecture.md").read_text()
        assert "gather_requirements" in content
        assert "analyze_destination" in content
        assert "search_hotels" in content
        assert "optimize_itinerary" in content

    def test_has_conditional_edges(self) -> None:
        content = (DOCS / "architecture.md").read_text()
        assert "should_optimize_costs" in content
        assert "process_approval_decision" in content
        assert "determine_revision_target" in content

    def test_has_state_model(self) -> None:
        content = (DOCS / "architecture.md").read_text()
        assert "TravelPlannerCore" in content
        assert "plan_id" in content
        assert "approval_status" in content

    def test_has_mcp_servers(self) -> None:
        content = (DOCS / "architecture.md").read_text()
        assert "Weather" in content
        assert "Hotels" in content
        assert "Activities" in content
        assert "Context" in content

    def test_has_validators(self) -> None:
        content = (DOCS / "architecture.md").read_text()
        assert "ItineraryValidator" in content
        assert "WeatherValidator" in content


# ===================================================================
# TestDocsConfiguration
# ===================================================================


class TestDocsConfiguration:
    def test_file_exists(self) -> None:
        assert (DOCS / "configuration.md").is_file()

    def test_has_env_vars(self) -> None:
        content = (DOCS / "configuration.md").read_text()
        assert "ANTHROPIC_API_KEY" in content
        assert "OPENAI_API_KEY" in content
        assert "LOG_LEVEL" in content
        assert "REDIS_URL" in content

    def test_has_constants(self) -> None:
        content = (DOCS / "configuration.md").read_text()
        assert "MAX_ACTIVITIES_PER_DAY" in content
        assert "MAX_DAILY_TRAVEL_TIME_MINUTES" in content
        assert "PACE_ACTIVITIES_PER_DAY" in content

    def test_has_env_example(self) -> None:
        content = (DOCS / "configuration.md").read_text()
        assert ".env" in content

    def test_has_budget_allocation(self) -> None:
        content = (DOCS / "configuration.md").read_text()
        assert "35%" in content
        assert "20%" in content


# ===================================================================
# TestDocsDeployment
# ===================================================================


class TestDocsDeployment:
    def test_file_exists(self) -> None:
        assert (DOCS / "deployment.md").is_file()

    def test_has_docker_section(self) -> None:
        content = (DOCS / "deployment.md").read_text()
        assert "Docker" in content
        assert "docker compose" in content

    def test_has_port_table(self) -> None:
        content = (DOCS / "deployment.md").read_text()
        assert "8000" in content
        assert "3000" in content
        assert "9090" in content

    def test_has_prometheus_section(self) -> None:
        content = (DOCS / "deployment.md").read_text()
        assert "Prometheus" in content
        assert "PromQL" in content

    def test_has_metrics_table(self) -> None:
        content = (DOCS / "deployment.md").read_text()
        assert "travel_plans_completed_total" in content
        assert "travel_node_execution_seconds" in content

    def test_has_local_execution(self) -> None:
        content = (DOCS / "deployment.md").read_text()
        assert "Execucao Local" in content
        assert "pytest" in content


# ===================================================================
# TestDocsApiReference
# ===================================================================


class TestDocsApiReference:
    def test_file_exists(self) -> None:
        assert (DOCS / "api-reference.md").is_file()

    def test_has_graph_section(self) -> None:
        content = (DOCS / "api-reference.md").read_text()
        assert "compile_graph" in content

    def test_has_nodes_section(self) -> None:
        content = (DOCS / "api-reference.md").read_text()
        assert "gather_requirements_node" in content
        assert "optimize_itinerary_node" in content

    def test_has_mcp_clients(self) -> None:
        content = (DOCS / "api-reference.md").read_text()
        assert "get_weather_forecast" in content
        assert "search_hotels" in content
        assert "discover_activities" in content
        assert "get_user_preferences" in content

    def test_has_multimodal(self) -> None:
        content = (DOCS / "api-reference.md").read_text()
        assert "populate_state_from_audio" in content
        assert "analyze_inspiration_image" in content
        assert "parse_competitor_offer_pdf" in content

    def test_has_validators(self) -> None:
        content = (DOCS / "api-reference.md").read_text()
        assert "validate_geographic_coherence" in content
        assert "validate_outdoor_activities" in content
        assert "ValidationResult" in content

    def test_has_output_generators(self) -> None:
        content = (DOCS / "api-reference.md").read_text()
        assert "generate_map_from_state" in content
        assert "generate_pdf_from_state" in content

    def test_has_observability(self) -> None:
        content = (DOCS / "api-reference.md").read_text()
        assert "track_node_execution" in content
        assert "track_planning" in content
        assert "get_metrics" in content

    def test_has_frontend(self) -> None:
        content = (DOCS / "api-reference.md").read_text()
        assert "/api/plan" in content
        assert "plan_trip" in content
        assert "handle_approval" in content

    def test_has_logging(self) -> None:
        content = (DOCS / "api-reference.md").read_text()
        assert "get_logger" in content
        assert "log_node_execution" in content
        assert "add_context" in content


# ===================================================================
# TestDocsCompleteness
# ===================================================================


class TestDocsCompleteness:
    """Verify all docs cross-reference correctly and no file is missing."""

    def test_all_four_docs_exist(self) -> None:
        assert (DOCS / "README.md").is_file()
        assert (DOCS / "architecture.md").is_file()
        assert (DOCS / "configuration.md").is_file()
        assert (DOCS / "deployment.md").is_file()
        assert (DOCS / "api-reference.md").is_file()

    def test_readme_links_resolve(self) -> None:
        content = (DOCS / "README.md").read_text()
        for linked in ["architecture.md", "configuration.md", "deployment.md", "api-reference.md"]:
            assert linked in content
            assert (DOCS / linked).is_file()
