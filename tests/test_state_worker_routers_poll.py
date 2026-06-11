"""Unit tests for entry poll router (T3)."""

from __future__ import annotations

import asyncio
import sys
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

import aiosqlite
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
from app.models.http import (  # noqa: E402
    ManifestBatchEntryWire,
    PreFilterResultEntryWire,
)
from app.routers import poll as poll_router  # noqa: E402
from app.transitions import (  # noqa: E402
    apply_pre_filter_results,
    claim_entries_poll,
    claim_manifest_poll,
    create_entry_from_content,
    ingest_manifest_batch,
)

_NOW = datetime(2026, 6, 11, 12, 0, 0, tzinfo=UTC)
_SOURCE = "arxiv:2301.00001"
_CONTENT = "full paper body text for vector-writer omission test"


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
    app.include_router(poll_router.router)
    with TestClient(app) as test_client:
        yield test_client


async def _seed_vector_write_queued(db_path: Path, source_id: str = _SOURCE) -> None:
    conn = await aiosqlite.connect(str(db_path))
    await conn.execute("PRAGMA journal_mode=WAL")
    try:
        await ingest_manifest_batch(
            conn,
            [
                ManifestBatchEntryWire(
                    source_id=source_id,
                    source=SourceEnum.ARXIV,
                    url="https://arxiv.org/abs/2301.00001",
                    title="Test Paper",
                    abstract="An abstract",
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
            "1.0.0",
            [
                PreFilterResultEntryWire(
                    source_id=source_id,
                    decision=1,
                    pre_filter_rationale="Relevant",
                )
            ],
        )
        await claim_manifest_poll(conn, ProcessingState.RELEVANCE_PASSED)
        await create_entry_from_content(conn, source_id, _CONTENT, ingested_at=_NOW)
        await conn.execute(
            "UPDATE entries SET processing_state = ? WHERE source_id = ?",
            (ProcessingState.VECTOR_WRITE_QUEUED.value, source_id),
        )
        await conn.execute(
            "UPDATE manifest SET processing_state = ? WHERE source_id = ?",
            (ProcessingState.VECTOR_WRITE_QUEUED.value, source_id),
        )
        await conn.commit()
    finally:
        await conn.close()


async def _seed_scraped_entry(db_path: Path, source_id: str = _SOURCE) -> None:
    conn = await aiosqlite.connect(str(db_path))
    await conn.execute("PRAGMA journal_mode=WAL")
    try:
        await ingest_manifest_batch(
            conn,
            [
                ManifestBatchEntryWire(
                    source_id=source_id,
                    source=SourceEnum.ARXIV,
                    url="https://arxiv.org/abs/2301.00001",
                    title="Test Paper",
                    domain=DomainEnum.PROFESSIONAL.value,
                )
            ],
            discovered_at=_NOW,
        )
        await claim_manifest_poll(conn, ProcessingState.DISCOVERED)
        await apply_pre_filter_results(
            conn,
            "batch-1",
            "1.0.0",
            [
                PreFilterResultEntryWire(
                    source_id=source_id,
                    decision=1,
                    pre_filter_rationale="Relevant",
                )
            ],
        )
        await claim_manifest_poll(conn, ProcessingState.RELEVANCE_PASSED)
        await create_entry_from_content(conn, source_id, _CONTENT, ingested_at=_NOW)
    finally:
        await conn.close()


@pytest.fixture
def vector_write_db(temp_db: Path) -> Path:
    asyncio.run(_seed_vector_write_queued(temp_db))
    return temp_db


def test_entries_poll_vector_write_queued_omits_content_raw(
    vector_write_db: Path,
) -> None:
    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        await init_pool(str(vector_write_db), size=2)
        yield
        await close_pool()

    app = FastAPI(lifespan=lifespan)
    app.include_router(poll_router.router)
    with TestClient(app) as client:
        response = client.get(
            "/entries/poll",
            params={"state": ProcessingState.VECTOR_WRITE_QUEUED.value},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["claimed_count"] == 1
    assert body["transitioned_to"] is None
    assert len(body["entries"]) == 1
    assert "content_raw" not in body["entries"][0]
    assert body["entries"][0]["source_id"] == _SOURCE


def test_entries_poll_scraped_includes_content_raw(client: TestClient, temp_db: Path) -> None:
    asyncio.run(_seed_scraped_entry(temp_db))

    response = client.get(
        "/entries/poll",
        params={"state": ProcessingState.SCRAPED.value},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["claimed_count"] == 1
    assert body["transitioned_to"] == ProcessingState.ENRICHMENT_STAGE1_QUEUED.value
    assert body["entries"][0]["content_raw"] == _CONTENT


def test_entries_poll_vector_write_queued_allows_repeat_poll(client: TestClient, temp_db: Path) -> None:
    """No claim on VECTOR_WRITE_QUEUED — second poll still returns the entry."""
    asyncio.run(_seed_vector_write_queued(temp_db))

    first = client.get(
        "/entries/poll",
        params={"state": ProcessingState.VECTOR_WRITE_QUEUED.value},
    )
    second = client.get(
        "/entries/poll",
        params={"state": ProcessingState.VECTOR_WRITE_QUEUED.value},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["claimed_count"] == 1
    assert second.json()["claimed_count"] == 1
    assert first.json()["transitioned_to"] is None
    assert second.json()["transitioned_to"] is None


def test_entries_poll_invalid_state_returns_400(client: TestClient) -> None:
    response = client.get("/entries/poll", params={"state": "DISCOVERED"})
    assert response.status_code == 400
    assert response.json() == {"error": "invalid_poll_state", "state": "DISCOVERED"}
