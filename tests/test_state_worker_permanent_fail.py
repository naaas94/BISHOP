"""Unit tests for POST /entries/permanent-fail (T5 / §0 flag 2)."""

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
from app.enums import DomainEnum, ProcessingState, SourceEnum  # noqa: E402
from app.models.http import ManifestBatchEntryWire, PreFilterResultEntryWire  # noqa: E402
from app.routers.entries import router  # noqa: E402
from app.transitions import (  # noqa: E402
    apply_pre_filter_results,
    claim_manifest_poll,
    create_entry_from_content,
    ingest_manifest_batch,
    record_failure,
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


async def _seed_escalation_flagged(conn, source_id: str = _SOURCE) -> None:
    """Advance source_id to ESCALATION_FLAGGED with a real entries row present."""
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
    # Escalate via the existing non-retriable-HTTP-status path (§6.3 classification).
    await record_failure(
        conn,
        source_id=source_id,
        state_at_failure=ProcessingState.SCRAPE_QUEUED,
        error_class="HTTPStatusError",
        http_status=404,
        message="Not found",
        is_retriable=True,
    )


def test_post_permanent_fail_transitions_to_permanently_failed(
    client: TestClient,
) -> None:
    async def _seed() -> None:
        async with get_db() as conn:
            await _seed_escalation_flagged(conn)

    asyncio.run(_seed())
    response = client.post(
        "/entries/permanent-fail",
        json={"source_id": _SOURCE},
    )
    assert response.status_code == 200
    assert response.json() == {
        "source_id": _SOURCE,
        "processing_state": ProcessingState.PERMANENTLY_FAILED.value,
    }

    async def _states() -> tuple:
        async with get_db() as conn:
            cursor = await conn.execute(
                "SELECT processing_state FROM manifest WHERE source_id = ?",
                (_SOURCE,),
            )
            manifest_state = await cursor.fetchone()
            cursor = await conn.execute(
                "SELECT processing_state, flagged_for_review FROM entries WHERE source_id = ?",
                (_SOURCE,),
            )
            entry_row = await cursor.fetchone()
            return manifest_state, entry_row

    manifest_state, entry_row = asyncio.run(_states())
    assert manifest_state[0] == ProcessingState.PERMANENTLY_FAILED.value
    assert entry_row[0] == ProcessingState.PERMANENTLY_FAILED.value
    assert entry_row[1] == 0


def test_post_permanent_fail_not_found_returns_404(client: TestClient) -> None:
    response = client.post(
        "/entries/permanent-fail",
        json={"source_id": "missing:999"},
    )
    assert response.status_code == 404
    assert response.json() == {"error": "not_found", "source_id": "missing:999"}


def test_post_permanent_fail_wrong_state_returns_409(client: TestClient) -> None:
    """Falsifier: a non-ESCALATION_FLAGGED source_id (e.g. DISCOVERED) is a 409."""

    async def _seed() -> None:
        async with get_db() as conn:
            await _seed_discovered(conn)

    asyncio.run(_seed())
    response = client.post(
        "/entries/permanent-fail",
        json={"source_id": _SOURCE},
    )
    assert response.status_code == 409
    body = response.json()
    assert body["error"] == "invalid_transition"
    assert body["source_id"] == _SOURCE
    assert body["from_state"] == ProcessingState.DISCOVERED.value
    assert body["to_state"] == ProcessingState.PERMANENTLY_FAILED.value
