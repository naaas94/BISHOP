"""Unit tests for scraper configuration env overrides (M2 T1) and category gate config."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

from bishop_shared.source_config import (
    SourceCategoryConfig,
    category_matches,
    load_source_config,
    resolve_source_config_path,
)

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRAPER_ROOT = _REPO_ROOT / "services" / "scraper"


def _load_config_module() -> ModuleType:
    """Load scraper config without registering the scraper `app` package globally."""
    path = _SCRAPER_ROOT / "app" / "config.py"
    spec = importlib.util.spec_from_file_location("scraper_config_under_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_state_worker_url_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("STATE_WORKER_URL", raising=False)
    config = _load_config_module()
    assert config.STATE_WORKER_BASE_URL == "http://state-worker:8000"


def test_state_worker_url_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STATE_WORKER_URL", "http://localhost:9999")
    config = _load_config_module()
    assert config.STATE_WORKER_BASE_URL == "http://localhost:9999"


def test_arxiv_categories_default() -> None:
    config = _load_config_module()
    assert config.ARXIV_CATEGORIES == ("cs.AI", "cs.CL", "cs.LG")


def test_arxiv_backfill_window_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BISHOP_ARXIV_BACKFILL_WINDOW_DAYS", raising=False)
    config = _load_config_module()
    assert config.ARXIV_BACKFILL_WINDOW_DAYS == 7


def test_arxiv_backfill_window_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BISHOP_ARXIV_BACKFILL_WINDOW_DAYS", "60")
    config = _load_config_module()
    assert config.ARXIV_BACKFILL_WINDOW_DAYS == 60


def test_schedule_interval_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BISHOP_SCRAPER_SCHEDULE_INTERVAL_SEC", raising=False)
    config = _load_config_module()
    assert config.SCRAPER_SCHEDULE_INTERVAL_SEC == 21600


def test_schedule_interval_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BISHOP_SCRAPER_SCHEDULE_INTERVAL_SEC", "3600")
    config = _load_config_module()
    assert config.SCRAPER_SCHEDULE_INTERVAL_SEC == 3600


def _gate(**overrides: object) -> SourceCategoryConfig:
    payload: dict[str, object] = {"version": "test"}
    payload.update(overrides)
    return SourceCategoryConfig.model_validate(payload)


def test_category_matches_exact() -> None:
    assert category_matches("cs.CV", "cs.CV")
    assert not category_matches("cs.CL", "cs.CV")


def test_category_matches_wildcard() -> None:
    assert category_matches("cs.CV", "cs.*")
    assert category_matches("eess.AS", "eess.*")
    assert not category_matches("eess.AS", "cs.*")
    assert not category_matches("cshort.AS", "cs.*")


def test_gate_exact_include_allows_only_listed() -> None:
    gate = _gate(include_categories=["cs.AI", "cs.CL"])
    assert gate.allows("cs.AI")
    assert not gate.allows("cs.CV")


def test_gate_wildcard_include() -> None:
    gate = _gate(include_categories=["cs.*"])
    assert gate.allows("cs.RO")
    assert not gate.allows("eess.AS")


def test_gate_empty_include_allows_all() -> None:
    gate = _gate(include_categories=[])
    assert gate.allows("q-bio.NC")
    assert gate.allows("hep-ex")


def test_gate_exclude_overrides_include() -> None:
    gate = _gate(include_categories=["cs.*"], exclude_categories=["cs.CV"])
    assert gate.allows("cs.LG")
    assert not gate.allows("cs.CV")


def test_gate_allows_item_without_category_metadata() -> None:
    gate = _gate(include_categories=["cs.AI"], exclude_categories=["cs.*"])
    assert gate.allows(None)


def test_load_source_config_missing_file_returns_none(tmp_path: Path) -> None:
    assert load_source_config("arxiv", path=tmp_path / "absent.yaml") is None


def test_load_arxiv_source_config_defaults_to_measure_only() -> None:
    config = load_source_config("arxiv", path=resolve_source_config_path("arxiv"))
    assert config is not None
    assert config.enforce is False
    assert config.include_categories == []
    assert "cs.CV" in config.exclude_categories


def test_github_token_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test_token")
    config = _load_config_module()
    assert config.GITHUB_TOKEN == "ghp_test_token"


def test_github_token_default_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    config = _load_config_module()
    assert config.GITHUB_TOKEN is None


def test_semantic_scholar_key_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SEMANTIC_SCHOLAR_API_KEY", "ss-test-key")
    config = _load_config_module()
    assert config.SEMANTIC_SCHOLAR_API_KEY == "ss-test-key"


def test_semantic_scholar_key_default_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SEMANTIC_SCHOLAR_API_KEY", raising=False)
    config = _load_config_module()
    assert config.SEMANTIC_SCHOLAR_API_KEY is None


def test_backfill_enabled_default_false(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BISHOP_BACKFILL_ENABLED", raising=False)
    config = _load_config_module()
    assert config.BISHOP_BACKFILL_ENABLED is False


def test_backfill_enabled_env_override_true(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BISHOP_BACKFILL_ENABLED", "1")
    config = _load_config_module()
    assert config.BISHOP_BACKFILL_ENABLED is True


def test_backfill_enabled_env_override_false_string(monkeypatch: pytest.MonkeyPatch) -> None:
    """Falsifier: a falsy-looking string must not coerce to True via bare truthiness."""
    monkeypatch.setenv("BISHOP_BACKFILL_ENABLED", "0")
    config = _load_config_module()
    assert config.BISHOP_BACKFILL_ENABLED is False


def test_backfill_chunk_days_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BISHOP_BACKFILL_CHUNK_DAYS", raising=False)
    config = _load_config_module()
    assert config.BISHOP_BACKFILL_CHUNK_DAYS == 7


def test_backfill_chunk_days_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BISHOP_BACKFILL_CHUNK_DAYS", "10")
    config = _load_config_module()
    assert config.BISHOP_BACKFILL_CHUNK_DAYS == 10


def test_backfill_inter_chunk_delay_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BISHOP_BACKFILL_INTER_CHUNK_DELAY_SEC", raising=False)
    config = _load_config_module()
    assert config.BISHOP_BACKFILL_INTER_CHUNK_DELAY_SEC == 300


def test_backfill_inter_chunk_delay_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BISHOP_BACKFILL_INTER_CHUNK_DELAY_SEC", "60")
    config = _load_config_module()
    assert config.BISHOP_BACKFILL_INTER_CHUNK_DELAY_SEC == 60
