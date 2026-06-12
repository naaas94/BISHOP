"""Unit tests for scraper configuration env overrides (M2 T1)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

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
