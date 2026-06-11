"""Unit tests for scraper-state routers (T5)."""

from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

_REPO_ROOT = Path(__file__).resolve().parent.parent
_STATE_WORKER_ROOT = _REPO_ROOT / "services" / "state-worker"

for path in (_STATE_WORKER_ROOT, _REPO_ROOT):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

from app.db import close_pool, init_pool, run_migrations  # noqa: E402
from app.enums import SourceEnum  # noqa: E402
from app.routers import scraper_state as scraper_state_router  # noqa: E402

_NOW = datetime(2026, 6, 11, 12, 0, 0, tzinfo=UTC)
_TS = datetime(2026, 6, 8, 10, 0, 0, tzinfo=UTC)


@pytest.fixture
def temp_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "bishop.db"
    run_migrations(str(db_path))
    return db_path


@pytest.fixture
def client(temp_db: Path) -> TestClient:
    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        await init_pool(str(temp_db), size=2)
        yield
        await close_pool()

    app = FastAPI(lifespan=lifespan)
    app.include_router(scraper_state_router.router)
    with TestClient(app) as test_client:
        yield test_client


def test_get_scraper_state_defaults_when_missing(client: TestClient) -> None:
    response = client.get(f"/scraper-state/{SourceEnum.ARXIV.value}")
    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == SourceEnum.ARXIV.value
    assert payload["last_successful_run_at"] is None
    assert payload["updated_at"] is not None


def test_post_then_get_scraper_state_round_trip(client: TestClient) -> None:
    post = client.post(
        f"/scraper-state/{SourceEnum.ARXIV.value}",
        json={"timestamp": _TS.isoformat().replace("+00:00", "Z")},
    )
    assert post.status_code == 204

    get = client.get(f"/scraper-state/{SourceEnum.ARXIV.value}")
    assert get.status_code == 200
    payload = get.json()
    assert payload["last_successful_run_at"] is not None
    assert payload["source"] == SourceEnum.ARXIV.value


def test_post_scraper_state_updates_existing_row(client: TestClient) -> None:
    first_ts = _TS
    second_ts = datetime(2026, 6, 9, 10, 0, 0, tzinfo=UTC)
    client.post(
        f"/scraper-state/{SourceEnum.ARXIV.value}",
        json={"timestamp": first_ts.isoformat().replace("+00:00", "Z")},
    )
    client.post(
        f"/scraper-state/{SourceEnum.ARXIV.value}",
        json={"timestamp": second_ts.isoformat().replace("+00:00", "Z")},
    )

    response = client.get(f"/scraper-state/{SourceEnum.ARXIV.value}")
    assert response.status_code == 200
    assert "2026-06-09" in response.json()["last_successful_run_at"]
