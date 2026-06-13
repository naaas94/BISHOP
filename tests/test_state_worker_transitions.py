"""Unit tests for state-worker transition engine (T2)."""

from __future__ import annotations

import asyncio
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_STATE_WORKER_ROOT = _REPO_ROOT / "services" / "state-worker"

for path in (_STATE_WORKER_ROOT, _REPO_ROOT):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

from app.db import close_pool, get_db, init_pool, run_migrations  # noqa: E402
from app.enums import BatchTypeEnum, DomainEnum, EntryTypeEnum, ProcessingState, SourceEnum  # noqa: E402
from app.models.http import (  # noqa: E402
    BatchRegisterRequest,
    EnrichmentStage1EntryWire,
    EnrichmentStage1ResultsRequest,
    ManifestBatchEntryWire,
    PreFilterResultEntryWire,
)
from app.transitions import (  # noqa: E402
    LOCK_STATE_SWEEP_RESETS,
    MANIFEST_CLAIM_MAP,
    N3_FAILURE_NORMALIZATION,
    ProvenanceIncompleteError,
    RETRY_TARGET_MAP,
    TerminalStateError,
    apply_enrichment_stage1_results,
    apply_pre_filter_results,
    assert_pre_filter_provenance,
    claim_entries_poll,
    claim_manifest_poll,
    create_entry_from_content,
    ingest_manifest_batch,
    manual_retry,
    mark_enrichment_stage1_submitted,
    mark_indexed,
    normalize_failure_state,
    record_failure,
    register_batch,
    resolve_retry_target,
    run_lock_state_recovery_sweep,
    run_retry_sweep,
)

_NOW = datetime(2026, 6, 11, 12, 0, 0, tzinfo=UTC)
_OLD = _NOW - timedelta(hours=1)
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
def db_pool(temp_db: Path):
    async def _setup():
        await init_pool(str(temp_db), size=1)
        yield
        await close_pool()

    return _setup


async def _seed_discovered(conn, source_id: str = _SOURCE) -> None:
    result = await ingest_manifest_batch(conn, [_wire_entry(source_id)])
    assert result.inserted == 1


async def _advance_to_relevance_passed(conn, source_id: str = _SOURCE) -> None:
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


async def _advance_to_scraped(conn, source_id: str = _SOURCE) -> str:
    await _advance_to_relevance_passed(conn, source_id)
    await claim_manifest_poll(conn, ProcessingState.RELEVANCE_PASSED)
    entry_id, _ = await create_entry_from_content(conn, source_id, "full body")
    return entry_id


async def _advance_to_stage1_submitted(conn, source_id: str = _SOURCE) -> None:
    await _advance_to_scraped(conn, source_id)
    await claim_entries_poll(conn, ProcessingState.SCRAPED)
    await mark_enrichment_stage1_submitted(conn, [source_id], "enrich-batch-1")


def test_claim_mapping_matches_spec() -> None:
    assert MANIFEST_CLAIM_MAP[ProcessingState.DISCOVERED] == ProcessingState.RELEVANCE_QUEUED
    assert MANIFEST_CLAIM_MAP[ProcessingState.RELEVANCE_PASSED] == ProcessingState.SCRAPE_QUEUED
    assert RETRY_TARGET_MAP[ProcessingState.SCRAPE_FAILED] == ProcessingState.RELEVANCE_PASSED
    assert LOCK_STATE_SWEEP_RESETS[ProcessingState.RELEVANCE_QUEUED] == ProcessingState.DISCOVERED


def test_n3_normalization_maps_submitted_to_failed() -> None:
    assert (
        normalize_failure_state(ProcessingState.ENRICHMENT_STAGE1_SUBMITTED)
        == ProcessingState.ENRICHMENT_STAGE1_FAILED
    )
    assert (
        N3_FAILURE_NORMALIZATION[ProcessingState.ENRICHMENT_STAGE2_SUBMITTED]
        == ProcessingState.ENRICHMENT_STAGE2_FAILED
    )


def test_resolve_retry_target_uses_canonical_mapping() -> None:
    assert resolve_retry_target(ProcessingState.VECTOR_WRITE_FAILED) == (
        ProcessingState.VECTOR_WRITE_QUEUED
    )


def test_assert_pre_filter_provenance_raises_when_incomplete() -> None:
    from app.models.domain import ManifestEntry

    manifest = ManifestEntry(
        source_id=_SOURCE,
        source=SourceEnum.ARXIV,
        url="https://example.com",
        title="T",
        discovered_at=_NOW,
        domain=DomainEnum.PROFESSIONAL,
        processing_state=ProcessingState.RELEVANCE_PASSED,
    )
    with pytest.raises(ProvenanceIncompleteError):
        assert_pre_filter_provenance(manifest)


def test_manifest_ingest_idempotent(temp_db: Path) -> None:
    async def _run() -> None:
        await init_pool(str(temp_db), size=1)
        try:
            async with get_db() as conn:
                first = await ingest_manifest_batch(conn, [_wire_entry()])
                second = await ingest_manifest_batch(conn, [_wire_entry()])
                assert first.inserted == 1 and first.skipped == 0
                assert second.inserted == 0 and second.skipped == 1
        finally:
            await close_pool()

    asyncio.run(_run())


def test_atomic_claim_second_poll_empty(temp_db: Path) -> None:
    async def _run() -> None:
        await init_pool(str(temp_db), size=1)
        try:
            async with get_db() as conn:
                await _seed_discovered(conn)
                first = await claim_manifest_poll(conn, ProcessingState.DISCOVERED, limit=50)
                second = await claim_manifest_poll(conn, ProcessingState.DISCOVERED, limit=50)
                assert first.claimed_count == 1
                assert first.transitioned_to == ProcessingState.RELEVANCE_QUEUED.value
                assert second.claimed_count == 0
                assert second.entries == []
        finally:
            await close_pool()

    asyncio.run(_run())


def test_terminal_state_blocks_pre_filter_update(temp_db: Path) -> None:
    async def _run() -> None:
        await init_pool(str(temp_db), size=1)
        try:
            async with get_db() as conn:
                await _seed_discovered(conn)
                await conn.execute(
                    "UPDATE manifest SET processing_state = ? WHERE source_id = ?",
                    (ProcessingState.RELEVANCE_REJECTED.value, _SOURCE),
                )
                await conn.commit()
                with pytest.raises(TerminalStateError):
                    await apply_pre_filter_results(
                        conn,
                        "batch-1",
                        "1.0.0",
                        [
                            PreFilterResultEntryWire(
                                source_id=_SOURCE,
                                decision=1,
                                pre_filter_rationale="late",
                            )
                        ],
                    )
        finally:
            await close_pool()

    asyncio.run(_run())


def test_h3_enrichment_stage1_success_atomic(temp_db: Path) -> None:
    async def _run() -> None:
        await init_pool(str(temp_db), size=1)
        try:
            async with get_db() as conn:
                await _advance_to_stage1_submitted(conn)
                await apply_enrichment_stage1_results(
                    conn,
                    "enrich-batch-1",
                    [
                        EnrichmentStage1EntryWire(
                            source_id=_SOURCE,
                            success=True,
                            summary="Dense summary",
                            concepts=["RAG"],
                            tags=["embeddings"],
                            entry_type=EntryTypeEnum.PAPER,
                            challenge_hooks=["latency"],
                        )
                    ],
                )
                cursor = await conn.execute(
                    "SELECT processing_state, summary FROM entries WHERE source_id = ?",
                    (_SOURCE,),
                )
                row = await cursor.fetchone()
                assert row[0] == ProcessingState.ENRICHMENT_STAGE2_QUEUED.value
                assert row[1] == "Dense summary"
        finally:
            await close_pool()

    asyncio.run(_run())


def test_h3_rollback_on_mid_sequence_failure(temp_db: Path) -> None:
    async def _run() -> None:
        await init_pool(str(temp_db), size=1)
        try:
            async with get_db() as conn:
                await _advance_to_stage1_submitted(conn)

                async def _boom(*_args, **_kwargs):
                    raise RuntimeError("simulated mid-H3 failure")

                request = EnrichmentStage1ResultsRequest(
                    batch_id="enrich-batch-1",
                    entries=[
                        EnrichmentStage1EntryWire(
                            source_id=_SOURCE,
                            success=True,
                            summary="Dense summary",
                            concepts=["RAG"],
                        )
                    ],
                )
                with patch(
                    "app.transitions._h3_enrichment_stage1_success",
                    side_effect=_boom,
                ):
                    with pytest.raises(RuntimeError):
                        await apply_enrichment_stage1_results(
                            conn, request.batch_id, request.entries
                        )
                cursor = await conn.execute(
                    "SELECT processing_state, summary FROM entries WHERE source_id = ?",
                    (_SOURCE,),
                )
                row = await cursor.fetchone()
                assert row[0] == ProcessingState.ENRICHMENT_STAGE1_SUBMITTED.value
                assert row[1] is None
        finally:
            await close_pool()

    asyncio.run(_run())


def test_n3_error_log_records_failed_not_submitted(temp_db: Path) -> None:
    async def _run() -> None:
        await init_pool(str(temp_db), size=1)
        try:
            async with get_db() as conn:
                await _advance_to_stage1_submitted(conn)
                await apply_enrichment_stage1_results(
                    conn,
                    "enrich-batch-1",
                    [
                        EnrichmentStage1EntryWire(
                            source_id=_SOURCE,
                            success=False,
                            error_message="batch item failed",
                        )
                    ],
                )
                cursor = await conn.execute(
                    "SELECT state_at_failure FROM error_log WHERE source_id = ?",
                    (_SOURCE,),
                )
                row = await cursor.fetchone()
                assert row[0] == ProcessingState.ENRICHMENT_STAGE1_FAILED.value
        finally:
            await close_pool()

    asyncio.run(_run())


def test_lock_state_sweep_resets_stuck_relevance_queued(temp_db: Path) -> None:
    async def _run() -> None:
        await init_pool(str(temp_db), size=1)
        try:
            async with get_db() as conn:
                await _seed_discovered(conn)
                await conn.execute(
                    """
                    UPDATE manifest SET
                        processing_state = ?,
                        discovered_at = ?
                    WHERE source_id = ?
                    """,
                    (
                        ProcessingState.RELEVANCE_QUEUED.value,
                        _OLD.isoformat(),
                        _SOURCE,
                    ),
                )
                await conn.commit()
                reset_count = await run_lock_state_recovery_sweep(
                    conn, threshold_sec=900, now=_NOW
                )
                assert reset_count == 1
                cursor = await conn.execute(
                    "SELECT processing_state FROM manifest WHERE source_id = ?",
                    (_SOURCE,),
                )
                row = await cursor.fetchone()
                assert row[0] == ProcessingState.DISCOVERED.value
        finally:
            await close_pool()

    asyncio.run(_run())


def test_lock_state_sweep_skips_relevance_queued_in_active_batch(temp_db: Path) -> None:
    async def _run() -> None:
        await init_pool(str(temp_db), size=1)
        try:
            async with get_db() as conn:
                await _seed_discovered(conn)
                await claim_manifest_poll(conn, ProcessingState.DISCOVERED)
                await register_batch(
                    conn,
                    BatchRegisterRequest(
                        batch_id="batch-active-1",
                        batch_type=BatchTypeEnum.PRE_FILTER,
                        domain=DomainEnum.PROFESSIONAL,
                        profile_version="1.0.0",
                        profile_render_hash="a" * 64,
                        source_ids=[_SOURCE],
                        external_batch_id="msgbatch_active_1",
                        entry_count=1,
                    ),
                )
                await conn.execute(
                    """
                    UPDATE manifest SET discovered_at = ?
                    WHERE source_id = ?
                    """,
                    (_OLD.isoformat(), _SOURCE),
                )
                await conn.commit()
                reset_count = await run_lock_state_recovery_sweep(
                    conn, threshold_sec=900, now=_NOW
                )
                assert reset_count == 0
                cursor = await conn.execute(
                    "SELECT processing_state FROM manifest WHERE source_id = ?",
                    (_SOURCE,),
                )
                row = await cursor.fetchone()
                assert row[0] == ProcessingState.RELEVANCE_QUEUED.value
        finally:
            await close_pool()

    asyncio.run(_run())


def test_retry_sweep_requeues_failed_entry(temp_db: Path) -> None:
    async def _run() -> None:
        await init_pool(str(temp_db), size=1)
        try:
            async with get_db() as conn:
                await _advance_to_scraped(conn)
                await record_failure(
                    conn,
                    source_id=_SOURCE,
                    state_at_failure=ProcessingState.SCRAPE_QUEUED,
                    error_class="TimeoutError",
                    http_status=None,
                    message="timeout",
                    is_retriable=True,
                )
                await conn.execute(
                    "UPDATE manifest SET next_retry_at = ? WHERE source_id = ?",
                    ((_NOW - timedelta(minutes=1)).isoformat(), _SOURCE),
                )
                await conn.commit()
                count = await run_retry_sweep(conn, now=_NOW)
                assert count == 1
                cursor = await conn.execute(
                    "SELECT processing_state FROM manifest WHERE source_id = ?",
                    (_SOURCE,),
                )
                row = await cursor.fetchone()
                assert row[0] == ProcessingState.RELEVANCE_PASSED.value
        finally:
            await close_pool()

    asyncio.run(_run())


def test_manual_retry_resets_retry_count(temp_db: Path) -> None:
    async def _run() -> None:
        await init_pool(str(temp_db), size=1)
        try:
            async with get_db() as conn:
                await _advance_to_scraped(conn)
                await record_failure(
                    conn,
                    source_id=_SOURCE,
                    state_at_failure=ProcessingState.ENRICHMENT_STAGE1_SUBMITTED,
                    error_class="BatchError",
                    http_status=None,
                    message="failed",
                    is_retriable=True,
                )
                target = await manual_retry(conn, _SOURCE)
                assert target == ProcessingState.SCRAPED
                cursor = await conn.execute(
                    "SELECT retry_count FROM manifest WHERE source_id = ?",
                    (_SOURCE,),
                )
                row = await cursor.fetchone()
                assert row[0] == 0
        finally:
            await close_pool()

    asyncio.run(_run())


def test_mark_indexed_idempotent(temp_db: Path) -> None:
    async def _run() -> None:
        await init_pool(str(temp_db), size=1)
        try:
            async with get_db() as conn:
                await _advance_to_scraped(conn)
                await conn.execute(
                    "UPDATE entries SET processing_state = ? WHERE source_id = ?",
                    (ProcessingState.VECTOR_WRITE_QUEUED.value, _SOURCE),
                )
                await conn.execute(
                    "UPDATE manifest SET processing_state = ? WHERE source_id = ?",
                    (ProcessingState.VECTOR_WRITE_QUEUED.value, _SOURCE),
                )
                await conn.commit()
                await mark_indexed(conn, _SOURCE)
                await mark_indexed(conn, _SOURCE)
                cursor = await conn.execute(
                    "SELECT processing_state FROM entries WHERE source_id = ?",
                    (_SOURCE,),
                )
                row = await cursor.fetchone()
                assert row[0] == ProcessingState.INDEXED.value
        finally:
            await close_pool()

    asyncio.run(_run())


def test_create_entry_rejects_incomplete_provenance(temp_db: Path) -> None:
    async def _run() -> None:
        await init_pool(str(temp_db), size=1)
        try:
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
                with pytest.raises(ProvenanceIncompleteError):
                    await create_entry_from_content(conn, _SOURCE, "body")
        finally:
            await close_pool()

    asyncio.run(_run())


def test_vector_write_poll_does_not_claim(temp_db: Path) -> None:
    async def _run() -> None:
        await init_pool(str(temp_db), size=1)
        try:
            async with get_db() as conn:
                await _advance_to_scraped(conn)
                await conn.execute(
                    "UPDATE entries SET processing_state = ? WHERE source_id = ?",
                    (ProcessingState.VECTOR_WRITE_QUEUED.value, _SOURCE),
                )
                await conn.commit()
                first = await claim_entries_poll(
                    conn, ProcessingState.VECTOR_WRITE_QUEUED
                )
                second = await claim_entries_poll(
                    conn, ProcessingState.VECTOR_WRITE_QUEUED
                )
                assert first.claimed_count == 1
                assert first.transitioned_to is None
                assert second.claimed_count == 1
        finally:
            await close_pool()

    asyncio.run(_run())
