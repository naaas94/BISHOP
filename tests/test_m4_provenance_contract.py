"""M4 exit gate: provenance assertion and SCRAPED entry creation contract (T3).

Complements M1 tests in test_state_worker_entries_router.py and
test_state_worker_transitions.py — does not replace them.
"""

from __future__ import annotations

import asyncio
import inspect
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
from app.models.http import (  # noqa: E402
    ManifestBatchEntryWire,
    PreFilterResultEntryWire,
)
from app.routers.entries import router  # noqa: E402
from app.transitions import (  # noqa: E402
    apply_pre_filter_results,
    claim_manifest_poll,
    create_entry_from_content,
    ingest_manifest_batch,
)

_NOW = datetime(2026, 6, 13, 12, 0, 0, tzinfo=UTC)
_SOURCE = "arxiv:2301.00001"

# Enrichment-populated columns that must remain SQL NULL at SCRAPED creation (M4 gate).
_M4_ENRICHMENT_NULL_COLUMNS = (
    "summary",
    "concepts",
    "tags",
    "entry_type",
    "challenge_hooks",
    "enrichment_stage1_batch_id",
    "relevance_score",
    "relevance_reason",
    "value_rationale",
    "enrichment_stage2_batch_id",
    "`references`",
    "cited_by",
)


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


async def _advance_to_scrape_queued(conn, source_id: str = _SOURCE) -> None:
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


def test_m4_create_entry_from_content_calls_assert_pre_filter_provenance() -> None:
    """Kill-criterion evidence: provenance guard is on the content-creation path."""
    source = inspect.getsource(create_entry_from_content)
    assert "assert_pre_filter_provenance(manifest)" in source


def test_m4_create_entry_leaves_enrichment_fields_sql_null(temp_db: Path) -> None:
    """SCRAPED creation must not pre-populate enrichment columns (M4 exit gate)."""

    async def _run() -> None:
        await init_pool(str(temp_db), size=1)
        try:
            async with get_db() as conn:
                await _advance_to_scrape_queued(conn)
                entry_id, state = await create_entry_from_content(
                    conn, _SOURCE, "full paper body"
                )
                assert state == ProcessingState.SCRAPED

                columns_sql = ", ".join(_M4_ENRICHMENT_NULL_COLUMNS)
                cursor = await conn.execute(
                    f"SELECT {columns_sql} FROM entries WHERE id = ?",
                    (entry_id,),
                )
                row = await cursor.fetchone()
                assert row is not None
                assert all(value is None for value in row)
        finally:
            await close_pool()

    asyncio.run(_run())


def test_m4_post_content_provenance_incomplete_returns_409(client: TestClient) -> None:
    """M4 exit gate: POST /entries/content rejects incomplete pre-filter provenance."""

    async def _seed() -> None:
        async with get_db() as conn:
            await _seed_discovered(conn)
            await conn.execute(
                """
                UPDATE manifest SET
                    processing_state = ?,
                    relevance_decision = 1
                WHERE source_id = ?
                """,
                (ProcessingState.RELEVANCE_PASSED.value, _SOURCE),
            )
            await conn.commit()

    asyncio.run(_seed())
    response = client.post(
        "/entries/content",
        json={"source_id": _SOURCE, "content_raw": "body"},
    )
    assert response.status_code == 409
    assert response.json() == {
        "error": "provenance_incomplete",
        "source_id": _SOURCE,
    }


def test_m4_content_post_after_poll_claim_uses_scrape_queued_state(temp_db: Path) -> None:
    """§5.3 happy path: poll claim moves manifest to SCRAPE_QUEUED before content POST."""

    async def _run() -> None:
        await init_pool(str(temp_db), size=1)
        try:
            async with get_db() as conn:
                await _advance_to_scrape_queued(conn)
                cursor = await conn.execute(
                    "SELECT processing_state FROM manifest WHERE source_id = ?",
                    (_SOURCE,),
                )
                row = await cursor.fetchone()
                assert row is not None
                assert row[0] == ProcessingState.SCRAPE_QUEUED.value

                entry_id, state = await create_entry_from_content(
                    conn, _SOURCE, "scraped body"
                )
                assert state == ProcessingState.SCRAPED
                assert entry_id
        finally:
            await close_pool()

    asyncio.run(_run())
