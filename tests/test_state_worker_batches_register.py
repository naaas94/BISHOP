"""Unit tests for batch registration, patch, and timeout routes (T3)."""

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
from app.enums import (  # noqa: E402
    BatchStatusEnum,
    BatchTypeEnum,
    DomainEnum,
    ProcessingState,
    SourceEnum,
)
from app.models.domain import BatchRecord  # noqa: E402
from app.models.http import ManifestBatchEntryWire  # noqa: E402
from app.routers import batches as batches_router  # noqa: E402
from app.transitions import claim_manifest_poll, ingest_manifest_batch  # noqa: E402

_NOW = datetime(2026, 6, 13, 12, 0, 0, tzinfo=UTC)
_BATCH_ID = "batch-uuid-register-1"
_SOURCE_A = "arxiv:2301.00001"
_SOURCE_B = "arxiv:2301.00002"
_PROFILE_HASH = "deadbeef" * 8


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
    app.include_router(batches_router.router)
    with TestClient(app) as test_client:
        yield test_client


def _register_payload(
    *,
    batch_id: str = _BATCH_ID,
    source_ids: list[str] | None = None,
) -> dict:
    return {
        "batch_id": batch_id,
        "batch_type": BatchTypeEnum.PRE_FILTER.value,
        "domain": DomainEnum.PROFESSIONAL.value,
        "profile_version": "1.0.0",
        "profile_render_hash": _PROFILE_HASH,
        "source_ids": source_ids if source_ids is not None else [_SOURCE_A, _SOURCE_B],
        "external_batch_id": "anthropic-batch-ext-1",
        "entry_count": 2,
    }


async def _seed_discovered_only(db_path: Path, source_ids: list[str]) -> None:
    async with aiosqlite.connect(db_path) as conn:
        await conn.execute("PRAGMA journal_mode=WAL")
        entries = [
            ManifestBatchEntryWire(
                source_id=source_id,
                source=SourceEnum.ARXIV,
                url=f"https://arxiv.org/abs/{source_id}",
                title=f"Paper {source_id}",
                abstract="An abstract",
                published_at=_NOW,
                domain=DomainEnum.PROFESSIONAL.value,
            )
            for source_id in source_ids
        ]
        await ingest_manifest_batch(conn, entries, discovered_at=_NOW)
        await conn.commit()


async def _seed_relevance_queued(db_path: Path, source_ids: list[str]) -> None:
    async with aiosqlite.connect(db_path) as conn:
        await conn.execute("PRAGMA journal_mode=WAL")
        entries = [
            ManifestBatchEntryWire(
                source_id=source_id,
                source=SourceEnum.ARXIV,
                url=f"https://arxiv.org/abs/{source_id}",
                title=f"Paper {source_id}",
                abstract="An abstract",
                published_at=_NOW,
                domain=DomainEnum.PROFESSIONAL.value,
            )
            for source_id in source_ids
        ]
        await ingest_manifest_batch(conn, entries, discovered_at=_NOW)
        await claim_manifest_poll(conn, ProcessingState.DISCOVERED)
        await conn.commit()


def test_batch_record_source_ids_round_trip() -> None:
    """Contract: BatchRecord.source_ids JSON list column round-trips."""
    original = BatchRecord(
        batch_id=_BATCH_ID,
        batch_type=BatchTypeEnum.PRE_FILTER,
        domain=DomainEnum.PROFESSIONAL,
        profile_version="1.0.0",
        profile_render_hash=_PROFILE_HASH,
        status=BatchStatusEnum.SUBMITTED,
        created_at=_NOW,
        entry_count=2,
        passed_count=0,
        failed_count=0,
        source_ids=[_SOURCE_A, _SOURCE_B],
    )
    row = original.to_db_row()
    assert isinstance(row["source_ids"], str)
    restored = BatchRecord.from_db_row({**row, "created_at": _NOW})
    assert restored.source_ids == [_SOURCE_A, _SOURCE_B]


def test_post_batches_registers_submitted(client: TestClient, temp_db: Path) -> None:
    asyncio.run(_seed_relevance_queued(temp_db, [_SOURCE_A, _SOURCE_B]))
    response = client.post("/batches", json=_register_payload())
    assert response.status_code == 201
    assert response.json() == {
        "batch_id": _BATCH_ID,
        "status": BatchStatusEnum.SUBMITTED.value,
    }

    detail = client.get(f"/batches/{_BATCH_ID}")
    assert detail.status_code == 200
    batch = detail.json()["batch"]
    assert batch["source_ids"] == [_SOURCE_A, _SOURCE_B]
    assert batch["external_batch_id"] == "anthropic-batch-ext-1"
    assert batch["entry_count"] == 2


def test_post_batches_duplicate_returns_409(client: TestClient, temp_db: Path) -> None:
    asyncio.run(_seed_relevance_queued(temp_db, [_SOURCE_A, _SOURCE_B]))
    first = client.post("/batches", json=_register_payload())
    second = client.post("/batches", json=_register_payload())
    assert first.status_code == 201
    assert second.status_code == 409
    assert second.json() == {"error": "batch_conflict", "batch_id": _BATCH_ID}


def test_post_batches_rejects_non_queued_source(client: TestClient, temp_db: Path) -> None:
    asyncio.run(_seed_relevance_queued(temp_db, [_SOURCE_A]))
    asyncio.run(_seed_discovered_only(temp_db, [_SOURCE_B]))
    response = client.post("/batches", json=_register_payload())
    assert response.status_code == 409
    assert response.json() == {
        "error": "invalid_source_state",
        "source_id": _SOURCE_B,
        "state": ProcessingState.DISCOVERED.value,
    }


def test_patch_batches_updates_status_and_counts(client: TestClient, temp_db: Path) -> None:
    asyncio.run(_seed_relevance_queued(temp_db, [_SOURCE_A, _SOURCE_B]))
    client.post("/batches", json=_register_payload())
    completed_at = _NOW.isoformat().replace("+00:00", "Z")
    response = client.patch(
        f"/batches/{_BATCH_ID}",
        json={
            "status": BatchStatusEnum.COMPLETE.value,
            "passed_count": 1,
            "failed_count": 1,
            "completed_at": completed_at,
        },
    )
    assert response.status_code == 200
    batch = response.json()["batch"]
    assert batch["status"] == BatchStatusEnum.COMPLETE.value
    assert batch["passed_count"] == 1
    assert batch["failed_count"] == 1
    assert batch["completed_at"] is not None


def test_patch_batches_not_found(client: TestClient) -> None:
    response = client.patch(
        "/batches/missing",
        json={"status": BatchStatusEnum.COMPLETE.value},
    )
    assert response.status_code == 404
    assert response.json() == {"error": "not_found", "batch_id": "missing"}


def test_post_batch_timeout_resets_relevance_queued(
    client: TestClient, temp_db: Path
) -> None:
    asyncio.run(_seed_relevance_queued(temp_db, [_SOURCE_A, _SOURCE_B]))
    client.post("/batches", json=_register_payload())

    response = client.post(f"/batches/{_BATCH_ID}/timeout")
    assert response.status_code == 200
    assert response.json() == {
        "batch_id": _BATCH_ID,
        "status": BatchStatusEnum.BATCH_TIMED_OUT.value,
        "entries_reset": 2,
    }

    async def _check_manifest_states() -> list[str]:
        async with aiosqlite.connect(temp_db) as conn:
            cursor = await conn.execute(
                "SELECT processing_state FROM manifest WHERE source_id IN (?, ?)",
                (_SOURCE_A, _SOURCE_B),
            )
            return [row[0] for row in await cursor.fetchall()]

    states = asyncio.run(_check_manifest_states())
    assert states == [
        ProcessingState.DISCOVERED.value,
        ProcessingState.DISCOVERED.value,
    ]


def test_post_batch_timeout_idempotent_when_already_timed_out(
    client: TestClient, temp_db: Path
) -> None:
    asyncio.run(_seed_relevance_queued(temp_db, [_SOURCE_A]))
    client.post("/batches", json=_register_payload(source_ids=[_SOURCE_A]))
    first = client.post(f"/batches/{_BATCH_ID}/timeout")
    second = client.post(f"/batches/{_BATCH_ID}/timeout")
    assert first.status_code == 200
    assert first.json()["entries_reset"] == 1
    assert second.status_code == 200
    assert second.json()["entries_reset"] == 0


def test_post_batch_timeout_rejects_complete_batch(client: TestClient, temp_db: Path) -> None:
    asyncio.run(_seed_relevance_queued(temp_db, [_SOURCE_A, _SOURCE_B]))
    client.post("/batches", json=_register_payload())
    client.patch(
        f"/batches/{_BATCH_ID}",
        json={"status": BatchStatusEnum.COMPLETE.value},
    )
    response = client.post(f"/batches/{_BATCH_ID}/timeout")
    assert response.status_code == 409
    assert response.json()["error"] == "invalid_batch_state"


def test_post_batch_timeout_skips_non_queued_source_ids(
    client: TestClient, temp_db: Path
) -> None:
    """Falsifier: timeout must not reset entries outside RELEVANCE_QUEUED."""
    asyncio.run(_seed_relevance_queued(temp_db, [_SOURCE_A]))
    asyncio.run(_seed_discovered_only(temp_db, [_SOURCE_B]))
    client.post("/batches", json=_register_payload(source_ids=[_SOURCE_A]))
    response = client.post(f"/batches/{_BATCH_ID}/timeout")
    assert response.status_code == 200
    assert response.json()["entries_reset"] == 1
