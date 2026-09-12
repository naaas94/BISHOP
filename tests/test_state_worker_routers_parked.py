"""Unit tests for the parked inbox router."""

from __future__ import annotations

import asyncio
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

from app.db import close_pool, get_db, init_pool, run_migrations  # noqa: E402
from app.enums import DomainEnum, ProcessingState, SourceEnum  # noqa: E402
from app.models.http import ManifestBatchEntryWire, PreFilterResultEntryWire  # noqa: E402
from app.routers import parked as parked_router  # noqa: E402
from app.transitions import (  # noqa: E402
    apply_pre_filter_results,
    claim_manifest_poll,
    ingest_manifest_batch,
)

_NOW = datetime(2026, 6, 11, 12, 0, 0, tzinfo=UTC)
_SOURCE = "arxiv:2301.00001"


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
    app.include_router(parked_router.router)
    with TestClient(app) as test_client:
        yield test_client


async def _park_one(db_path: Path) -> None:
    await init_pool(str(db_path), size=1)
    async with get_db() as conn:
        await ingest_manifest_batch(
            conn,
            [
                ManifestBatchEntryWire(
                    source_id=_SOURCE,
                    source=SourceEnum.ARXIV,
                    url="https://arxiv.org/abs/2301.00001",
                    title="Parked Paper",
                    abstract="An abstract worth skimming",
                    published_at=_NOW,
                    domain=DomainEnum.PROFESSIONAL.value,
                )
            ],
            discovered_at=_NOW,
        )
        await claim_manifest_poll(conn, ProcessingState.DISCOVERED)
        await apply_pre_filter_results(
            conn,
            "batch-1",
            "1.2.0-soft-launch",
            [
                PreFilterResultEntryWire(
                    source_id=_SOURCE,
                    decision=1,
                    pre_filter_rationale="Interesting, not a working reference.",
                    pre_filter_tier="peripheral",
                )
            ],
        )
    await close_pool()


def test_parked_empty_when_none(client: TestClient) -> None:
    response = client.get("/parked")
    assert response.status_code == 200
    assert response.json() == {"entries": []}


def test_parked_lists_and_promotes(client: TestClient, temp_db: Path) -> None:
    asyncio.run(_park_one(temp_db))
    asyncio.run(init_pool(str(temp_db), size=2))
    listed = client.get("/parked")
    assert listed.status_code == 200
    body = listed.json()
    assert len(body["entries"]) == 1
    assert body["entries"][0]["source_id"] == _SOURCE
    assert body["entries"][0]["processing_state"] == ProcessingState.RELEVANCE_PARKED.value
    assert body["entries"][0]["abstract"] == "An abstract worth skimming"

    promoted = client.post("/parked/promote", json={"source_id": _SOURCE})
    assert promoted.status_code == 200
    assert promoted.json() == {
        "source_id": _SOURCE,
        "processing_state": ProcessingState.RELEVANCE_PASSED.value,
    }
    after = client.get("/parked")
    assert after.json() == {"entries": []}


def test_promote_non_parked_is_conflict(client: TestClient, temp_db: Path) -> None:
    asyncio.run(_park_one(temp_db))
    asyncio.run(init_pool(str(temp_db), size=2))
    client.post("/parked/promote", json={"source_id": _SOURCE})
    again = client.post("/parked/promote", json={"source_id": _SOURCE})
    assert again.status_code == 409
    assert again.json()["error"] == "invalid_transition"
