"""Static contract tests for scripts/verify-m3.sh (M3 T6)."""

from pathlib import Path

import pytest

SCRIPT_PATH = Path("scripts/verify-m3.sh")
G2_TEST_MODULES = (
    "tests/test_state_worker_contract.py",
    "tests/test_state_worker_health.py",
    "tests/test_constants.py",
)
M3_TEST_FRAGMENTS = (
    "tests/test_verify_m3.py",
    "tests/test_profile_renderer.py",
    "tests/test_prefilter_",
    "tests/test_batch_poller_",
    "tests/test_state_worker_batches_register.py",
    "tests/test_m3_integration.py",
)


@pytest.fixture(scope="module")
def script_text() -> str:
    assert SCRIPT_PATH.is_file(), "scripts/verify-m3.sh must exist"
    return SCRIPT_PATH.read_text(encoding="utf-8")


def test_runs_g2_contract_pytest_modules(script_text: str) -> None:
    for module in G2_TEST_MODULES:
        assert module in script_text


def test_invokes_g3_gate(script_text: str) -> None:
    assert "verify-g3.sh" in script_text


def test_runs_m3_pytest_modules(script_text: str) -> None:
    for fragment in M3_TEST_FRAGMENTS:
        assert fragment in script_text


def test_uses_pytest_verbose_short_traceback(script_text: str) -> None:
    assert "pytest" in script_text
    assert "-v" in script_text
    assert "--tb=short" in script_text


def test_does_not_require_docker(script_text: str) -> None:
    """Falsifier: M3 gate accidentally depends on Docker compose."""
    assert "docker compose" not in script_text
    assert "docker-compose" not in script_text


def test_exits_nonzero_on_failure(script_text: str) -> None:
    assert "set -euo pipefail" in script_text
