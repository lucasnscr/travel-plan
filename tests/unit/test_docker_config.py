"""Unit tests for Docker configuration files."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent.parent


# ===================================================================
# TestDockerfile
# ===================================================================


class TestDockerfile:
    def test_file_exists(self) -> None:
        assert (ROOT / "Dockerfile").is_file()

    def test_base_image_python_311(self) -> None:
        content = (ROOT / "Dockerfile").read_text()
        assert "python:3.11-slim" in content

    def test_exposes_app_port(self) -> None:
        content = (ROOT / "Dockerfile").read_text()
        assert "8000" in content

    def test_has_healthcheck(self) -> None:
        content = (ROOT / "Dockerfile").read_text()
        assert "HEALTHCHECK" in content

    def test_installs_poetry(self) -> None:
        content = (ROOT / "Dockerfile").read_text()
        assert "install.python-poetry.org" in content

    def test_copies_source(self) -> None:
        content = (ROOT / "Dockerfile").read_text()
        assert "COPY src/" in content

    def test_uses_entrypoint(self) -> None:
        content = (ROOT / "Dockerfile").read_text()
        assert "entrypoint.sh" in content

    def test_no_dev_dependencies(self) -> None:
        content = (ROOT / "Dockerfile").read_text()
        assert "--without dev" in content


# ===================================================================
# TestDockerCompose
# ===================================================================


class TestDockerCompose:
    def test_file_exists(self) -> None:
        assert (ROOT / "docker-compose.yml").is_file()

    def test_valid_yaml(self) -> None:
        content = (ROOT / "docker-compose.yml").read_text()
        data = yaml.safe_load(content)
        assert isinstance(data, dict)

    def test_has_api_service(self) -> None:
        data = yaml.safe_load((ROOT / "docker-compose.yml").read_text())
        assert "api" in data["services"]

    def test_has_frontend_service(self) -> None:
        data = yaml.safe_load((ROOT / "docker-compose.yml").read_text())
        assert "frontend" in data["services"]

    def test_has_redis_service(self) -> None:
        data = yaml.safe_load((ROOT / "docker-compose.yml").read_text())
        assert "redis" in data["services"]

    def test_has_prometheus_service(self) -> None:
        data = yaml.safe_load((ROOT / "docker-compose.yml").read_text())
        assert "prometheus" in data["services"]

    def test_api_exposes_port(self) -> None:
        data = yaml.safe_load((ROOT / "docker-compose.yml").read_text())
        ports = data["services"]["api"]["ports"]
        assert any("8000" in str(p) for p in ports)

    def test_frontend_exposes_port(self) -> None:
        data = yaml.safe_load((ROOT / "docker-compose.yml").read_text())
        ports = data["services"]["frontend"]["ports"]
        assert any("3000" in str(p) for p in ports)

    def test_api_depends_on_redis(self) -> None:
        data = yaml.safe_load((ROOT / "docker-compose.yml").read_text())
        depends = data["services"]["api"]["depends_on"]
        # depends_on can be a list or dict
        if isinstance(depends, list):
            assert "redis" in depends
        else:
            assert "redis" in depends

    def test_api_has_anthropic_key_env(self) -> None:
        data = yaml.safe_load((ROOT / "docker-compose.yml").read_text())
        env = data["services"]["api"]["environment"]
        assert any("ANTHROPIC_API_KEY" in str(e) for e in env)

    def test_api_has_redis_url_env(self) -> None:
        data = yaml.safe_load((ROOT / "docker-compose.yml").read_text())
        env = data["services"]["api"]["environment"]
        assert any("REDIS_URL" in str(e) for e in env)

    def test_prometheus_maps_config(self) -> None:
        data = yaml.safe_load((ROOT / "docker-compose.yml").read_text())
        volumes = data["services"]["prometheus"]["volumes"]
        assert any("prometheus.yml" in str(v) for v in volumes)

    def test_has_named_volumes(self) -> None:
        data = yaml.safe_load((ROOT / "docker-compose.yml").read_text())
        assert "volumes" in data
        assert "redis_data" in data["volumes"]
        assert "prometheus_data" in data["volumes"]


# ===================================================================
# TestPrometheusConfig
# ===================================================================


class TestPrometheusConfig:
    def test_file_exists(self) -> None:
        assert (ROOT / "prometheus.yml").is_file()

    def test_valid_yaml(self) -> None:
        data = yaml.safe_load((ROOT / "prometheus.yml").read_text())
        assert isinstance(data, dict)

    def test_has_scrape_interval(self) -> None:
        data = yaml.safe_load((ROOT / "prometheus.yml").read_text())
        assert "scrape_interval" in data["global"]

    def test_scrapes_api_on_8000(self) -> None:
        data = yaml.safe_load((ROOT / "prometheus.yml").read_text())
        jobs = data["scrape_configs"]
        targets = jobs[0]["static_configs"][0]["targets"]
        assert "api:8000" in targets

    def test_job_name_is_travel_orchestrator(self) -> None:
        data = yaml.safe_load((ROOT / "prometheus.yml").read_text())
        assert data["scrape_configs"][0]["job_name"] == "travel-orchestrator"

    def test_metrics_path(self) -> None:
        data = yaml.safe_load((ROOT / "prometheus.yml").read_text())
        assert data["scrape_configs"][0]["metrics_path"] == "/metrics"


# ===================================================================
# TestDockerignore
# ===================================================================


class TestDockerignore:
    def test_file_exists(self) -> None:
        assert (ROOT / ".dockerignore").is_file()

    def test_ignores_venv(self) -> None:
        content = (ROOT / ".dockerignore").read_text()
        assert ".venv/" in content

    def test_ignores_pycache(self) -> None:
        content = (ROOT / ".dockerignore").read_text()
        assert "__pycache__/" in content

    def test_ignores_env_file(self) -> None:
        content = (ROOT / ".dockerignore").read_text()
        assert ".env" in content

    def test_ignores_git(self) -> None:
        content = (ROOT / ".dockerignore").read_text()
        assert ".git/" in content

    def test_ignores_tests(self) -> None:
        content = (ROOT / ".dockerignore").read_text()
        assert "tests/" in content


# ===================================================================
# TestEntrypoint
# ===================================================================


class TestEntrypoint:
    def test_file_exists(self) -> None:
        assert (ROOT / "scripts" / "entrypoint.sh").is_file()

    def test_starts_uvicorn(self) -> None:
        content = (ROOT / "scripts" / "entrypoint.sh").read_text()
        assert "uvicorn" in content
        assert "8000" in content

    def test_starts_api_server(self) -> None:
        content = (ROOT / "scripts" / "entrypoint.sh").read_text()
        assert "travel_orchestrator.api.main" in content

    def test_uses_exec_for_foreground_process(self) -> None:
        content = (ROOT / "scripts" / "entrypoint.sh").read_text()
        assert "exec " in content

    def test_has_shebang(self) -> None:
        content = (ROOT / "scripts" / "entrypoint.sh").read_text()
        assert content.startswith("#!/bin/bash")


# ===================================================================
# TestFrontendDockerfile
# ===================================================================


class TestFrontendDockerfile:
    def test_file_exists(self) -> None:
        assert (ROOT / "frontend" / "Dockerfile").is_file()

    def test_uses_node(self) -> None:
        content = (ROOT / "frontend" / "Dockerfile").read_text()
        assert "node:" in content

    def test_exposes_3000(self) -> None:
        content = (ROOT / "frontend" / "Dockerfile").read_text()
        assert "3000" in content

    def test_runs_build(self) -> None:
        content = (ROOT / "frontend" / "Dockerfile").read_text()
        assert "npm run build" in content
