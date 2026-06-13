"""Unit tests for batch-poller config (M3 T5)."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_BATCH_POLLER_ROOT = _REPO_ROOT / "services" / "batch-poller"


def _load_config_module(monkeypatch: pytest.MonkeyPatch, *, clear_env: bool = True):
    if clear_env:
        monkeypatch.delenv("BISHOP_BATCH_POLL_INTERVAL_SEC", raising=False)
        monkeypatch.delenv("BISHOP_BATCH_TIMEOUT_HOURS", raising=False)
        monkeypatch.delenv("STATE_WORKER_URL", raising=False)

    saved = {name: mod for name, mod in sys.modules.items() if name == "app" or name.startswith("app.")}
    for name in saved:
        del sys.modules[name]

    path_state: list[str] = []
    for path_str in (str(_BATCH_POLLER_ROOT), str(_REPO_ROOT)):
        if path_str not in sys.path:
            sys.path.insert(0, path_str)
            path_state.append(path_str)

    try:
        if "app.config" in sys.modules:
            return importlib.reload(sys.modules["app.config"])
        import app.config as config_mod  # noqa: WPS433

        return importlib.reload(config_mod)
    finally:
        for name in list(sys.modules):
            if name == "app" or name.startswith("app."):
                del sys.modules[name]
        sys.modules.update(saved)
        for path_str in path_state:
            sys.path.remove(path_str)


def test_batch_poll_interval_default(monkeypatch: pytest.MonkeyPatch) -> None:
    config = _load_config_module(monkeypatch)
    assert config.BATCH_POLL_INTERVAL_SEC == 120


def test_batch_timeout_hours_default(monkeypatch: pytest.MonkeyPatch) -> None:
    config = _load_config_module(monkeypatch)
    assert config.BATCH_TIMEOUT_HOURS == 48


def test_batch_poll_interval_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BISHOP_BATCH_POLL_INTERVAL_SEC", "90")
    config = _load_config_module(monkeypatch, clear_env=False)
    assert config.BATCH_POLL_INTERVAL_SEC == 90


def test_batch_timeout_hours_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BISHOP_BATCH_TIMEOUT_HOURS", "24")
    config = _load_config_module(monkeypatch, clear_env=False)
    assert config.BATCH_TIMEOUT_HOURS == 24
