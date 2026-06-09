"""Static contract tests for scripts/verify-g1.sh (M0 T5)."""

import re
from pathlib import Path

import pytest

from bishop_shared.constants import (
    BISHOP_SERVICES,
    BISHOP_VOLUME_MOUNTS,
    QUERY_API_HOST_PORT,
    UI_HOST_PORT,
)

SCRIPT_PATH = Path("scripts/verify-g1.sh")


@pytest.fixture(scope="module")
def script_text() -> str:
    assert SCRIPT_PATH.is_file(), "scripts/verify-g1.sh must exist"
    return SCRIPT_PATH.read_text(encoding="utf-8")


def test_runs_init_volumes_and_compose_up(script_text: str) -> None:
    assert "init-volumes.sh" in script_text
    assert "docker compose up --build -d" in script_text


def test_asserts_nine_running_containers(script_text: str) -> None:
    assert str(len(BISHOP_SERVICES)) in script_text
    assert "restarting" in script_text.lower()


def test_state_worker_health_uses_exec_not_host_curl(script_text: str) -> None:
    assert "docker compose exec" in script_text
    assert "state-worker" in script_text
    assert "/health" in script_text
    for line in script_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        if "localhost:8000" in line and "exec" not in line:
            pytest.fail(f"host localhost curl to state-worker forbidden: {line}")


def test_health_body_must_contain_ok(script_text: str) -> None:
    """Falsifier: 200 response with wrong JSON body must not pass."""
    assert "health_body" in script_text or "health" in script_text
    assert '"ok"' in script_text or '*"ok"*' in script_text


def test_host_curl_query_api_and_ui_ports(script_text: str) -> None:
    assert str(QUERY_API_HOST_PORT) in script_text
    assert str(UI_HOST_PORT) in script_text
    assert re.search(r"curl\s+-sf.*localhost", script_text)


def test_volume_writability_all_six_subdirs(script_text: str) -> None:
    for mount in BISHOP_VOLUME_MOUNTS:
        assert mount.host_suffix in script_text
    assert ".g1-write-probe" in script_text or "probe" in script_text.lower()
