"""Static contract tests for scripts/verify-m8.sh (M8 T8-bis)."""

from pathlib import Path

import pytest

SCRIPT_PATH = Path("scripts/verify-m8.sh")

SCRAPER_TEST_MODULES = (
    "tests/test_scraper_adapters_huggingface.py",
    "tests/test_scraper_adapters_paperswithcode.py",
    "tests/test_scraper_adapters_semantic_scholar.py",
    "tests/test_scraper_adapters_github.py",
    "tests/test_scraper_adapters_openreview.py",
    "tests/test_scraper_adapters_lesswrong.py",
    "tests/test_scraper_adapters.py",
    "tests/test_scraper_loop.py",
    "tests/test_scraper_backfill_chunking.py",
    "tests/test_scraper_config.py",
)

STATE_WORKER_TEST_MODULES = (
    "tests/test_state_worker_reading_status.py",
    "tests/test_state_worker_permanent_fail.py",
)

QUERY_UI_TEST_MODULES = (
    "tests/test_query_api_routes_entry_actions.py",
    "tests/test_ui_escalations.py",
    "tests/test_ui_explorer.py",
)

GATE_SELF_TEST_MODULES = (
    "tests/test_verify_m8.py",
)


@pytest.fixture(scope="module")
def script_text() -> str:
    assert SCRIPT_PATH.is_file(), "scripts/verify-m8.sh must exist"
    return SCRIPT_PATH.read_text(encoding="utf-8")


def test_runs_all_m8_adapter_and_loop_test_modules(script_text: str) -> None:
    for module in SCRAPER_TEST_MODULES:
        assert module in script_text


def test_runs_all_m8_state_worker_test_modules(script_text: str) -> None:
    for module in STATE_WORKER_TEST_MODULES:
        assert module in script_text


def test_runs_all_m8_query_ui_test_modules(script_text: str) -> None:
    for module in QUERY_UI_TEST_MODULES:
        assert module in script_text


def test_runs_verify_m8_self_test(script_text: str) -> None:
    for module in GATE_SELF_TEST_MODULES:
        assert module in script_text


def test_runs_g5_quality_gate_wrapper(script_text: str) -> None:
    assert "scripts/run-g5-quality-gate.sh" in script_text


def test_runs_g6_prefilter_gold_binding(script_text: str) -> None:
    assert "tests/test_g6_prefilter_gold.py" in script_text


def test_runs_g6_enrichment_structural_tests_only(script_text: str) -> None:
    assert "test_g6_enrichment_template_schema" in script_text
    assert "test_g6_enrichment_template_entry_slots" in script_text
    assert "test_g6_enrichment_manual_checklist" not in script_text


def test_does_not_export_g6_manual_flag(script_text: str) -> None:
    """Falsifier: verify-m8.sh must never set BISHOP_G6_MANUAL=1 (kept hook rejects
    would fail the all-true operator checklist)."""
    assert "BISHOP_G6_MANUAL=1" not in script_text


def test_does_not_rebuild_retired_v1_g6_scaffold(script_text: str) -> None:
    """Falsifier: must not reintroduce the retired v1.0 G6 CSV/20-item scaffold."""
    assert "run-g6-quality-sampling.sh" not in script_text
    assert "g6-sampling-template.md" not in script_text
    assert "test_g6_quality_sampling.py" not in script_text


def test_uses_pytest_verbose_short_traceback(script_text: str) -> None:
    assert "pytest" in script_text
    assert "-v" in script_text
    assert "--tb=short" in script_text


def test_exits_nonzero_on_failure(script_text: str) -> None:
    assert "set -euo pipefail" in script_text


def test_does_not_require_docker(script_text: str) -> None:
    """Falsifier: M8 gate accidentally depends on Docker compose."""
    assert "docker compose" not in script_text
    assert "docker-compose" not in script_text
