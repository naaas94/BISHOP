"""Unit tests for state-worker main assembly (T5)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

_REPO_ROOT = Path(__file__).resolve().parent.parent
_STATE_WORKER_ROOT = _REPO_ROOT / "services" / "state-worker"

for path in (_STATE_WORKER_ROOT, _REPO_ROOT):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

from app.main import app  # noqa: E402


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    db_path = tmp_path / "bishop.db"
    monkeypatch.setattr("app.db.SQLITE_DB_PATH", str(db_path))
    with TestClient(app) as test_client:
        yield test_client


def test_main_health_without_db_query(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_main_registers_spec_routes() -> None:
    """Falsifier: T3/T4/T5 routers are not mounted on the application."""
    routes = {route.path for route in app.routes if hasattr(route, "path")}
    expected = {
        "/health",
        "/manifest/batch",
        "/manifest/poll",
        "/entries/poll",
        "/manifest/pre-filter-results",
        "/entries/content",
        "/entries/enrichment-stage1-results",
        "/entries/enrichment-stage2-results",
        "/entries/indexed",
        "/entries/failed",
        "/entries/retry",
        "/batches",
        "/batches/{batch_id}",
        "/scraper-state/{source}",
        "/escalations",
    }
    assert expected.issubset(routes)
