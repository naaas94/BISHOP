"""Unit tests for M5 state-worker enrichment hub (T2)."""

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

from app.db import close_pool, get_db, init_pool, run_migrations  # noqa: E402
from app.enums import (  # noqa: E402
    BatchTypeEnum,
    DomainEnum,
    EntryTypeEnum,
    OovReviewStatusEnum,
    ProcessingState,
    SourceEnum,
)
from app.models.http import (  # noqa: E402
    BatchRegisterRequest,
    EnrichmentStage1EntryWire,
    ManifestBatchEntryWire,
    PreFilterResultEntryWire,
)
from app.routers import batches as batches_router  # noqa: E402
from app.transitions import (  # noqa: E402
    BatchConflictError,
    InvalidTransitionError,
    apply_batch_timeout,
    apply_enrichment_stage1_results,
    claim_entries_poll,
    claim_manifest_poll,
    create_entry_from_content,
    ingest_manifest_batch,
    register_batch,
)

_NOW = datetime(2026, 6, 13, 12, 0, 0, tzinfo=UTC)
_SOURCE = "arxiv:2301.00001"
_SOURCE_B = "arxiv:2301.00002"
_PROFILE_HASH = "deadbeef" * 8
_STAGE1_BATCH = "enrich-stage1-batch-1"
_STAGE2_BATCH = "enrich-stage2-batch-1"


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


def _wire_entry(source_id: str = _SOURCE) -> ManifestBatchEntryWire:
    return ManifestBatchEntryWire(
        source_id=source_id,
        source=SourceEnum.ARXIV,
        url=f"https://arxiv.org/abs/{source_id}",
        title="Test Paper",
        abstract="An abstract",
        published_at=_NOW,
        domain=DomainEnum.PROFESSIONAL.value,
    )


async def _advance_to_stage1_queued(conn, source_id: str = _SOURCE) -> None:
    await ingest_manifest_batch(conn, [_wire_entry(source_id)], discovered_at=_NOW)
    await claim_manifest_poll(conn, ProcessingState.DISCOVERED)
    await apply_pre_filter_results_helper(conn, source_id)
    await claim_manifest_poll(conn, ProcessingState.RELEVANCE_PASSED)
    await create_entry_from_content(conn, source_id, "full body", ingested_at=_NOW)
    await claim_entries_poll(conn, ProcessingState.SCRAPED)


async def _advance_to_stage2_claimed(conn, source_id: str = _SOURCE) -> None:
    await _advance_to_stage1_queued(conn, source_id)
    from app.transitions import mark_enrichment_stage1_submitted

    await mark_enrichment_stage1_submitted(conn, [source_id], "prior-stage1-batch")
    await apply_enrichment_stage1_results(
        conn,
        "prior-stage1-batch",
        [
            EnrichmentStage1EntryWire(
                source_id=source_id,
                success=True,
                summary="summary",
            )
        ],
    )
    await claim_entries_poll(conn, ProcessingState.ENRICHMENT_STAGE2_QUEUED)


async def apply_pre_filter_results_helper(conn, source_id: str) -> None:
    from app.transitions import apply_pre_filter_results

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


def _stage1_register_request(
    *,
    batch_id: str = _STAGE1_BATCH,
    source_ids: list[str] | None = None,
) -> BatchRegisterRequest:
    ids = source_ids if source_ids is not None else [_SOURCE]
    return BatchRegisterRequest(
        batch_id=batch_id,
        batch_type=BatchTypeEnum.ENRICHMENT_STAGE1,
        domain=DomainEnum.PROFESSIONAL,
        profile_version="1.0.0",
        profile_render_hash=_PROFILE_HASH,
        source_ids=ids,
        external_batch_id="anthropic-ext-1",
        entry_count=len(ids),
    )


def _stage2_register_request(
    *,
    batch_id: str = _STAGE2_BATCH,
    source_ids: list[str] | None = None,
) -> BatchRegisterRequest:
    ids = source_ids if source_ids is not None else [_SOURCE]
    return BatchRegisterRequest(
        batch_id=batch_id,
        batch_type=BatchTypeEnum.ENRICHMENT_STAGE2,
        domain=DomainEnum.PROFESSIONAL,
        profile_version="1.0.0",
        profile_render_hash=_PROFILE_HASH,
        source_ids=ids,
        external_batch_id="anthropic-ext-2",
        entry_count=len(ids),
    )


def test_enrichment_stage1_wire_accepts_oov_tags_stripped() -> None:
    wire = EnrichmentStage1EntryWire(
        source_id=_SOURCE,
        success=True,
        tags=["embeddings"],
        oov_tags_stripped=["novel-tag"],
    )
    assert wire.oov_tags_stripped == ["novel-tag"]


def test_register_batch_stage1_moves_entries_to_submitted(temp_db: Path) -> None:
    async def _run() -> None:
        await init_pool(str(temp_db), size=1)
        try:
            async with get_db() as conn:
                await _advance_to_stage1_queued(conn)
                await register_batch(conn, _stage1_register_request())
                cursor = await conn.execute(
                    "SELECT processing_state FROM entries WHERE source_id = ?",
                    (_SOURCE,),
                )
                row = await cursor.fetchone()
                assert row[0] == ProcessingState.ENRICHMENT_STAGE1_SUBMITTED.value
        finally:
            await close_pool()

    asyncio.run(_run())


def test_register_batch_stage2_moves_entries_to_submitted(temp_db: Path) -> None:
    async def _run() -> None:
        await init_pool(str(temp_db), size=1)
        try:
            async with get_db() as conn:
                await _advance_to_stage2_claimed(conn)
                await register_batch(conn, _stage2_register_request())
                cursor = await conn.execute(
                    "SELECT processing_state FROM entries WHERE source_id = ?",
                    (_SOURCE,),
                )
                row = await cursor.fetchone()
                assert row[0] == ProcessingState.ENRICHMENT_STAGE2_SUBMITTED.value
        finally:
            await close_pool()

    asyncio.run(_run())


def test_register_batch_stage1_rejects_wrong_entry_state(temp_db: Path) -> None:
    async def _run() -> None:
        await init_pool(str(temp_db), size=1)
        try:
            async with get_db() as conn:
                await _advance_to_scraped_only(conn)
                with pytest.raises(InvalidTransitionError):
                    await register_batch(conn, _stage1_register_request())
                cursor = await conn.execute(
                    "SELECT COUNT(*) FROM batches WHERE batch_id = ?",
                    (_STAGE1_BATCH,),
                )
                assert (await cursor.fetchone())[0] == 0
        finally:
            await close_pool()

    asyncio.run(_run())


async def _advance_to_scraped_only(conn, source_id: str = _SOURCE) -> None:
    await ingest_manifest_batch(conn, [_wire_entry(source_id)], discovered_at=_NOW)
    await claim_manifest_poll(conn, ProcessingState.DISCOVERED)
    await apply_pre_filter_results_helper(conn, source_id)
    await claim_manifest_poll(conn, ProcessingState.RELEVANCE_PASSED)
    await create_entry_from_content(conn, source_id, "full body", ingested_at=_NOW)


def test_register_batch_stage1_via_http_moves_to_submitted(
    client: TestClient, temp_db: Path
) -> None:
    async def _seed() -> None:
        async with aiosqlite.connect(temp_db) as conn:
            await conn.execute("PRAGMA journal_mode=WAL")
            await _advance_to_stage1_queued(conn)

    asyncio.run(_seed())
    response = client.post(
        "/batches",
        json={
            "batch_id": _STAGE1_BATCH,
            "batch_type": BatchTypeEnum.ENRICHMENT_STAGE1.value,
            "domain": DomainEnum.PROFESSIONAL.value,
            "profile_version": "1.0.0",
            "profile_render_hash": _PROFILE_HASH,
            "source_ids": [_SOURCE],
            "external_batch_id": "anthropic-ext-1",
            "entry_count": 1,
        },
    )
    assert response.status_code == 201

    async def _check() -> str:
        async with aiosqlite.connect(temp_db) as conn:
            cursor = await conn.execute(
                "SELECT processing_state FROM entries WHERE source_id = ?",
                (_SOURCE,),
            )
            return (await cursor.fetchone())[0]

    assert asyncio.run(_check()) == ProcessingState.ENRICHMENT_STAGE1_SUBMITTED.value


def test_batch_timeout_stage1_submitted_to_failed(temp_db: Path) -> None:
    async def _run() -> None:
        await init_pool(str(temp_db), size=1)
        try:
            async with get_db() as conn:
                await _advance_to_stage1_queued(conn)
                await register_batch(conn, _stage1_register_request())
                result = await apply_batch_timeout(conn, _STAGE1_BATCH)
                assert result.entries_reset == 1
                cursor = await conn.execute(
                    "SELECT processing_state FROM entries WHERE source_id = ?",
                    (_SOURCE,),
                )
                assert (await cursor.fetchone())[0] == (
                    ProcessingState.ENRICHMENT_STAGE1_FAILED.value
                )
        finally:
            await close_pool()

    asyncio.run(_run())


def test_batch_timeout_stage2_submitted_to_failed(temp_db: Path) -> None:
    async def _run() -> None:
        await init_pool(str(temp_db), size=1)
        try:
            async with get_db() as conn:
                await _advance_to_stage2_claimed(conn)
                await register_batch(conn, _stage2_register_request())
                result = await apply_batch_timeout(conn, _STAGE2_BATCH)
                assert result.entries_reset == 1
                cursor = await conn.execute(
                    "SELECT processing_state FROM entries WHERE source_id = ?",
                    (_SOURCE,),
                )
                assert (await cursor.fetchone())[0] == (
                    ProcessingState.ENRICHMENT_STAGE2_FAILED.value
                )
        finally:
            await close_pool()

    asyncio.run(_run())


def test_stage1_results_persist_oov_tags_log(temp_db: Path) -> None:
    async def _run() -> None:
        await init_pool(str(temp_db), size=1)
        try:
            async with get_db() as conn:
                await _advance_to_stage1_queued(conn)
                from app.transitions import mark_enrichment_stage1_submitted

                await mark_enrichment_stage1_submitted(conn, [_SOURCE], _STAGE1_BATCH)
                await apply_enrichment_stage1_results(
                    conn,
                    _STAGE1_BATCH,
                    [
                        EnrichmentStage1EntryWire(
                            source_id=_SOURCE,
                            success=True,
                            summary="Dense summary",
                            tags=["embeddings"],
                            entry_type=EntryTypeEnum.PAPER,
                            oov_tags_stripped=["novel-tag", "another-oov"],
                        )
                    ],
                )
                cursor = await conn.execute(
                    """
                    SELECT tag_value, review_status, enrichment_batch_id
                    FROM oov_tags_log
                    WHERE source_id = ?
                    ORDER BY tag_value
                    """,
                    (_SOURCE,),
                )
                rows = await cursor.fetchall()
                assert len(rows) == 2
                assert rows[0][0] == "another-oov"
                assert rows[0][1] == OovReviewStatusEnum.PENDING.value
                assert rows[0][2] == _STAGE1_BATCH
                assert rows[1][0] == "novel-tag"
        finally:
            await close_pool()

    asyncio.run(_run())


def test_register_batch_rolls_back_on_second_source_invalid_state(
    temp_db: Path,
) -> None:
    """Falsifier: partial batch registration must not leave orphan BatchRecord."""

    async def _run() -> None:
        await init_pool(str(temp_db), size=1)
        try:
            async with get_db() as conn:
                await _advance_to_stage1_queued(conn, _SOURCE)
                await _advance_to_scraped_only(conn, _SOURCE_B)
                with pytest.raises(InvalidTransitionError):
                    await register_batch(
                        conn,
                        _stage1_register_request(source_ids=[_SOURCE, _SOURCE_B]),
                    )
                cursor = await conn.execute(
                    "SELECT COUNT(*) FROM batches WHERE batch_id = ?",
                    (_STAGE1_BATCH,),
                )
                assert (await cursor.fetchone())[0] == 0
                cursor = await conn.execute(
                    "SELECT processing_state FROM entries WHERE source_id = ?",
                    (_SOURCE,),
                )
                assert (await cursor.fetchone())[0] == (
                    ProcessingState.ENRICHMENT_STAGE1_QUEUED.value
                )
        finally:
            await close_pool()

    asyncio.run(_run())


def test_register_batch_duplicate_still_raises_conflict(temp_db: Path) -> None:
    async def _run() -> None:
        await init_pool(str(temp_db), size=1)
        try:
            async with get_db() as conn:
                await _advance_to_stage1_queued(conn)
                await register_batch(conn, _stage1_register_request())
                with pytest.raises(BatchConflictError):
                    await register_batch(conn, _stage1_register_request())
        finally:
            await close_pool()

    asyncio.run(_run())
