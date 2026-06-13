"""Unit tests for bishop_shared.query_config (M7 T1 contract surface)."""

from __future__ import annotations

import pytest

from bishop_shared.enums import DomainEnum
from bishop_shared.query_config import (
    BM25_RELOAD_INTERVAL_SEC,
    DEFAULT_SEARCH_DOMAIN,
    RRF_K,
)


def test_rrf_k_pinned() -> None:
    assert RRF_K == 60


def test_bm25_reload_interval_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BISHOP_BM25_RELOAD_INTERVAL_SEC", raising=False)
    import importlib

    import bishop_shared.query_config as query_config

    importlib.reload(query_config)
    assert query_config.BM25_RELOAD_INTERVAL_SEC == 300

    monkeypatch.setenv("BISHOP_BM25_RELOAD_INTERVAL_SEC", "120")
    importlib.reload(query_config)
    assert query_config.BM25_RELOAD_INTERVAL_SEC == 120

    monkeypatch.delenv("BISHOP_BM25_RELOAD_INTERVAL_SEC", raising=False)
    importlib.reload(query_config)


def test_default_search_domain() -> None:
    assert DEFAULT_SEARCH_DOMAIN == "professional"
    assert DEFAULT_SEARCH_DOMAIN == DomainEnum.PROFESSIONAL.value
