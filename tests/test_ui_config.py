"""Unit tests for UI QUERY_API_URL config (M7 T7)."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

from bishop_shared.constants import QUERY_API_HOST_PORT

_REPO_ROOT = Path(__file__).resolve().parent.parent
_UI_ROOT = _REPO_ROOT / "services" / "ui"


def _reload_ui_config(monkeypatch: pytest.MonkeyPatch) -> object:
    path_str = str(_UI_ROOT)
    inserted = False
    if path_str not in sys.path:
        sys.path.insert(0, path_str)
        inserted = True
    for name in list(sys.modules):
        if name == "app" or name.startswith("app."):
            del sys.modules[name]
    try:
        return importlib.import_module("app.config")
    finally:
        if inserted:
            sys.path.remove(path_str)


def test_query_api_url_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """Falsifier: host default must match QUERY_API_HOST_PORT (8080)."""
    monkeypatch.delenv("QUERY_API_URL", raising=False)
    config = _reload_ui_config(monkeypatch)
    assert config.QUERY_API_URL == f"http://localhost:{QUERY_API_HOST_PORT}"


def test_query_api_url_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QUERY_API_URL", "http://query-api:8000")
    config = _reload_ui_config(monkeypatch)
    assert config.QUERY_API_URL == "http://query-api:8000"
