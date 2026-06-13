"""Unit tests for content-scraper configuration (M4 T2)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_CONTENT_SCRAPER_ROOT = _REPO_ROOT / "services" / "content-scraper"


def _load_config_module() -> ModuleType:
    path = _CONTENT_SCRAPER_ROOT / "app" / "config.py"
    spec = importlib.util.spec_from_file_location("content_scraper_config_under_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_content_scrape_batch_size_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BISHOP_CONTENT_SCRAPE_BATCH_SIZE", raising=False)
    config = _load_config_module()
    assert config.CONTENT_SCRAPE_BATCH_SIZE == 10


def test_content_scrape_batch_size_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BISHOP_CONTENT_SCRAPE_BATCH_SIZE", "25")
    config = _load_config_module()
    assert config.CONTENT_SCRAPE_BATCH_SIZE == 25


def test_content_scrape_poll_interval_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BISHOP_CONTENT_SCRAPE_POLL_INTERVAL_SEC", raising=False)
    config = _load_config_module()
    assert config.CONTENT_SCRAPE_POLL_INTERVAL_SEC == 120


def test_content_scrape_poll_interval_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BISHOP_CONTENT_SCRAPE_POLL_INTERVAL_SEC", "60")
    config = _load_config_module()
    assert config.CONTENT_SCRAPE_POLL_INTERVAL_SEC == 60


def test_state_worker_url_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("STATE_WORKER_URL", raising=False)
    config = _load_config_module()
    assert config.STATE_WORKER_BASE_URL == "http://state-worker:8000"


def test_log_level_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    config = _load_config_module()
    assert config.LOG_LEVEL == "INFO"
