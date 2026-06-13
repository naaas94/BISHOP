"""Static contract tests for scripts/verify-m4.sh (M4 T4)."""

from pathlib import Path

import pytest

SCRIPT_PATH = Path("scripts/verify-m4.sh")
G2_TEST_MODULES = (
    "tests/test_state_worker_contract.py",
    "tests/test_state_worker_health.py",
    "tests/test_constants.py",
)
M4_TEST_FRAGMENTS = (
    "tests/test_verify_m4.py",
    "tests/test_arxiv_fetch_content.py",
    "tests/test_content_scraper_",
    "tests/test_m4_provenance_contract.py",
    "tests/test_m4_integration.py",
)


@pytest.fixture(scope="module")
def script_text() -> str:
    assert SCRIPT_PATH.is_file(), "scripts/verify-m4.sh must exist"
    return SCRIPT_PATH.read_text(encoding="utf-8")


def test_runs_g2_contract_pytest_modules(script_text: str) -> None:
    for module in G2_TEST_MODULES:
        assert module in script_text


def test_runs_m4_pytest_modules(script_text: str) -> None:
    for fragment in M4_TEST_FRAGMENTS:
        assert fragment in script_text


def test_uses_pytest_verbose_short_traceback(script_text: str) -> None:
    assert "pytest" in script_text
    assert "-v" in script_text
    assert "--tb=short" in script_text


def test_does_not_require_docker(script_text: str) -> None:
    """Falsifier: M4 gate accidentally depends on Docker compose."""
    assert "docker compose" not in script_text
    assert "docker-compose" not in script_text


def test_exits_nonzero_on_failure(script_text: str) -> None:
    assert "set -euo pipefail" in script_text
