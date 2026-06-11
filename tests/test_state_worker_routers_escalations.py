"""Unit tests for escalations router (T5)."""

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
from app.models.http import ManifestBatchEntryWire  # noqa: E402
from app.routers import escalations as escalations_router  # noqa: E402
from app.transitions import ingest_manifest_batch, record_failure  # noqa: E402

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
    app.include_router(escalations_router.router)
    with TestClient(app) as test_client:
        yield test_client


async def _seed_escalation(db_path: Path) -> None:
    await init_pool(str(db_path), size=1)
    async with get_db() as conn:
        await ingest_manifest_batch(
            conn,
            [
                ManifestBatchEntryWire(
                    source_id=_SOURCE,
                    source=SourceEnum.ARXIV,
                    url="https://arxiv.org/abs/2301.00001",
                    title="Escalated Paper",
                    abstract="An abstract",
                    published_at=_NOW,
                    domain=DomainEnum.PROFESSIONAL.value,
                )
            ],
            discovered_at=_NOW,
        )
        await record_failure(
            conn,
            source_id=_SOURCE,
            state_at_failure=ProcessingState.SCRAPE_QUEUED,
            error_class="HTTPStatusError",
            http_status=404,
            message="Not found",
            is_retriable=True,
        )
    await close_pool()


def test_escalations_empty_when_none_flagged(client: TestClient) -> None:
    response = client.get("/escalations")
    assert response.status_code == 200
    assert response.json() == {"entries": []}


def test_escalations_returns_flagged_entry_with_error_log(
    temp_db: Path, client: TestClient
) -> None:
    asyncio.run(_seed_escalation(temp_db))
    asyncio.run(init_pool(str(temp_db), size=2))

    response = client.get("/escalations")
    assert response.status_code == 200
    entries = response.json()["entries"]
    assert len(entries) == 1
    assert entries[0]["source_id"] == _SOURCE
    assert entries[0]["title"] == "Escalated Paper"
    assert entries[0]["processing_state"] == ProcessingState.ESCALATION_FLAGGED.value
    assert len(entries[0]["error_log"]) == 1
    assert entries[0]["error_log"][0]["message"] == "Not found"
