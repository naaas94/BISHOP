"""Unit tests for manifest ingest and poll routers (T3)."""

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
from app.enums import DomainEnum, ProcessingState, SourceEnum  # noqa: E402
from app.routers import manifest as manifest_router  # noqa: E402

_NOW = datetime(2026, 6, 11, 12, 0, 0, tzinfo=UTC)
_SOURCE = "arxiv:2301.00001"


def _batch_payload(source_id: str = _SOURCE) -> dict:
    return {
        "entries": [
            {
                "source_id": source_id,
                "source": SourceEnum.ARXIV.value,
                "url": "https://arxiv.org/abs/2301.00001",
                "title": "Test Paper",
                "abstract": "An abstract",
                "published_at": _NOW.isoformat().replace("+00:00", "Z"),
                "domain": DomainEnum.PROFESSIONAL.value,
            }
        ]
    }


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
    app.include_router(manifest_router.router)
    with TestClient(app) as test_client:
        yield test_client


def test_manifest_batch_insert_is_idempotent_on_source_id(client: TestClient) -> None:
    first = client.post("/manifest/batch", json=_batch_payload())
    second = client.post("/manifest/batch", json=_batch_payload())

    assert first.status_code == 200
    assert first.json() == {"inserted": 1, "skipped": 0}
    assert second.status_code == 200
    assert second.json() == {"inserted": 0, "skipped": 1}


def test_manifest_batch_new_rows_start_discovered(client: TestClient) -> None:
    response = client.post("/manifest/batch", json=_batch_payload())
    assert response.status_code == 200

    poll = client.get("/manifest/poll", params={"state": ProcessingState.DISCOVERED.value})
    body = poll.json()
    assert poll.status_code == 200
    assert body["claimed_count"] == 1
    assert body["transitioned_to"] == ProcessingState.RELEVANCE_QUEUED.value
    assert body["entries"][0]["processing_state"] == ProcessingState.RELEVANCE_QUEUED.value


def test_manifest_poll_double_poll_returns_empty_second_claim(client: TestClient) -> None:
    client.post("/manifest/batch", json=_batch_payload())

    first = client.get("/manifest/poll", params={"state": ProcessingState.DISCOVERED.value})
    second = client.get("/manifest/poll", params={"state": ProcessingState.DISCOVERED.value})

    assert first.status_code == 200
    assert first.json()["claimed_count"] == 1
    assert second.status_code == 200
    second_body = second.json()
    assert second_body["claimed_count"] == 0
    assert second_body["entries"] == []


def test_manifest_poll_invalid_state_returns_400(client: TestClient) -> None:
    response = client.get("/manifest/poll", params={"state": "SCRAPED"})
    assert response.status_code == 400
    assert response.json() == {"error": "invalid_poll_state", "state": "SCRAPED"}
