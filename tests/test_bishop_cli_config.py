"""Unit tests for bishop CLI config (M7 T6)."""

from __future__ import annotations

import importlib
import sys

import pytest


def _reload_config() -> object:
    sys.modules.pop("bishop_cli.config", None)
    return importlib.import_module("bishop_cli.config")


def test_query_api_base_url_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("QUERY_API_BASE_URL", raising=False)
    config = _reload_config()
    assert config.QUERY_API_BASE_URL == "http://localhost:8080"


def test_query_api_base_url_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QUERY_API_BASE_URL", "http://query-api:8000")
    config = _reload_config()
    assert config.QUERY_API_BASE_URL == "http://query-api:8000"
