"""Static contract tests for docker-compose.yml (M0 T4)."""

from pathlib import Path

import pytest

from bishop_shared.constants import (
    BISHOP_SERVICES,
    BISHOP_VOLUME_MOUNTS,
    QUERY_API_HOST_PORT,
    UI_HOST_PORT,
)

COMPOSE_PATH = Path("docker-compose.yml")

# T1 decision log — per-service host_suffix mounts at M0.
SERVICE_VOLUME_SUFFIXES: dict[str, tuple[str, ...]] = {
    "state-worker": ("sqlite", "logs"),
    "batch-poller": ("sqlite", "logs"),
    "vector-writer": ("lancedb", "duckdb", "bm25", "logs"),
    "query-api": ("lancedb", "duckdb", "bm25", "sqlite", "logs"),
    "pre-filter-worker": ("profiles", "logs"),
    "enrichment-batcher": ("profiles", "logs"),
    "scraper": ("logs",),
    "content-scraper": ("logs",),
    "ui": (),
}

SUFFIX_TO_CONTAINER = {m.host_suffix: m.container_path for m in BISHOP_VOLUME_MOUNTS}


def _service_block(text: str, service: str) -> str:
    marker = f"  {service}:"
    start = text.index(marker)
    rest = text[start + len(marker) :]
    lines: list[str] = [marker]
    for line in rest.splitlines():
        if line and not line.startswith(" ") and not line.startswith("\t"):
            break
        if line.startswith("  ") and not line.startswith("    ") and line.strip().endswith(":"):
            if line != marker:
                break
        lines.append(line)
    return "\n".join(lines)


@pytest.fixture(scope="module")
def compose_text() -> str:
    assert COMPOSE_PATH.is_file(), "docker-compose.yml must exist"
    return COMPOSE_PATH.read_text(encoding="utf-8")


def test_all_nine_services_declared(compose_text: str) -> None:
    for service in BISHOP_SERVICES:
        assert f"  {service}:" in compose_text


def test_bishop_internal_network(compose_text: str) -> None:
    assert "bishop-internal" in compose_text
    assert "name: bishop-internal" in compose_text


def test_state_worker_has_healthcheck_and_no_host_ports(compose_text: str) -> None:
    block = _service_block(compose_text, "state-worker")
    assert "healthcheck:" in block
    assert "curl" in block
    assert "http://localhost:8000/health" in block
    assert "start_period: 30s" in block
    assert "ports:" not in block


def test_query_api_and_ui_host_port_bindings(compose_text: str) -> None:
    query_block = _service_block(compose_text, "query-api")
    ui_block = _service_block(compose_text, "ui")
    assert f'"${{QUERY_API_HOST_PORT}}:8000"' in query_block or "${QUERY_API_HOST_PORT}:8000" in query_block
    assert f'"${{UI_HOST_PORT}}:80"' in ui_block or "${UI_HOST_PORT}:80" in ui_block
    assert str(QUERY_API_HOST_PORT) not in query_block.replace("${QUERY_API_HOST_PORT}", "")
    assert str(UI_HOST_PORT) not in ui_block.replace("${UI_HOST_PORT}", "")


@pytest.mark.parametrize("dependent", [s for s in BISHOP_SERVICES if s != "state-worker"])
def test_dependent_waits_for_healthy_state_worker(compose_text: str, dependent: str) -> None:
    block = _service_block(compose_text, dependent)
    assert "depends_on:" in block
    assert "state-worker:" in block
    assert "condition: service_healthy" in block
    assert "STATE_WORKER_URL: http://state-worker:8000" in block


@pytest.mark.parametrize("service,suffixes", list(SERVICE_VOLUME_SUFFIXES.items()))
def test_volume_matrix(compose_text: str, service: str, suffixes: tuple[str, ...]) -> None:
    block = _service_block(compose_text, service)
    if not suffixes:
        assert "volumes:" not in block
        return
    assert "volumes:" in block
    for suffix in suffixes:
        container_path = SUFFIX_TO_CONTAINER[suffix]
        expected = f"${{BISHOP_DATA_ROOT}}/{suffix}:{container_path}"
        assert expected in block


def test_only_query_api_and_ui_expose_host_ports(compose_text: str) -> None:
    for service in BISHOP_SERVICES:
        block = _service_block(compose_text, service)
        if service in ("query-api", "ui"):
            assert "ports:" in block
        else:
            assert "ports:" not in block


def test_image_tags_use_milestone_convention(compose_text: str) -> None:
  milestone_tags: dict[str, str] = {
      "state-worker": "m1",
      "scraper": "m2",
      "pre-filter-worker": "m3",
      "batch-poller": "m5",
      "content-scraper": "m4",
      "enrichment-batcher": "m5",
      "vector-writer": "m6",
      "query-api": "m7",
      "ui": "m7",
  }
  for service in BISHOP_SERVICES:
      block = _service_block(compose_text, service)
      tag = milestone_tags.get(service, "m0")
      assert f"image: bishop/{service}:{tag}" in block


def test_ui_query_api_url_env(compose_text: str) -> None:
    """Falsifier: ui compose block lacks QUERY_API_URL for in-network query-api."""
    block = _service_block(compose_text, "ui")
    assert "QUERY_API_URL: http://query-api:8000" in block


def test_vector_writer_stop_grace_period(compose_text: str) -> None:
    """Falsifier: spec §6.2 G1 requires stop_grace_period on vector-writer."""
    block = _service_block(compose_text, "vector-writer")
    assert "stop_grace_period: 30s" in block


def test_repo_root_build_context_for_bishop_shared(compose_text: str) -> None:
    """Falsifier: per-service context would break T2/T3 COPY bishop_shared paths."""
    for service in BISHOP_SERVICES:
        block = _service_block(compose_text, service)
        assert "context: ." in block
        assert f"dockerfile: services/{service}/Dockerfile" in block
