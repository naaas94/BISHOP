"""Unit tests for PATCH /entries/{source_id}/reading-status (T5 / §0 flag 1)."""

from __future__ import annotations

import asyncio
import sys
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
from app.enums import DomainEnum, ProcessingState, ReadingStatusEnum, SourceEnum  # noqa: E402
from app.models.http import ManifestBatchEntryWire, PreFilterResultEntryWire  # noqa: E402
from app.routers.entries import router  # noqa: E402
from app.transitions import (  # noqa: E402
    apply_pre_filter_results,
    claim_manifest_poll,
    create_entry_from_content,
    ingest_manifest_batch,
)

_NOW = datetime(2026, 6, 11, 12, 0, 0, tzinfo=UTC)
_SOURCE = "arxiv:2301.00001"


def _wire_entry(source_id: str = _SOURCE) -> ManifestBatchEntryWire:
    return ManifestBatchEntryWire(
        source_id=source_id,
        source=SourceEnum.ARXIV,
        url="https://arxiv.org/abs/2301.00001",
        title="Test Paper",
        abstract="An abstract",
        published_at=_NOW,
        domain=DomainEnum.PROFESSIONAL.value,
    )


@pytest.fixture
def temp_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "bishop.db"
    run_migrations(str(db_path))
    return db_path


@pytest.fixture
def client(temp_db: Path):
    async def _setup() -> None:
        await init_pool(str(temp_db), size=1)

    asyncio.run(_setup())
    app = FastAPI()
    app.include_router(router)
    yield TestClient(app)
    asyncio.run(close_pool())


async def _seed_discovered(conn, source_id: str = _SOURCE) -> None:
    result = await ingest_manifest_batch(conn, [_wire_entry(source_id)])
    assert result.inserted == 1


async def _seed_entry(conn, source_id: str = _SOURCE) -> None:
    """Advance source_id through to an existing entries row (SCRAPED)."""
    await _seed_discovered(conn, source_id)
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
    await create_entry_from_content(conn, source_id, "full body")


def test_patch_reading_status_updates_entry(client: TestClient) -> None:
    async def _seed() -> None:
        async with get_db() as conn:
            await _seed_entry(conn)

    asyncio.run(_seed())
    response = client.patch(
        f"/entries/{_SOURCE}/reading-status",
        json={"reading_status": ReadingStatusEnum.READ.value},
    )
    assert response.status_code == 200
    assert response.json() == {
        "source_id": _SOURCE,
        "reading_status": ReadingStatusEnum.READ.value,
    }

    async def _read_status() -> tuple:
        async with get_db() as conn:
            cursor = await conn.execute(
                "SELECT reading_status FROM entries WHERE source_id = ?",
                (_SOURCE,),
            )
            return await cursor.fetchone()

    assert tuple(asyncio.run(_read_status())) == (ReadingStatusEnum.READ.value,)


def test_patch_reading_status_slash_source_id(client: TestClient) -> None:
    github_id = "github:clavia-labs/tardigrade"

    async def _seed() -> None:
        async with get_db() as conn:
            await _seed_entry(conn, github_id)

    asyncio.run(_seed())
    response = client.patch(
        f"/entries/{github_id}/reading-status",
        json={"reading_status": ReadingStatusEnum.READ.value},
    )
    assert response.status_code == 200
    assert response.json() == {
        "source_id": github_id,
        "reading_status": ReadingStatusEnum.READ.value,
    }


def test_patch_reading_status_does_not_touch_manifest_processing_state(
    client: TestClient,
) -> None:
    """Contract: reading-status PATCH updates entries.reading_status only."""

    async def _seed() -> None:
        async with get_db() as conn:
            await _seed_entry(conn)

    asyncio.run(_seed())

    async def _manifest_state() -> tuple:
        async with get_db() as conn:
            cursor = await conn.execute(
                "SELECT processing_state FROM manifest WHERE source_id = ?",
                (_SOURCE,),
            )
            return await cursor.fetchone()

    before = tuple(asyncio.run(_manifest_state()))

    response = client.patch(
        f"/entries/{_SOURCE}/reading-status",
        json={"reading_status": ReadingStatusEnum.ARCHIVED.value},
    )
    assert response.status_code == 200

    after = tuple(asyncio.run(_manifest_state()))
    assert before == after
    assert after == (ProcessingState.SCRAPED.value,)


def test_patch_reading_status_not_found_returns_404(client: TestClient) -> None:
    response = client.patch(
        "/entries/missing:999/reading-status",
        json={"reading_status": ReadingStatusEnum.READ.value},
    )
    assert response.status_code == 404
    assert response.json() == {"error": "not_found", "source_id": "missing:999"}


def test_patch_reading_status_manifest_only_returns_409(client: TestClient) -> None:
    """Falsifier: a manifest-only source_id (no entries row) is a 409, not a 404 or 200."""

    async def _seed() -> None:
        async with get_db() as conn:
            await _seed_discovered(conn)

    asyncio.run(_seed())
    response = client.patch(
        f"/entries/{_SOURCE}/reading-status",
        json={"reading_status": ReadingStatusEnum.READ.value},
    )
    assert response.status_code == 409
    assert response.json() == {"error": "entry_missing", "source_id": _SOURCE}


def test_patch_reading_status_invalid_enum_returns_422(client: TestClient) -> None:
    async def _seed() -> None:
        async with get_db() as conn:
            await _seed_entry(conn)

    asyncio.run(_seed())
    response = client.patch(
        f"/entries/{_SOURCE}/reading-status",
        json={"reading_status": "not_a_real_status"},
    )
    assert response.status_code == 422
