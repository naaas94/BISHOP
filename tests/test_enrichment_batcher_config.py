"""Unit tests for enrichment-batcher configuration (M5 T3)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_ENRICHMENT_ROOT = _REPO_ROOT / "services" / "enrichment-batcher"


def _load_config_module() -> ModuleType:
    path = _ENRICHMENT_ROOT / "app" / "config.py"
    spec = importlib.util.spec_from_file_location("enrichment_batcher_config_under_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_enrichment_stage1_batch_size_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BISHOP_ENRICHMENT_STAGE1_BATCH_SIZE", raising=False)
    config = _load_config_module()
    assert config.ENRICHMENT_STAGE1_BATCH_SIZE == 10


def test_enrichment_stage1_batch_size_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BISHOP_ENRICHMENT_STAGE1_BATCH_SIZE", "5")
    config = _load_config_module()
    assert config.ENRICHMENT_STAGE1_BATCH_SIZE == 5


def test_enrichment_stage2_batch_size_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BISHOP_ENRICHMENT_STAGE2_BATCH_SIZE", raising=False)
    config = _load_config_module()
    assert config.ENRICHMENT_STAGE2_BATCH_SIZE == 10


def test_enrichment_stage2_batch_size_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BISHOP_ENRICHMENT_STAGE2_BATCH_SIZE", "7")
    config = _load_config_module()
    assert config.ENRICHMENT_STAGE2_BATCH_SIZE == 7


def test_enrichment_poll_interval_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BISHOP_ENRICHMENT_POLL_INTERVAL_SEC", raising=False)
    config = _load_config_module()
    assert config.ENRICHMENT_POLL_INTERVAL_SEC == 120


def test_enrichment_poll_interval_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BISHOP_ENRICHMENT_POLL_INTERVAL_SEC", "60")
    config = _load_config_module()
    assert config.ENRICHMENT_POLL_INTERVAL_SEC == 60


def test_state_worker_url_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("STATE_WORKER_URL", raising=False)
    config = _load_config_module()
    assert config.STATE_WORKER_BASE_URL == "http://state-worker:8000"
