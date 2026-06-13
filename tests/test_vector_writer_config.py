"""Unit tests for vector-writer config (M6 T5 contract surface)."""

from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_VECTOR_WRITER_ROOT = _REPO_ROOT / "services" / "vector-writer"


def _load_config_module() -> ModuleType:
    saved_app_modules = {
        name: module
        for name, module in sys.modules.items()
        if name == "app" or name.startswith("app.")
    }
    for name in saved_app_modules:
        del sys.modules[name]

    path_str = str(_VECTOR_WRITER_ROOT)
    inserted = False
    if path_str not in sys.path:
        sys.path.insert(0, path_str)
        inserted = True

    try:
        import app.config as config_mod  # noqa: WPS433
    finally:
        for name in list(sys.modules):
            if name == "app" or name.startswith("app."):
                del sys.modules[name]
        sys.modules.update(saved_app_modules)
        if inserted:
            sys.path.remove(path_str)

    return config_mod


def test_vector_write_poll_state_is_vector_write_queued() -> None:
    config = _load_config_module()
    assert config.VECTOR_WRITE_POLL_STATE == "VECTOR_WRITE_QUEUED"


def test_vector_write_batch_size_default_and_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BISHOP_VECTOR_WRITE_BATCH_SIZE", raising=False)
    config = _load_config_module()
    assert config.VECTOR_WRITE_BATCH_SIZE == 10

    monkeypatch.setenv("BISHOP_VECTOR_WRITE_BATCH_SIZE", "25")
    config = _load_config_module()
    assert config.VECTOR_WRITE_BATCH_SIZE == 25


def test_vector_write_poll_interval_default_and_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BISHOP_VECTOR_WRITE_POLL_INTERVAL_SEC", raising=False)
    config = _load_config_module()
    assert config.VECTOR_WRITE_POLL_INTERVAL_SEC == 120

    monkeypatch.setenv("BISHOP_VECTOR_WRITE_POLL_INTERVAL_SEC", "60")
    config = _load_config_module()
    assert config.VECTOR_WRITE_POLL_INTERVAL_SEC == 60
