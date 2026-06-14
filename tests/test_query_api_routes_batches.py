"""Unit tests for batch proxy routes (M7 T5)."""

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


def _load_batches_router():
    saved = _clear_app_modules()
    path_str = str(_QUERY_API_ROOT)
    inserted = None
    if path_str not in sys.path:
        sys.path.insert(0, path_str)
        inserted = path_str
    try:
        from app.routers import batches as batches_router  # noqa: WPS433
    finally:
        _restore_app_modules(saved, inserted)
    return batches_router


@pytest.fixture
def batches_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    batches_router = _load_batches_router()
    saved = _clear_app_modules()
    path_str = str(_QUERY_API_ROOT)
    inserted = None
    if path_str not in sys.path:
        sys.path.insert(0, path_str)
        inserted = path_str

    try:
        import app.config as config_mod  # noqa: WPS433

        monkeypatch.setattr(
            config_mod,
            "STATE_WORKER_BASE_URL",
            "http://state-worker.test:8000",
        )

        def _fake_get(path: str, *, query: str = ""):
            if path == "/batches":
                assert query == "status=complete"
                return 200, {"batches": [{"batch_id": "b-1"}]}
            if path == "/batches/b-1":
                return 200, {
                    "batch": {
                        "batch_id": "b-1",
                        "source_ids": ["arxiv:1", "arxiv:2"],
                    }
                }
            return 404, None

        monkeypatch.setattr(batches_router, "_state_worker_get", _fake_get)

        stores = MagicMock()
        from app.stores.duckdb_reader import EntryMetadataRow  # noqa: WPS433

        stores.metadata.fetch_top_entry_metadata.return_value = [
            EntryMetadataRow(
                source_id="arxiv:1",
                title="Top Paper",
                summary="Sum",
                relevance_score=0.95,
                entry_type="paper",
                tags=["AI"],
            ),
        ]

        app = FastAPI()
        app.state.stores = stores
        app.include_router(batches_router.router)
        with TestClient(app) as client:
            yield client
    finally:
        _restore_app_modules(saved, inserted)


def test_batches_list_proxies_state_worker(batches_client: TestClient) -> None:
    response = batches_client.get("/batches", params={"status": "complete"})
    assert response.status_code == 200
    assert response.json()["batches"][0]["batch_id"] == "b-1"


def test_batch_detail_enriches_top_entries(batches_client: TestClient) -> None:
    response = batches_client.get("/batches/b-1")
    assert response.status_code == 200
    body = response.json()
    assert body["batch"]["batch_id"] == "b-1"
    assert len(body["entries"]) == 1
    assert body["entries"][0]["source_id"] == "arxiv:1"
    assert body["entries"][0]["relevance_score"] == 0.95


def test_batches_upstream_error(monkeypatch: pytest.MonkeyPatch) -> None:
    batches_router = _load_batches_router()
    saved = _clear_app_modules()
    path_str = str(_QUERY_API_ROOT)
    inserted = None
    if path_str not in sys.path:
        sys.path.insert(0, path_str)
        inserted = path_str

    try:
        monkeypatch.setattr(
            batches_router,
            "_state_worker_get",
            lambda path, query="": (503, None),
        )
        app = FastAPI()
        app.state.stores = MagicMock()
        app.include_router(batches_router.router)
        with TestClient(app) as client:
            response = client.get("/batches", params={"status": "complete"})
    finally:
        _restore_app_modules(saved, inserted)

    assert response.status_code == 503
    assert response.json()["error"] == "upstream_error"
