"""State transition engine — atomic claims, H3 transactions, N3 normalization, sweeps."""

from __future__ import annotations

import json
import logging
import random
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import aiosqlite

from app.config import RETRY_MAX_ATTEMPTS
from app.enums import (
    BatchStatusEnum,
    BatchTypeEnum,
    DomainEnum,
    ProcessingState,
    ReadingStatusEnum,
    SourceEnum,
)
from app.models.domain import BatchRecord, Entry, ErrorLog, ManifestEntry
from app.models.http import (
    BatchPatchRequest,
    BatchRegisterRequest,
    EnrichmentStage1EntryWire,
    EnrichmentStage2EntryWire,
    ManifestBatchEntryWire,
    PreFilterResultEntryWire,
)

from app.alerts import emit_alert

logger = logging.getLogger(__name__)

TERMINAL_STATES = frozenset(
    {
        ProcessingState.RELEVANCE_REJECTED,
        ProcessingState.INDEXED,
        ProcessingState.PERMANENTLY_FAILED,
    }
)

MANIFEST_CLAIM_MAP: dict[ProcessingState, ProcessingState] = {
    ProcessingState.DISCOVERED: ProcessingState.RELEVANCE_QUEUED,
    ProcessingState.RELEVANCE_PASSED: ProcessingState.SCRAPE_QUEUED,
}

ENTRIES_CLAIM_MAP: dict[ProcessingState, ProcessingState] = {
    ProcessingState.SCRAPED: ProcessingState.ENRICHMENT_STAGE1_QUEUED,
    ProcessingState.ENRICHMENT_STAGE2_QUEUED: ProcessingState.ENRICHMENT_STAGE2_CLAIMED,
}

RETRY_TARGET_MAP: dict[ProcessingState, ProcessingState] = {
    ProcessingState.SCRAPE_FAILED: ProcessingState.RELEVANCE_PASSED,
    ProcessingState.ENRICHMENT_STAGE1_FAILED: ProcessingState.SCRAPED,
    ProcessingState.ENRICHMENT_STAGE2_FAILED: ProcessingState.ENRICHMENT_STAGE2_QUEUED,
    ProcessingState.VECTOR_WRITE_FAILED: ProcessingState.VECTOR_WRITE_QUEUED,
}

MANUAL_RETRY_TARGET_MAP: dict[ProcessingState, ProcessingState] = {
    ProcessingState.SCRAPE_QUEUED: ProcessingState.RELEVANCE_PASSED,
    ProcessingState.SCRAPE_FAILED: ProcessingState.RELEVANCE_PASSED,
    ProcessingState.ENRICHMENT_STAGE1_QUEUED: ProcessingState.SCRAPED,
    ProcessingState.ENRICHMENT_STAGE1_FAILED: ProcessingState.SCRAPED,
    ProcessingState.ENRICHMENT_STAGE2_CLAIMED: ProcessingState.ENRICHMENT_STAGE2_QUEUED,
    ProcessingState.ENRICHMENT_STAGE2_FAILED: ProcessingState.ENRICHMENT_STAGE2_QUEUED,
    ProcessingState.VECTOR_WRITE_QUEUED: ProcessingState.VECTOR_WRITE_QUEUED,
    ProcessingState.VECTOR_WRITE_FAILED: ProcessingState.VECTOR_WRITE_QUEUED,
}

LOCK_STATE_SWEEP_RESETS: dict[ProcessingState, ProcessingState] = {
    ProcessingState.RELEVANCE_QUEUED: ProcessingState.DISCOVERED,
    ProcessingState.SCRAPE_QUEUED: ProcessingState.RELEVANCE_PASSED,
    ProcessingState.ENRICHMENT_STAGE1_QUEUED: ProcessingState.SCRAPED,
    ProcessingState.ENRICHMENT_STAGE2_CLAIMED: ProcessingState.ENRICHMENT_STAGE2_QUEUED,
}

MANIFEST_LOCK_STATES = frozenset(
    {ProcessingState.RELEVANCE_QUEUED, ProcessingState.SCRAPE_QUEUED}
)
ENTRY_LOCK_STATES = frozenset(
    {
        ProcessingState.ENRICHMENT_STAGE1_QUEUED,
        ProcessingState.ENRICHMENT_STAGE2_CLAIMED,
    }
)

N3_FAILURE_NORMALIZATION: dict[ProcessingState, ProcessingState] = {
    ProcessingState.ENRICHMENT_STAGE1_SUBMITTED: ProcessingState.ENRICHMENT_STAGE1_FAILED,
    ProcessingState.ENRICHMENT_STAGE2_SUBMITTED: ProcessingState.ENRICHMENT_STAGE2_FAILED,
}

FAILURE_TARGET_MAP: dict[ProcessingState, ProcessingState] = {
    ProcessingState.SCRAPE_QUEUED: ProcessingState.SCRAPE_FAILED,
    ProcessingState.ENRICHMENT_STAGE1_QUEUED: ProcessingState.ENRICHMENT_STAGE1_FAILED,
    ProcessingState.ENRICHMENT_STAGE1_SUBMITTED: ProcessingState.ENRICHMENT_STAGE1_FAILED,
    ProcessingState.ENRICHMENT_STAGE2_CLAIMED: ProcessingState.ENRICHMENT_STAGE2_FAILED,
    ProcessingState.ENRICHMENT_STAGE2_SUBMITTED: ProcessingState.ENRICHMENT_STAGE2_FAILED,
    ProcessingState.VECTOR_WRITE_QUEUED: ProcessingState.VECTOR_WRITE_FAILED,
}

FATAL_HTTP_STATUSES = frozenset({400, 410})
ESCALATION_HTTP_STATUSES = frozenset({401, 403, 404, 422})

DEFAULT_RETRY_BASE_DELAY_SEC = 60


class TransitionError(Exception):
    """Base class for transition failures surfaced to routers."""


class NotFoundError(TransitionError):
    def __init__(self, source_id: str) -> None:
        self.source_id = source_id
        super().__init__(f"source_id not found: {source_id}")


class InvalidTransitionError(TransitionError):
    def __init__(self, source_id: str, from_state: str, to_state: str) -> None:
        self.source_id = source_id
        self.from_state = from_state
        self.to_state = to_state
        super().__init__(
            f"invalid transition for {source_id}: {from_state} -> {to_state}"
        )


class TerminalStateError(TransitionError):
    def __init__(self, source_id: str) -> None:
        self.source_id = source_id
        super().__init__(f"terminal state for {source_id}")


class ProvenanceIncompleteError(TransitionError):
    def __init__(self, source_id: str) -> None:
        self.source_id = source_id
        super().__init__(f"provenance incomplete for {source_id}")


class BatchNotFoundError(TransitionError):
    def __init__(self, batch_id: str) -> None:
        self.batch_id = batch_id
        super().__init__(f"batch not found: {batch_id}")


class BatchConflictError(TransitionError):
    def __init__(self, batch_id: str) -> None:
        self.batch_id = batch_id
        super().__init__(f"batch already exists: {batch_id}")


class BatchInvalidStateError(TransitionError):
    def __init__(self, batch_id: str, status: str) -> None:
        self.batch_id = batch_id
        self.status = status
        super().__init__(f"invalid batch state for timeout: {batch_id} ({status})")


@dataclass(frozen=True)
class BatchTimeoutResult:
    batch_id: str
    status: BatchStatusEnum
    entries_reset: int


@dataclass(frozen=True)
class PollClaimResult:
    entries: list[Any]
    claimed_count: int
    transitioned_to: str | None


@dataclass(frozen=True)
class IngestManifestResult:
    inserted: int
    skipped: int


@dataclass(frozen=True)
class PreFilterResultsResult:
    updated: int
    passed: int
    rejected: int


def normalize_failure_state(state_at_failure: ProcessingState) -> ProcessingState:
    """N3: map SUBMITTED states to corresponding FAILED for ErrorLog writes."""
    return N3_FAILURE_NORMALIZATION.get(state_at_failure, state_at_failure)


def assert_pre_filter_provenance(manifest: ManifestEntry) -> None:
    """M2: Stage 3 entry creation requires completed pre-filter provenance."""
    if (
        manifest.profile_version is None
        or manifest.pre_filter_batch_id is None
        or manifest.pre_filter_rationale is None
    ):
        raise ProvenanceIncompleteError(manifest.source_id)


def resolve_retry_target(state_at_failure: ProcessingState) -> ProcessingState:
    """Canonical retry target from §6.2 / §14.2 mapping tables."""
    if state_at_failure in RETRY_TARGET_MAP:
        return RETRY_TARGET_MAP[state_at_failure]
    if state_at_failure in MANUAL_RETRY_TARGET_MAP:
        return MANUAL_RETRY_TARGET_MAP[state_at_failure]
    raise InvalidTransitionError(
        state_at_failure.value,
        state_at_failure.value,
        "retry_target",
    )


def compute_next_retry_at(retry_count: int, *, now: datetime | None = None) -> datetime:
    """Exponential backoff with ±20% jitter per §6.4."""
    base = now or datetime.now(UTC)
    delay = DEFAULT_RETRY_BASE_DELAY_SEC * (2**retry_count)
    jitter = delay * 0.2 * (2 * random.random() - 1)
    return base + timedelta(seconds=max(1, int(delay + jitter)))


def _prepare_conn(conn: aiosqlite.Connection) -> None:
    conn.row_factory = aiosqlite.Row


async def _insert_row(
    conn: aiosqlite.Connection, table: str, row: dict[str, Any]
) -> None:
    columns = ", ".join(f'"{key}"' for key in row)
    placeholders = ", ".join("?" for _ in row)
    await conn.execute(
        f'INSERT INTO "{table}" ({columns}) VALUES ({placeholders})',
        tuple(row.values()),
    )


def _parse_state(value: str) -> ProcessingState:
    return ProcessingState(value)


def _guard_terminal(state: ProcessingState, source_id: str) -> None:
    if state in TERMINAL_STATES:
        raise TerminalStateError(source_id)


def _row_to_manifest(row: aiosqlite.Row | dict[str, Any]) -> ManifestEntry:
    data = dict(row)
    data["source"] = SourceEnum(data["source"])
    data["domain"] = DomainEnum(data["domain"])
    data["processing_state"] = _parse_state(data["processing_state"])
    for key in ("published_at", "discovered_at", "next_retry_at"):
        if data.get(key):
            data[key] = datetime.fromisoformat(data[key])
    return ManifestEntry.model_validate(data)


def _row_to_entry(row: aiosqlite.Row | dict[str, Any]) -> Entry:
    return Entry.from_db_row(dict(row))


async def _fetch_manifest(
    conn: aiosqlite.Connection, source_id: str
) -> ManifestEntry | None:
    _prepare_conn(conn)
    cursor = await conn.execute(
        "SELECT * FROM manifest WHERE source_id = ?", (source_id,)
    )
    row = await cursor.fetchone()
    return _row_to_manifest(row) if row else None


async def _fetch_entry(
    conn: aiosqlite.Connection, source_id: str
) -> Entry | None:
    cursor = await conn.execute(
        "SELECT * FROM entries WHERE source_id = ?", (source_id,)
    )
    row = await cursor.fetchone()
    return _row_to_entry(row) if row else None


async def _set_manifest_state(
    conn: aiosqlite.Connection,
    source_id: str,
    new_state: ProcessingState,
    *,
    expected: ProcessingState | None = None,
) -> None:
    if expected is not None:
        cursor = await conn.execute(
            "SELECT processing_state FROM manifest WHERE source_id = ?",
            (source_id,),
        )
        row = await cursor.fetchone()
        if row is None:
            raise NotFoundError(source_id)
        current = _parse_state(row[0])
        if current != expected:
            raise InvalidTransitionError(
                source_id, current.value, new_state.value
            )
    await conn.execute(
        "UPDATE manifest SET processing_state = ? WHERE source_id = ?",
        (new_state.value, source_id),
    )


async def _set_entry_state(
    conn: aiosqlite.Connection,
    source_id: str,
    new_state: ProcessingState,
    *,
    expected: ProcessingState | None = None,
) -> None:
    if expected is not None:
        cursor = await conn.execute(
            "SELECT processing_state FROM entries WHERE source_id = ?",
            (source_id,),
        )
        row = await cursor.fetchone()
        if row is None:
            raise NotFoundError(source_id)
        current = _parse_state(row[0])
        if current != expected:
            raise InvalidTransitionError(
                source_id, current.value, new_state.value
            )
    await conn.execute(
        "UPDATE entries SET processing_state = ? WHERE source_id = ?",
        (new_state.value, source_id),
    )


async def _sync_pipeline_state(
    conn: aiosqlite.Connection, source_id: str, new_state: ProcessingState
) -> None:
    """Keep manifest and entry processing_state aligned when entry exists."""
    await _set_manifest_state(conn, source_id, new_state)
    entry = await _fetch_entry(conn, source_id)
    if entry is not None:
        await _set_entry_state(conn, source_id, new_state)


async def _fetch_batch(
    conn: aiosqlite.Connection, batch_id: str
) -> BatchRecord | None:
    _prepare_conn(conn)
    cursor = await conn.execute(
        "SELECT * FROM batches WHERE batch_id = ?", (batch_id,)
    )
    row = await cursor.fetchone()
    return BatchRecord.from_db_row(dict(row)) if row else None


async def register_batch(
    conn: aiosqlite.Connection,
    request: BatchRegisterRequest,
    *,
    created_at: datetime | None = None,
) -> BatchRecord:
    """Insert BatchRecord at Anthropic submit time; 409 on duplicate batch_id."""
    existing = await _fetch_batch(conn, request.batch_id)
    if existing is not None:
        raise BatchConflictError(request.batch_id)

    now = created_at or datetime.now(UTC)
    record = BatchRecord(
        batch_id=request.batch_id,
        batch_type=request.batch_type,
        domain=request.domain,
        profile_version=request.profile_version,
        profile_render_hash=request.profile_render_hash,
        status=BatchStatusEnum.SUBMITTED,
        created_at=now,
        submitted_at=now,
        entry_count=request.entry_count,
        passed_count=0,
        failed_count=0,
        source_ids=list(request.source_ids),
        external_batch_id=request.external_batch_id,
    )
    await _insert_row(conn, "batches", record.to_db_row())
    await conn.commit()
    logger.info(
        "batch registered",
        extra={
            "batch_id": request.batch_id,
            "external_batch_id": request.external_batch_id,
            "event": "batch_registered",
        },
    )
    return record


async def patch_batch(
    conn: aiosqlite.Connection,
    batch_id: str,
    request: BatchPatchRequest,
) -> BatchRecord:
    """Update batch lifecycle fields; 404 if batch_id missing."""
    existing = await _fetch_batch(conn, batch_id)
    if existing is None:
        raise BatchNotFoundError(batch_id)

    updates: dict[str, Any] = {"status": request.status.value}
    if request.passed_count is not None:
        updates["passed_count"] = request.passed_count
    if request.failed_count is not None:
        updates["failed_count"] = request.failed_count
    if request.completed_at is not None:
        updates["completed_at"] = request.completed_at.isoformat()
    if request.external_batch_id is not None:
        updates["external_batch_id"] = request.external_batch_id

    set_clause = ", ".join(f'"{key}" = ?' for key in updates)
    await conn.execute(
        f"UPDATE batches SET {set_clause} WHERE batch_id = ?",
        (*updates.values(), batch_id),
    )
    await conn.commit()

    updated = await _fetch_batch(conn, batch_id)
    assert updated is not None
    logger.info(
        "batch patched",
        extra={
            "batch_id": batch_id,
            "event": "batch_patched",
            "passed": request.passed_count,
            "rejected": request.failed_count,
        },
    )
    return updated


async def apply_batch_timeout(
    conn: aiosqlite.Connection,
    batch_id: str,
) -> BatchTimeoutResult:
    """
    Mark batch batch_timed_out and reset RELEVANCE_QUEUED manifest rows
    whose source_id is in the batch source_ids list to DISCOVERED.
    """
    batch = await _fetch_batch(conn, batch_id)
    if batch is None:
        raise BatchNotFoundError(batch_id)

    if batch.status == BatchStatusEnum.BATCH_TIMED_OUT:
        return BatchTimeoutResult(
            batch_id=batch_id,
            status=BatchStatusEnum.BATCH_TIMED_OUT,
            entries_reset=0,
        )

    if batch.status not in {
        BatchStatusEnum.SUBMITTED,
        BatchStatusEnum.PROCESSING,
        BatchStatusEnum.PENDING,
    }:
        raise BatchInvalidStateError(batch_id, batch.status.value)

    entries_reset = 0
    for source_id in batch.source_ids:
        manifest = await _fetch_manifest(conn, source_id)
        if manifest is None:
            continue
        if manifest.processing_state != ProcessingState.RELEVANCE_QUEUED:
            continue
        await _set_manifest_state(
            conn,
            source_id,
            ProcessingState.DISCOVERED,
            expected=ProcessingState.RELEVANCE_QUEUED,
        )
        entries_reset += 1
        logger.info(
            "batch timeout entry reset",
            extra={
                "batch_id": batch_id,
                "source_id": source_id,
                "event": "batch_timeout_reset",
                "entries_reset": entries_reset,
            },
        )

    await conn.execute(
        "UPDATE batches SET status = ? WHERE batch_id = ?",
        (BatchStatusEnum.BATCH_TIMED_OUT.value, batch_id),
    )
    await conn.commit()
    logger.warning(
        "batch timed out",
        extra={
            "batch_id": batch_id,
            "event": "batch_timed_out",
            "entries_reset": entries_reset,
        },
    )
    return BatchTimeoutResult(
        batch_id=batch_id,
        status=BatchStatusEnum.BATCH_TIMED_OUT,
        entries_reset=entries_reset,
    )


async def ingest_manifest_batch(
    conn: aiosqlite.Connection,
    entries: list[ManifestBatchEntryWire],
    *,
    discovered_at: datetime | None = None,
) -> IngestManifestResult:
    """Idempotent manifest ingest — skip existing source_id rows."""
    _prepare_conn(conn)
    now = discovered_at or datetime.now(UTC)
    inserted = 0
    skipped = 0
    for wire in entries:
        cursor = await conn.execute(
            "SELECT 1 FROM manifest WHERE source_id = ?", (wire.source_id,)
        )
        if await cursor.fetchone():
            skipped += 1
            logger.warning(
                "manifest ingest skip",
                extra={"source_id": wire.source_id},
            )
            continue
        manifest = ManifestEntry(
            source_id=wire.source_id,
            source=wire.source,
            url=wire.url,
            title=wire.title,
            abstract=wire.abstract,
            published_at=wire.published_at,
            discovered_at=now,
            domain=DomainEnum(wire.domain),
            processing_state=ProcessingState.DISCOVERED,
            retry_count=0,
        )
        await _insert_row(conn, "manifest", manifest.to_db_row())
        inserted += 1
    await conn.commit()
    return IngestManifestResult(inserted=inserted, skipped=skipped)


async def claim_manifest_poll(
    conn: aiosqlite.Connection,
    state: ProcessingState,
    *,
    domain: DomainEnum | None = None,
    limit: int = 50,
) -> PollClaimResult:
    """Atomic claim for manifest poll states (DISCOVERED, RELEVANCE_PASSED)."""
    _prepare_conn(conn)
    lock_state = MANIFEST_CLAIM_MAP.get(state)
    if lock_state is None:
        return PollClaimResult(entries=[], claimed_count=0, transitioned_to=None)

    await conn.execute("BEGIN")
    try:
        query = (
            "SELECT * FROM manifest WHERE processing_state = ?"
            + (" AND domain = ?" if domain else "")
            + " ORDER BY discovered_at LIMIT ?"
        )
        params: list[Any] = [state.value]
        if domain:
            params.append(domain.value)
        params.append(limit)
        cursor = await conn.execute(query, params)
        rows = await cursor.fetchall()
        source_ids = [row["source_id"] for row in rows]
        for source_id in source_ids:
            await conn.execute(
                "UPDATE manifest SET processing_state = ? WHERE source_id = ? AND processing_state = ?",
                (lock_state.value, source_id, state.value),
            )
        await conn.commit()
    except Exception:
        await conn.rollback()
        raise

    claimed: list[ManifestEntry] = []
    for row in rows:
        entry = _row_to_manifest(row)
        entry.processing_state = lock_state
        claimed.append(entry)
    return PollClaimResult(
        entries=claimed,
        claimed_count=len(claimed),
        transitioned_to=lock_state.value,
    )


async def claim_entries_poll(
    conn: aiosqlite.Connection,
    state: ProcessingState,
    *,
    domain: DomainEnum | None = None,
    limit: int = 50,
) -> PollClaimResult:
    """Atomic claim for entry poll states; VECTOR_WRITE_QUEUED returns without claim."""
    _prepare_conn(conn)
    if state == ProcessingState.VECTOR_WRITE_QUEUED:
        query = (
            "SELECT * FROM entries WHERE processing_state = ?"
            + (" AND domain = ?" if domain else "")
            + " ORDER BY ingested_at LIMIT ?"
        )
        params: list[Any] = [state.value]
        if domain:
            params.append(domain.value)
        params.append(limit)
        cursor = await conn.execute(query, params)
        rows = await cursor.fetchall()
        entries = [_row_to_entry(row) for row in rows]
        return PollClaimResult(
            entries=entries,
            claimed_count=len(entries),
            transitioned_to=None,
        )

    lock_state = ENTRIES_CLAIM_MAP.get(state)
    if lock_state is None:
        return PollClaimResult(entries=[], claimed_count=0, transitioned_to=None)

    await conn.execute("BEGIN")
    try:
        query = (
            "SELECT * FROM entries WHERE processing_state = ?"
            + (" AND domain = ?" if domain else "")
            + " ORDER BY ingested_at LIMIT ?"
        )
        params = [state.value]
        if domain:
            params.append(domain.value)
        params.append(limit)
        cursor = await conn.execute(query, params)
        rows = await cursor.fetchall()
        source_ids = [row["source_id"] for row in rows]
        for source_id in source_ids:
            await conn.execute(
                "UPDATE entries SET processing_state = ? WHERE source_id = ? AND processing_state = ?",
                (lock_state.value, source_id, state.value),
            )
            await conn.execute(
                "UPDATE manifest SET processing_state = ? WHERE source_id = ?",
                (lock_state.value, source_id),
            )
        await conn.commit()
    except Exception:
        await conn.rollback()
        raise

    claimed: list[Entry] = []
    for row in rows:
        entry = _row_to_entry(row)
        entry.processing_state = lock_state
        claimed.append(entry)
    return PollClaimResult(
        entries=claimed,
        claimed_count=len(claimed),
        transitioned_to=lock_state.value,
    )


async def apply_pre_filter_results(
    conn: aiosqlite.Connection,
    batch_id: str,
    profile_version: str,
    entries: list[PreFilterResultEntryWire],
) -> PreFilterResultsResult:
    updated = 0
    passed = 0
    rejected = 0
    for item in entries:
        manifest = await _fetch_manifest(conn, item.source_id)
        if manifest is None:
            raise NotFoundError(item.source_id)
        _guard_terminal(manifest.processing_state, item.source_id)

        if manifest.processing_state == ProcessingState.RELEVANCE_QUEUED:
            target = (
                ProcessingState.RELEVANCE_PASSED
                if item.decision == 1
                else ProcessingState.RELEVANCE_REJECTED
            )
        elif manifest.processing_state in {
            ProcessingState.RELEVANCE_PASSED,
            ProcessingState.RELEVANCE_REJECTED,
        }:
            if (
                manifest.pre_filter_batch_id == batch_id
                and manifest.relevance_decision == item.decision
            ):
                continue
            target = manifest.processing_state
        else:
            raise InvalidTransitionError(
                item.source_id,
                manifest.processing_state.value,
                "pre_filter_result",
            )

        if item.decision == 1:
            passed += 1
        else:
            rejected += 1

        await conn.execute(
            """
            UPDATE manifest SET
                profile_version = ?,
                pre_filter_batch_id = ?,
                relevance_decision = ?,
                pre_filter_rationale = ?,
                processing_state = ?
            WHERE source_id = ?
            """,
            (
                profile_version,
                batch_id,
                item.decision,
                item.pre_filter_rationale,
                target.value,
                item.source_id,
            ),
        )
        updated += 1
        logger.info(
            "transition",
            extra={
                "source_id": item.source_id,
                "from_state": manifest.processing_state.value,
                "to_state": target.value,
                "batch_id": batch_id,
            },
        )
    await conn.commit()
    return PreFilterResultsResult(updated=updated, passed=passed, rejected=rejected)


async def create_entry_from_content(
    conn: aiosqlite.Connection,
    source_id: str,
    content_raw: str,
    *,
    ingested_at: datetime | None = None,
) -> tuple[str, ProcessingState]:
    """Create Entry from manifest + content; transition manifest to SCRAPED."""
    manifest = await _fetch_manifest(conn, source_id)
    if manifest is None:
        raise NotFoundError(source_id)
    _guard_terminal(manifest.processing_state, source_id)

    existing = await _fetch_entry(conn, source_id)
    if existing is not None:
        if manifest.processing_state == ProcessingState.SCRAPED:
            return existing.id, ProcessingState.SCRAPED
        raise InvalidTransitionError(
            source_id,
            manifest.processing_state.value,
            ProcessingState.SCRAPED.value,
        )

    if manifest.processing_state not in {
        ProcessingState.RELEVANCE_PASSED,
        ProcessingState.SCRAPE_QUEUED,
    }:
        raise InvalidTransitionError(
            source_id,
            manifest.processing_state.value,
            ProcessingState.SCRAPED.value,
        )

    assert_pre_filter_provenance(manifest)

    now = ingested_at or datetime.now(UTC)
    entry_id = str(uuid.uuid4())
    entry = Entry(
        id=entry_id,
        source_id=manifest.source_id,
        source=manifest.source,
        url=manifest.url,
        title=manifest.title,
        content_raw=content_raw,
        published_at=manifest.published_at,
        ingested_at=now,
        domain=manifest.domain,
        profile_version=manifest.profile_version,  # type: ignore[arg-type]
        pre_filter_batch_id=manifest.pre_filter_batch_id,  # type: ignore[arg-type]
        pre_filter_rationale=manifest.pre_filter_rationale,  # type: ignore[arg-type]
        processing_state=ProcessingState.SCRAPED,
    )
    await _insert_row(conn, "entries", entry.to_db_row())
    await _set_manifest_state(
        conn,
        source_id,
        ProcessingState.SCRAPED,
        expected=manifest.processing_state,
    )
    await conn.commit()
    return entry_id, ProcessingState.SCRAPED


async def mark_enrichment_stage1_submitted(
    conn: aiosqlite.Connection,
    source_ids: list[str],
    batch_id: str,
) -> int:
    """Transition claimed entries to ENRICHMENT_STAGE1_SUBMITTED after batch submit."""
    count = 0
    for source_id in source_ids:
        entry = await _fetch_entry(conn, source_id)
        if entry is None:
            raise NotFoundError(source_id)
        if entry.processing_state == ProcessingState.ENRICHMENT_STAGE1_SUBMITTED:
            if entry.enrichment_stage1_batch_id == batch_id:
                continue
        elif entry.processing_state != ProcessingState.ENRICHMENT_STAGE1_QUEUED:
            raise InvalidTransitionError(
                source_id,
                entry.processing_state.value,
                ProcessingState.ENRICHMENT_STAGE1_SUBMITTED.value,
            )
        await conn.execute(
            """
            UPDATE entries SET
                processing_state = ?,
                enrichment_stage1_batch_id = ?
            WHERE source_id = ?
            """,
            (
                ProcessingState.ENRICHMENT_STAGE1_SUBMITTED.value,
                batch_id,
                source_id,
            ),
        )
        await _set_manifest_state(
            conn, source_id, ProcessingState.ENRICHMENT_STAGE1_SUBMITTED
        )
        count += 1
    await conn.commit()
    return count


async def mark_enrichment_stage2_submitted(
    conn: aiosqlite.Connection,
    source_ids: list[str],
    batch_id: str,
) -> int:
    """Transition claimed entries to ENRICHMENT_STAGE2_SUBMITTED after batch submit."""
    count = 0
    for source_id in source_ids:
        entry = await _fetch_entry(conn, source_id)
        if entry is None:
            raise NotFoundError(source_id)
        if entry.processing_state == ProcessingState.ENRICHMENT_STAGE2_SUBMITTED:
            if entry.enrichment_stage2_batch_id == batch_id:
                continue
        elif entry.processing_state != ProcessingState.ENRICHMENT_STAGE2_CLAIMED:
            raise InvalidTransitionError(
                source_id,
                entry.processing_state.value,
                ProcessingState.ENRICHMENT_STAGE2_SUBMITTED.value,
            )
        await conn.execute(
            """
            UPDATE entries SET
                processing_state = ?,
                enrichment_stage2_batch_id = ?
            WHERE source_id = ?
            """,
            (
                ProcessingState.ENRICHMENT_STAGE2_SUBMITTED.value,
                batch_id,
                source_id,
            ),
        )
        await _set_manifest_state(
            conn, source_id, ProcessingState.ENRICHMENT_STAGE2_SUBMITTED
        )
        count += 1
    await conn.commit()
    return count


async def apply_enrichment_stage1_results(
    conn: aiosqlite.Connection,
    batch_id: str,
    entries: list[EnrichmentStage1EntryWire],
) -> None:
    for item in entries:
        entry = await _fetch_entry(conn, item.source_id)
        if entry is None:
            raise NotFoundError(item.source_id)
        _guard_terminal(entry.processing_state, item.source_id)

        if not item.success:
            await _record_enrichment_failure(
                conn,
                item.source_id,
                ProcessingState.ENRICHMENT_STAGE1_SUBMITTED,
                item.error_message or "enrichment stage1 failed",
                batch_id=batch_id,
            )
            continue

        if entry.processing_state == ProcessingState.ENRICHMENT_STAGE2_QUEUED:
            continue

        if entry.processing_state != ProcessingState.ENRICHMENT_STAGE1_SUBMITTED:
            raise InvalidTransitionError(
                item.source_id,
                entry.processing_state.value,
                ProcessingState.ENRICHMENT_STAGE2_QUEUED.value,
            )

        await _h3_enrichment_stage1_success(conn, item, batch_id)


async def _h3_enrichment_stage1_success(
    conn: aiosqlite.Connection,
    item: EnrichmentStage1EntryWire,
    batch_id: str,
) -> None:
    """H3: COMPLETE + field writes + ENRICHMENT_STAGE2_QUEUED in one transaction."""
    concepts_json = json.dumps(item.concepts) if item.concepts is not None else None
    tags_json = json.dumps(item.tags) if item.tags is not None else None
    hooks_json = (
        json.dumps(item.challenge_hooks) if item.challenge_hooks is not None else None
    )
    entry_type = item.entry_type.value if item.entry_type else None

    await conn.execute("BEGIN")
    try:
        await conn.execute(
            "UPDATE entries SET processing_state = ? WHERE source_id = ?",
            (ProcessingState.ENRICHMENT_STAGE1_COMPLETE.value, item.source_id),
        )
        await conn.execute(
            """
            UPDATE entries SET
                summary = ?,
                concepts = ?,
                tags = ?,
                entry_type = ?,
                challenge_hooks = ?,
                enrichment_stage1_batch_id = ?
            WHERE source_id = ?
            """,
            (
                item.summary,
                concepts_json,
                tags_json,
                entry_type,
                hooks_json,
                batch_id,
                item.source_id,
            ),
        )
        await conn.execute(
            "UPDATE entries SET processing_state = ? WHERE source_id = ?",
            (ProcessingState.ENRICHMENT_STAGE2_QUEUED.value, item.source_id),
        )
        await conn.execute(
            "UPDATE manifest SET processing_state = ? WHERE source_id = ?",
            (ProcessingState.ENRICHMENT_STAGE2_QUEUED.value, item.source_id),
        )
        await conn.commit()
    except Exception:
        await conn.rollback()
        raise


async def apply_enrichment_stage2_results(
    conn: aiosqlite.Connection,
    batch_id: str,
    entries: list[EnrichmentStage2EntryWire],
) -> None:
    for item in entries:
        entry = await _fetch_entry(conn, item.source_id)
        if entry is None:
            raise NotFoundError(item.source_id)
        _guard_terminal(entry.processing_state, item.source_id)

        if not item.success:
            await _record_enrichment_failure(
                conn,
                item.source_id,
                ProcessingState.ENRICHMENT_STAGE2_SUBMITTED,
                item.error_message or "enrichment stage2 failed",
                batch_id=batch_id,
            )
            continue

        if entry.processing_state == ProcessingState.VECTOR_WRITE_QUEUED:
            continue

        if entry.processing_state != ProcessingState.ENRICHMENT_STAGE2_SUBMITTED:
            raise InvalidTransitionError(
                item.source_id,
                entry.processing_state.value,
                ProcessingState.VECTOR_WRITE_QUEUED.value,
            )

        await _h3_enrichment_stage2_success(conn, item, batch_id)


async def _h3_enrichment_stage2_success(
    conn: aiosqlite.Connection,
    item: EnrichmentStage2EntryWire,
    batch_id: str,
) -> None:
    await conn.execute("BEGIN")
    try:
        await conn.execute(
            "UPDATE entries SET processing_state = ? WHERE source_id = ?",
            (ProcessingState.ENRICHMENT_STAGE2_COMPLETE.value, item.source_id),
        )
        await conn.execute(
            """
            UPDATE entries SET
                relevance_score = ?,
                relevance_reason = ?,
                value_rationale = ?,
                enrichment_stage2_batch_id = ?
            WHERE source_id = ?
            """,
            (
                item.relevance_score,
                item.relevance_reason,
                item.value_rationale,
                batch_id,
                item.source_id,
            ),
        )
        await conn.execute(
            "UPDATE entries SET processing_state = ? WHERE source_id = ?",
            (ProcessingState.VECTOR_WRITE_QUEUED.value, item.source_id),
        )
        await conn.execute(
            "UPDATE manifest SET processing_state = ? WHERE source_id = ?",
            (ProcessingState.VECTOR_WRITE_QUEUED.value, item.source_id),
        )
        await conn.commit()
    except Exception:
        await conn.rollback()
        raise


async def _record_enrichment_failure(
    conn: aiosqlite.Connection,
    source_id: str,
    submitted_state: ProcessingState,
    message: str,
    *,
    batch_id: str,
) -> None:
    normalized = normalize_failure_state(submitted_state)
    failed_state = FAILURE_TARGET_MAP.get(
        submitted_state, normalized
    )
    await record_failure(
        conn,
        source_id=source_id,
        state_at_failure=submitted_state,
        error_class="EnrichmentBatchError",
        http_status=None,
        message=message,
        is_retriable=True,
        target_failed_state=failed_state,
        batch_id=batch_id,
    )


async def mark_indexed(conn: aiosqlite.Connection, source_id: str) -> None:
    _prepare_conn(conn)
    entry = await _fetch_entry(conn, source_id)
    if entry is None:
        raise NotFoundError(source_id)
    if entry.processing_state == ProcessingState.INDEXED:
        logger.warning(
            "mark_indexed idempotent no-op",
            extra={"source_id": source_id},
        )
        return
    if entry.processing_state != ProcessingState.VECTOR_WRITE_QUEUED:
        raise InvalidTransitionError(
            source_id,
            entry.processing_state.value,
            ProcessingState.INDEXED.value,
        )
    await _sync_pipeline_state(conn, source_id, ProcessingState.INDEXED)
    await conn.commit()


async def record_failure(
    conn: aiosqlite.Connection,
    *,
    source_id: str,
    state_at_failure: ProcessingState,
    error_class: str,
    http_status: int | None,
    message: str,
    is_retriable: bool,
    target_failed_state: ProcessingState | None = None,
    batch_id: str | None = None,
) -> None:
    manifest = await _fetch_manifest(conn, source_id)
    if manifest is None:
        raise NotFoundError(source_id)
    _guard_terminal(manifest.processing_state, source_id)

    normalized = normalize_failure_state(state_at_failure)
    failed_state = target_failed_state or FAILURE_TARGET_MAP.get(
        state_at_failure, normalized
    )

    alert_type: str | None = None
    if http_status in FATAL_HTTP_STATUSES:
        target = ProcessingState.PERMANENTLY_FAILED
        next_retry_at = None
        new_retry_count = manifest.retry_count
        alert_type = "permanent_failure"
    elif not is_retriable or http_status in ESCALATION_HTTP_STATUSES:
        target = ProcessingState.ESCALATION_FLAGGED
        next_retry_at = None
        new_retry_count = manifest.retry_count
        alert_type = "escalation_flagged"
    elif manifest.retry_count + 1 >= RETRY_MAX_ATTEMPTS:
        target = ProcessingState.ESCALATION_FLAGGED
        next_retry_at = None
        new_retry_count = manifest.retry_count + 1
        alert_type = "retry_budget_exhausted"
    else:
        target = failed_state
        new_retry_count = manifest.retry_count + 1
        next_retry_at = compute_next_retry_at(new_retry_count)

    error_id = str(uuid.uuid4())
    now = datetime.now(UTC)
    error_log = ErrorLog(
        id=error_id,
        source_id=source_id,
        attempt_number=new_retry_count,
        state_at_failure=normalized,
        error_class=error_class,
        http_status=http_status,
        message=message,
        is_retriable=is_retriable,
        timestamp=now,
        next_retry_at=next_retry_at,
    )
    await _insert_row(conn, "error_log", error_log.to_db_row())

    await conn.execute(
        """
        UPDATE manifest SET
            processing_state = ?,
            retry_count = ?,
            next_retry_at = ?
        WHERE source_id = ?
        """,
        (
            target.value,
            new_retry_count,
            next_retry_at.isoformat() if next_retry_at else None,
            source_id,
        ),
    )
    entry = await _fetch_entry(conn, source_id)
    if entry is not None:
        entry_target = (
            target if target in TERMINAL_STATES or target == ProcessingState.ESCALATION_FLAGGED
            else failed_state
        )
        await conn.execute(
            "UPDATE entries SET processing_state = ?, flagged_for_review = ? WHERE source_id = ?",
            (
                entry_target.value,
                int(target == ProcessingState.ESCALATION_FLAGGED),
                source_id,
            ),
        )
    if alert_type is not None:
        await emit_alert(
            conn,
            source_id=source_id,
            alert_type=alert_type,
            message=message,
            state_at_failure=normalized,
            attempt_number=new_retry_count,
        )
    await conn.commit()
    logger.error(
        "transition failure",
        extra={
            "source_id": source_id,
            "from_state": state_at_failure.value,
            "to_state": target.value,
            "batch_id": batch_id,
        },
    )


async def manual_retry(conn: aiosqlite.Connection, source_id: str) -> ProcessingState:
    manifest = await _fetch_manifest(conn, source_id)
    if manifest is None:
        raise NotFoundError(source_id)

    cursor = await conn.execute(
        """
        SELECT state_at_failure FROM error_log
        WHERE source_id = ?
        ORDER BY timestamp DESC
        LIMIT 1
        """,
        (source_id,),
    )
    row = await cursor.fetchone()
    if row is None:
        raise InvalidTransitionError(source_id, manifest.processing_state.value, "retry")

    state_at_failure = _parse_state(row[0])
    target = resolve_retry_target(state_at_failure)

    await conn.execute(
        """
        UPDATE manifest SET
            processing_state = ?,
            retry_count = 0,
            next_retry_at = NULL
        WHERE source_id = ?
        """,
        (target.value, source_id),
    )
    entry = await _fetch_entry(conn, source_id)
    if entry is not None:
        await conn.execute(
            "UPDATE entries SET processing_state = ?, flagged_for_review = 0 WHERE source_id = ?",
            (target.value, source_id),
        )
    await conn.commit()
    return target


async def run_lock_state_recovery_sweep(
    conn: aiosqlite.Connection,
    threshold_sec: int,
    *,
    now: datetime | None = None,
) -> int:
    """
  Reset stuck lock states per §6.2.

  Age proxy: manifest lock states use discovered_at; entry lock states use ingested_at
  (no state_entered_at column in §7 — see T2 decision log).
    """
    reference = now or datetime.now(UTC)
    cutoff = (reference - timedelta(seconds=threshold_sec)).isoformat()
    reset_count = 0

    for lock_state, work_ready in LOCK_STATE_SWEEP_RESETS.items():
        if lock_state in MANIFEST_LOCK_STATES:
            cursor = await conn.execute(
                """
                SELECT source_id FROM manifest
                WHERE processing_state = ? AND discovered_at <= ?
                """,
                (lock_state.value, cutoff),
            )
            source_ids = [row[0] for row in await cursor.fetchall()]
            for source_id in source_ids:
                await _set_manifest_state(conn, source_id, work_ready, expected=lock_state)
                reset_count += 1
                logger.info(
                    "sweep_reset",
                    extra={
                        "source_id": source_id,
                        "from_state": lock_state.value,
                        "to_state": work_ready.value,
                    },
                )
        else:
            cursor = await conn.execute(
                """
                SELECT source_id FROM entries
                WHERE processing_state = ? AND ingested_at <= ?
                """,
                (lock_state.value, cutoff),
            )
            source_ids = [row[0] for row in await cursor.fetchall()]
            for source_id in source_ids:
                await _set_entry_state(conn, source_id, work_ready, expected=lock_state)
                await _set_manifest_state(conn, source_id, work_ready)
                reset_count += 1
                logger.info(
                    "sweep_reset",
                    extra={
                        "source_id": source_id,
                        "from_state": lock_state.value,
                        "to_state": work_ready.value,
                    },
                )
    if reset_count:
        await conn.commit()
    return reset_count


async def run_retry_sweep(
    conn: aiosqlite.Connection,
    max_attempts: int | None = None,
    *,
    now: datetime | None = None,
) -> int:
    """Re-enqueue eligible _FAILED manifest rows per §6.2 retry mapping."""
    reference = now or datetime.now(UTC)
    cutoff = reference.isoformat()
    limit = max_attempts if max_attempts is not None else RETRY_MAX_ATTEMPTS
    failed_values = tuple(s.value for s in RETRY_TARGET_MAP)
    cursor = await conn.execute(
        f"""
        SELECT source_id, processing_state, retry_count FROM manifest
        WHERE processing_state IN ({",".join("?" for _ in failed_values)})
          AND next_retry_at IS NOT NULL
          AND next_retry_at <= ?
          AND retry_count < ?
        """,
        (*failed_values, cutoff, limit),
    )
    rows = await cursor.fetchall()
    requeue_count = 0
    for row in rows:
        source_id = row[0]
        failed_state = _parse_state(row[1])
        target = RETRY_TARGET_MAP[failed_state]
        await conn.execute(
            """
            UPDATE manifest SET
                processing_state = ?,
                next_retry_at = NULL
            WHERE source_id = ?
            """,
            (target.value, source_id),
        )
        entry = await _fetch_entry(conn, source_id)
        if entry is not None:
            await conn.execute(
                "UPDATE entries SET processing_state = ? WHERE source_id = ?",
                (target.value, source_id),
            )
        requeue_count += 1
        logger.info(
            "retry_requeue",
            extra={
                "source_id": source_id,
                "from_state": failed_state.value,
                "to_state": target.value,
            },
        )
    if requeue_count:
        await conn.commit()
    return requeue_count
