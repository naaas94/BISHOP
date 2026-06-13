"""Unit tests for GET /recent (M7 T5)."""

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


def _load_recent_router():
    saved = _clear_app_modules()
    path_str = str(_QUERY_API_ROOT)
    inserted = None
    if path_str not in sys.path:
        sys.path.insert(0, path_str)
        inserted = path_str
    try:
        from app.routers import recent as recent_router  # noqa: WPS433
        from app.stores.duckdb_reader import RecentEntry  # noqa: WPS433
    finally:
        _restore_app_modules(saved, inserted)
    return recent_router, RecentEntry


@pytest.fixture
def recent_client() -> TestClient:
    recent_router, RecentEntry = _load_recent_router()
    saved = _clear_app_modules()
    path_str = str(_QUERY_API_ROOT)
    inserted = None
    if path_str not in sys.path:
        sys.path.insert(0, path_str)
        inserted = path_str

    try:
        stores = MagicMock()
        stores.metadata.recent.return_value = [
            RecentEntry(
                source_id="arxiv:1",
                source="arxiv",
                title="Recent Paper",
                ingested_at="2026-06-13T00:00:00+00:00",
                domain="professional",
                entry_type="paper",
                relevance_score=0.8,
                summary="Summary text",
            )
        ]

        app = FastAPI()
        app.state.stores = stores
        app.include_router(recent_router.router)
        with TestClient(app) as client:
            yield client
    finally:
        _restore_app_modules(saved, inserted)


def test_recent_defaults_days_to_seven(recent_client: TestClient) -> None:
    response = recent_client.get("/recent")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["entries"][0]["source_id"] == "arxiv:1"
    assert body["entries"][0]["title"] == "Recent Paper"


def test_recent_passes_filters(recent_client: TestClient) -> None:
    response = recent_client.get(
        "/recent",
        params={"source": "arxiv", "days": 3, "domain": "professional"},
    )
    assert response.status_code == 200
