"""Unit tests for batch query routers (T5)."""

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
from app.enums import BatchStatusEnum, BatchTypeEnum, DomainEnum  # noqa: E402
from app.models.domain import BatchRecord  # noqa: E402
from app.routers import batches as batches_router  # noqa: E402

_NOW = datetime(2026, 6, 11, 12, 0, 0, tzinfo=UTC)
_BATCH_ID = "batch-uuid-1"


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


async def _insert_batch(
    db_path: Path,
    *,
    batch_id: str = _BATCH_ID,
    status: BatchStatusEnum = BatchStatusEnum.SUBMITTED,
) -> None:
    import aiosqlite

    record = BatchRecord(
        batch_id=batch_id,
        batch_type=BatchTypeEnum.PRE_FILTER,
        domain=DomainEnum.PROFESSIONAL,
        profile_version="1.0.0",
        profile_render_hash="abc123",
        status=status,
        created_at=_NOW,
        entry_count=5,
        passed_count=0,
        failed_count=0,
    )
    async with aiosqlite.connect(db_path) as conn:
        row = record.to_db_row()
        columns = ", ".join(f'"{key}"' for key in row)
        placeholders = ", ".join("?" for _ in row)
        await conn.execute(
            f'INSERT INTO batches ({columns}) VALUES ({placeholders})',
            tuple(row.values()),
        )
        await conn.commit()


def test_batches_list_filters_by_status(temp_db: Path, client: TestClient) -> None:
    import asyncio

    asyncio.run(_insert_batch(temp_db, status=BatchStatusEnum.SUBMITTED))
    asyncio.run(
        _insert_batch(
            temp_db,
            batch_id="batch-uuid-2",
            status=BatchStatusEnum.COMPLETE,
        )
    )

    response = client.get("/batches", params={"status": "submitted,processing"})
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["batches"]) == 1
    assert payload["batches"][0]["batch_id"] == _BATCH_ID
    assert payload["batches"][0]["status"] == BatchStatusEnum.SUBMITTED.value


def test_batches_list_empty_when_no_matches(client: TestClient) -> None:
    response = client.get("/batches", params={"status": "submitted,processing"})
    assert response.status_code == 200
    assert response.json() == {"batches": []}


def test_batch_detail_returns_record(temp_db: Path, client: TestClient) -> None:
    import asyncio

    asyncio.run(_insert_batch(temp_db))

    response = client.get(f"/batches/{_BATCH_ID}")
    assert response.status_code == 200
    assert response.json()["batch"]["batch_id"] == _BATCH_ID


def test_batch_detail_not_found(client: TestClient) -> None:
    response = client.get("/batches/missing-batch")
    assert response.status_code == 404
    assert response.json() == {"error": "not_found", "batch_id": "missing-batch"}


def test_batches_rejects_invalid_status_token(client: TestClient) -> None:
    """Falsifier: unknown status values are accepted silently."""
    response = client.get("/batches", params={"status": "not-a-status"})
    assert response.status_code == 400
    assert response.json()["error"] == "invalid_batch_status"
