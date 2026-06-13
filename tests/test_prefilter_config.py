"""Unit tests for pre-filter worker configuration (M3 T4)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_PREFILTER_ROOT = _REPO_ROOT / "services" / "pre-filter-worker"


def _load_config_module() -> ModuleType:
    path = _PREFILTER_ROOT / "app" / "config.py"
    spec = importlib.util.spec_from_file_location("prefilter_config_under_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_prefilter_batch_size_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BISHOP_PREFILTER_BATCH_SIZE", raising=False)
    config = _load_config_module()
    assert config.PREFILTER_BATCH_SIZE == 50


def test_prefilter_batch_size_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BISHOP_PREFILTER_BATCH_SIZE", "20")
    config = _load_config_module()
    assert config.PREFILTER_BATCH_SIZE == 20


def test_prefilter_poll_interval_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BISHOP_PREFILTER_POLL_INTERVAL_SEC", raising=False)
    config = _load_config_module()
    assert config.PREFILTER_POLL_INTERVAL_SEC == 60


def test_prefilter_poll_interval_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BISHOP_PREFILTER_POLL_INTERVAL_SEC", "120")
    config = _load_config_module()
    assert config.PREFILTER_POLL_INTERVAL_SEC == 120


def test_state_worker_url_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("STATE_WORKER_URL", raising=False)
    config = _load_config_module()
    assert config.STATE_WORKER_BASE_URL == "http://state-worker:8000"
