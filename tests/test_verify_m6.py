"""Static contract tests for scripts/verify-m6.sh (M6 T6)."""

from pathlib import Path

import pytest

SCRIPT_PATH = Path("scripts/verify-m6.sh")
G2_TEST_MODULES = (
    "tests/test_state_worker_contract.py",
    "tests/test_state_worker_health.py",
    "tests/test_constants.py",
)
M6_TEST_FRAGMENTS = (
    "tests/test_verify_m6.py",
    "tests/test_indexing_config.py",
    "tests/test_atomic_persist.py",
    "tests/test_lancedb_store.py",
    "tests/test_bm25_store.py",
    "tests/test_duckdb_mirror.py",
    "tests/test_vector_writer_config.py",
    "tests/test_vector_writer_models.py",
    "tests/test_vector_writer_embedding.py",
    "tests/test_vector_writer_index_entry.py",
    "tests/test_vector_writer_loop.py",
    "tests/test_bm25_lock_contention.py",
    "tests/test_duckdb_concurrent_read.py",
    "tests/test_g5_quality_gate.py",
    "tests/test_m6_integration.py",
)


@pytest.fixture(scope="module")
def script_text() -> str:
    assert SCRIPT_PATH.is_file(), "scripts/verify-m6.sh must exist"
    return SCRIPT_PATH.read_text(encoding="utf-8")


def test_runs_g2_contract_pytest_modules(script_text: str) -> None:
    for module in G2_TEST_MODULES:
        assert module in script_text


def test_runs_m6_pytest_modules(script_text: str) -> None:
    for fragment in M6_TEST_FRAGMENTS:
        assert fragment in script_text


def test_uses_pytest_verbose_short_traceback(script_text: str) -> None:
    assert "pytest" in script_text
    assert "-v" in script_text
    assert "--tb=short" in script_text


def test_excludes_heavy_g5_live_gate(script_text: str) -> None:
    """Falsifier: verify-m6 must not run live SentenceTransformer gate by default."""
    assert '-m "not heavy"' in script_text or "-m 'not heavy'" in script_text


def test_does_not_require_docker(script_text: str) -> None:
    assert "docker compose" not in script_text
    assert "docker-compose" not in script_text


def test_exits_nonzero_on_failure(script_text: str) -> None:
    assert "set -euo pipefail" in script_text
