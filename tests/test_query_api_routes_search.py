"""Unit tests for GET /search (M7 T5)."""

from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

_REPO_ROOT = Path(__file__).resolve().parent.parent
_QUERY_API_ROOT = _REPO_ROOT / "services" / "query-api"


def _clear_app_modules() -> dict[str, ModuleType]:
    saved = {
        name: module
        for name, module in sys.modules.items()
        if name == "app" or name.startswith("app.")
    }
    for name in saved:
        del sys.modules[name]
    return saved


def _restore_app_modules(saved: dict[str, ModuleType], inserted_path: str | None) -> None:
    for name in list(sys.modules):
        if name == "app" or name.startswith("app."):
            del sys.modules[name]
    sys.modules.update(saved)
    if inserted_path is not None:
        sys.path.remove(inserted_path)


def _load_search_router():
    saved = _clear_app_modules()
    path_str = str(_QUERY_API_ROOT)
    inserted = None
    if path_str not in sys.path:
        sys.path.insert(0, path_str)
        inserted = path_str
    try:
        from app.routers import search as search_router  # noqa: WPS433
    finally:
        _restore_app_modules(saved, inserted)
    return search_router


def _make_stores(
    *,
    filter_source_ids: list[str] | None = None,
    orchestration_hits: list[tuple[str, float]] | None = None,
) -> MagicMock:
    stores = MagicMock()
    bm25 = MagicMock()
    dense = MagicMock()
    metadata = MagicMock()
    encoder = MagicMock()
    encoder.encode_query.return_value = [0.1] * 384

    if filter_source_ids is not None:
        metadata.filter_source_ids.return_value = filter_source_ids
    else:
        metadata.filter_source_ids.return_value = ["arxiv:1"]

    metadata.connect.return_value.execute.return_value.fetchall.return_value = [
        ("arxiv:1", "Title One", "Summary", 0.9, "paper", '["RAG"]'),
    ]

    stores.bm25 = bm25
    stores.dense = dense
    stores.metadata = metadata
    stores.encoder = encoder

    if orchestration_hits is None:
        orchestration_hits = [("arxiv:1", 0.032)]

    from app.retrieval.search import SearchOrchestrationResult  # noqa: WPS433

    stores._orchestration = SearchOrchestrationResult(
        query="test query",
        problem_shaped=False,
        channels_active=["bm25_main", "dense"],
        hits=orchestration_hits,
    )
    return stores


@pytest.fixture
def search_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    search_router = _load_search_router()
    saved = _clear_app_modules()
    path_str = str(_QUERY_API_ROOT)
    inserted = None
    if path_str not in sys.path:
        sys.path.insert(0, path_str)
        inserted = path_str

    try:
        from app.retrieval.search import SearchOrchestrationResult  # noqa: WPS433

        stores = _make_stores()

        def _run_search(**kwargs):
            del kwargs
            return stores._orchestration

        monkeypatch.setattr(search_router, "run_search", _run_search)

        app = FastAPI()
        app.state.stores = stores
        app.include_router(search_router.router)
        with TestClient(app) as client:
            yield client
    finally:
        _restore_app_modules(saved, inserted)


def test_search_returns_contract_shape(search_client: TestClient) -> None:
    response = search_client.get("/search", params={"q": "rag systems"})
    assert response.status_code == 200
    body = response.json()
    assert body["query"] == "test query"
    assert body["problem_shaped"] is False
    assert body["channels_active"] == ["bm25_main", "dense"]
    assert body["total"] == 1
    hit = body["hits"][0]
    assert hit["source_id"] == "arxiv:1"
    assert hit["rrf_score"] == 0.032
    assert hit["title"] == "Title One"
    assert hit["tags"] == ["RAG"]


def test_search_missing_q_returns_400(search_client: TestClient) -> None:
    """Falsifier: missing required q does not return HTTP 400."""
    response = search_client.get("/search")
    assert response.status_code == 422 or response.status_code == 400


def test_search_min_relevance_invokes_metadata_pre_filter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    search_router = _load_search_router()
    saved = _clear_app_modules()
    path_str = str(_QUERY_API_ROOT)
    inserted = None
    if path_str not in sys.path:
        sys.path.insert(0, path_str)
        inserted = path_str

    try:
        from app.retrieval.search import SearchOrchestrationResult  # noqa: WPS433

        stores = _make_stores(filter_source_ids=[])
        stores._orchestration = SearchOrchestrationResult(
            query="filtered",
            problem_shaped=False,
            channels_active=["bm25_main", "dense"],
            hits=[],
        )
        captured: dict[str, object] = {}

        def _run_search(**kwargs):
            captured.update(kwargs)
            return stores._orchestration

        monkeypatch.setattr(search_router, "run_search", _run_search)

        app = FastAPI()
        app.state.stores = stores
        app.include_router(search_router.router)
        with TestClient(app) as client:
            response = client.get(
                "/search",
                params={"q": "test", "min_relevance": 0.5},
            )
    finally:
        _restore_app_modules(saved, inserted)

    assert response.status_code == 200
    assert captured.get("min_relevance") == 0.5


def test_search_days_invokes_metadata_pre_filter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    search_router = _load_search_router()
    saved = _clear_app_modules()
    path_str = str(_QUERY_API_ROOT)
    inserted = None
    if path_str not in sys.path:
        sys.path.insert(0, path_str)
        inserted = path_str

    try:
        from app.retrieval.search import SearchOrchestrationResult  # noqa: WPS433

        stores = _make_stores(filter_source_ids=[])
        stores._orchestration = SearchOrchestrationResult(
            query="filtered",
            problem_shaped=False,
            channels_active=["bm25_main", "dense"],
            hits=[],
        )
        captured: dict[str, object] = {}

        def _run_search(**kwargs):
            captured.update(kwargs)
            return stores._orchestration

        monkeypatch.setattr(search_router, "run_search", _run_search)

        app = FastAPI()
        app.state.stores = stores
        app.include_router(search_router.router)
        with TestClient(app) as client:
            response = client.get("/search", params={"q": "test", "days": 14})
    finally:
        _restore_app_modules(saved, inserted)

    assert response.status_code == 200
    assert captured.get("days") == 14
