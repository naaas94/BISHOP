"""Unit tests for state-worker configuration env overrides."""

import importlib
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_STATE_WORKER_ROOT = _REPO_ROOT / "services" / "state-worker"

for path in (_STATE_WORKER_ROOT, _REPO_ROOT):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)


def _reload_config() -> object:
    if "app.config" in sys.modules:
        return importlib.reload(sys.modules["app.config"])
    import app.config

    return app.config


def test_retry_max_attempts_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BISHOP_RETRY_MAX_ATTEMPTS", raising=False)
    config = _reload_config()
    assert config.RETRY_MAX_ATTEMPTS == 3


def test_sweep_and_stuck_threshold_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BISHOP_SWEEP_INTERVAL_SEC", raising=False)
    monkeypatch.delenv("BISHOP_STUCK_THRESHOLD_SEC", raising=False)
    config = _reload_config()
    assert config.SWEEP_INTERVAL_SEC == 300
    assert config.STUCK_THRESHOLD_SEC == 900


def test_config_env_round_trip(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BISHOP_RETRY_MAX_ATTEMPTS", "7")
    monkeypatch.setenv("BISHOP_SWEEP_INTERVAL_SEC", "120")
    monkeypatch.setenv("BISHOP_STUCK_THRESHOLD_SEC", "600")
    config = _reload_config()
    assert config.RETRY_MAX_ATTEMPTS == 7
    assert config.SWEEP_INTERVAL_SEC == 120
    assert config.STUCK_THRESHOLD_SEC == 600
