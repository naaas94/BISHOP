"""Static contract tests for scripts/verify-m7.sh (M7 T8)."""

from pathlib import Path

import pytest

SCRIPT_PATH = Path("scripts/verify-m7.sh")
G2_TEST_MODULES = (
    "tests/test_state_worker_contract.py",
    "tests/test_state_worker_health.py",
    "tests/test_constants.py",
)
M7_TEST_FRAGMENTS = (
    "tests/test_verify_m7.py",
    "tests/test_query_config.py",
    "tests/test_query_api_models.py",
    "tests/test_bm25_tokenize.py",
    "tests/test_query_api_bm25_reader.py",
    "tests/test_query_api_lancedb_reader.py",
    "tests/test_query_api_duckdb_reader.py",
    "tests/test_query_api_embedding.py",
    "tests/test_problem_shaped.py",
    "tests/test_rrf.py",
    "tests/test_query_api_routes_search.py",
    "tests/test_query_api_routes_recent.py",
    "tests/test_query_api_routes_entry.py",
    "tests/test_query_api_routes_batches.py",
    "tests/test_query_api_routes_escalations.py",
    "tests/test_query_api_cold_start.py",
    "tests/test_query_api_search_orchestrator.py",
    "tests/test_bishop_cli.py",
    "tests/test_bishop_cli_config.py",
    "tests/test_ui_config.py",
    "tests/test_ui_routes.py",
    "tests/test_m7_integration.py",
)


@pytest.fixture(scope="module")
def script_text() -> str:
    assert SCRIPT_PATH.is_file(), "scripts/verify-m7.sh must exist"
    return SCRIPT_PATH.read_text(encoding="utf-8")


def test_runs_g2_contract_pytest_modules(script_text: str) -> None:
    for module in G2_TEST_MODULES:
        assert module in script_text


def test_integration_run_in_isolated_subprocess(script_text: str) -> None:
    """Falsifier: integration runs after ui routes in same pytest process (app collision)."""
    integration_pos = script_text.index("tests/test_m7_integration.py")
    ui_routes_pos = script_text.index("tests/test_ui_routes.py")
    assert integration_pos < ui_routes_pos
    assert "integration gate (isolated subprocess" in script_text


def test_models_run_in_isolated_subprocess(script_text: str) -> None:
    """Falsifier: models run after bm25_tokenize in same pytest process (app collision)."""
    models_pos = script_text.index("tests/test_query_api_models.py")
    suite_pos = script_text.index('log "Running M7 unit pytest suite"')
    bm25_pos = script_text.index("tests/test_bm25_tokenize.py")
    assert models_pos < suite_pos
    assert models_pos < bm25_pos
    assert "pydantic models (isolated subprocess" in script_text


def test_runs_m7_pytest_modules(script_text: str) -> None:
    for fragment in M7_TEST_FRAGMENTS:
        assert fragment in script_text


def test_uses_pytest_verbose_short_traceback(script_text: str) -> None:
    assert "pytest" in script_text
    assert "-v" in script_text
    assert "--tb=short" in script_text


def test_does_not_require_docker(script_text: str) -> None:
    """Falsifier: M7 gate accidentally depends on Docker compose."""
    assert "docker compose" not in script_text
    assert "docker-compose" not in script_text


def test_exits_nonzero_on_failure(script_text: str) -> None:
    assert "set -euo pipefail" in script_text


def test_optional_strict_gates_behind_env_flag(script_text: str) -> None:
    """Falsifier: live G5 gate runs unconditionally in default verify path."""
    assert "BISHOP_M7_REQUIRE_GATES" in script_text
    assert "test_g5_quality_gate.py" in script_text
