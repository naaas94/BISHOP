"""Unit tests for §14.3 alert dual-write and log-level contract (T8)."""

from __future__ import annotations

import asyncio
import sys
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_STATE_WORKER_ROOT = _REPO_ROOT / "services" / "state-worker"

for path in (_STATE_WORKER_ROOT, _REPO_ROOT):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

from app.alerts import ALERT_ERROR_CLASS, emit_alert  # noqa: E402
from app.config import RETRY_MAX_ATTEMPTS  # noqa: E402
from app.db import close_pool, get_db, init_pool, run_migrations  # noqa: E402
from app.enums import DomainEnum, ProcessingState, SourceEnum  # noqa: E402
from app.models.http import ManifestBatchEntryWire  # noqa: E402
from app.transitions import ingest_manifest_batch, record_failure  # noqa: E402

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


async def _seed_discovered(conn, source_id: str = _SOURCE) -> None:
    result = await ingest_manifest_batch(conn, [_wire_entry(source_id)])
    assert result.inserted == 1


@patch("app.alerts.logger.critical")
def test_record_failure_escalation_emits_critical_alert(
    mock_critical, temp_db: Path
) -> None:
    async def _run() -> None:
        await init_pool(str(temp_db), size=1)
        try:
            async with get_db() as conn:
                await _seed_discovered(conn)
                await conn.execute(
                    "UPDATE manifest SET retry_count = ? WHERE source_id = ?",
                    (RETRY_MAX_ATTEMPTS - 1, _SOURCE),
                )
                await conn.commit()
                await record_failure(
                    conn,
                    source_id=_SOURCE,
                    state_at_failure=ProcessingState.SCRAPE_QUEUED,
                    error_class="TimeoutError",
                    http_status=None,
                    message="timeout after retries",
                    is_retriable=True,
                )
                cursor = await conn.execute(
                    "SELECT error_class, message FROM error_log WHERE source_id = ?",
                    (_SOURCE,),
                )
                rows = await cursor.fetchall()
                alert_rows = [r for r in rows if r[0] == ALERT_ERROR_CLASS]
                assert len(alert_rows) == 1
                assert alert_rows[0][1] == "timeout after retries"
                cursor = await conn.execute(
                    "SELECT processing_state FROM manifest WHERE source_id = ?",
                    (_SOURCE,),
                )
                row = await cursor.fetchone()
                assert row[0] == ProcessingState.ESCALATION_FLAGGED.value
        finally:
            await close_pool()

    asyncio.run(_run())

    mock_critical.assert_called_once()
    extra = mock_critical.call_args.kwargs["extra"]
    assert extra["alert_type"] == "retry_budget_exhausted"
    assert extra["source_id"] == _SOURCE


@patch("app.alerts.logger.critical")
def test_record_failure_permanent_failure_emits_alert(
    mock_critical, temp_db: Path
) -> None:
    async def _run() -> None:
        await init_pool(str(temp_db), size=1)
        try:
            async with get_db() as conn:
                await _seed_discovered(conn)
                await record_failure(
                    conn,
                    source_id=_SOURCE,
                    state_at_failure=ProcessingState.SCRAPE_QUEUED,
                    error_class="HttpError",
                    http_status=410,
                    message="gone",
                    is_retriable=True,
                )
                cursor = await conn.execute(
                    "SELECT error_class FROM error_log WHERE source_id = ? AND error_class = ?",
                    (_SOURCE, ALERT_ERROR_CLASS),
                )
                assert await cursor.fetchone() is not None
        finally:
            await close_pool()

    asyncio.run(_run())

    mock_critical.assert_called_once()
    assert mock_critical.call_args.kwargs["extra"]["alert_type"] == "permanent_failure"


def test_emit_alert_writes_error_log_row(temp_db: Path) -> None:
    async def _run() -> None:
        await init_pool(str(temp_db), size=1)
        try:
            async with get_db() as conn:
                await _seed_discovered(conn)
                await emit_alert(
                    conn,
                    source_id=_SOURCE,
                    alert_type="escalation_flagged",
                    message="test alert",
                    state_at_failure=ProcessingState.SCRAPE_QUEUED,
                    attempt_number=1,
                )
                await conn.commit()
                cursor = await conn.execute(
                    """
                    SELECT error_class, message, state_at_failure, attempt_number
                    FROM error_log WHERE source_id = ? AND error_class = ?
                    """,
                    (_SOURCE, ALERT_ERROR_CLASS),
                )
                row = await cursor.fetchone()
                assert row is not None
                assert row[0] == ALERT_ERROR_CLASS
                assert row[1] == "test alert"
                assert row[2] == ProcessingState.SCRAPE_QUEUED.value
                assert row[3] == 1
        finally:
            await close_pool()

    asyncio.run(_run())


@patch("app.transitions.logger.warning")
def test_manifest_ingest_skip_logs_warning(mock_warning, temp_db: Path) -> None:
    async def _run() -> None:
        await init_pool(str(temp_db), size=1)
        try:
            async with get_db() as conn:
                await ingest_manifest_batch(conn, [_wire_entry()])
                result = await ingest_manifest_batch(conn, [_wire_entry()])
                assert result.skipped == 1
        finally:
            await close_pool()

    asyncio.run(_run())

    mock_warning.assert_called_once()
    assert mock_warning.call_args.args[0] == "manifest ingest skip"
    assert mock_warning.call_args.kwargs["extra"]["source_id"] == _SOURCE


@patch("app.transitions.logger.error")
def test_record_failure_logs_error_not_info(mock_error, temp_db: Path) -> None:
    async def _run() -> None:
        await init_pool(str(temp_db), size=1)
        try:
            async with get_db() as conn:
                await _seed_discovered(conn)
                await record_failure(
                    conn,
                    source_id=_SOURCE,
                    state_at_failure=ProcessingState.SCRAPE_QUEUED,
                    error_class="TimeoutError",
                    http_status=None,
                    message="transient",
                    is_retriable=True,
                )
        finally:
            await close_pool()

    asyncio.run(_run())

    mock_error.assert_called_once()
    assert mock_error.call_args.args[0] == "transition failure"
    assert mock_error.call_args.kwargs["extra"]["source_id"] == _SOURCE


@patch("app.alerts.logger.critical")
def test_retriable_failure_without_alert_does_not_emit_critical(
    mock_critical, temp_db: Path
) -> None:
    """Falsifier: sub-threshold retriable failure must not produce §14.3 alert."""
    async def _run() -> None:
        await init_pool(str(temp_db), size=1)
        try:
            async with get_db() as conn:
                await _seed_discovered(conn)
                await record_failure(
                    conn,
                    source_id=_SOURCE,
                    state_at_failure=ProcessingState.SCRAPE_QUEUED,
                    error_class="TimeoutError",
                    http_status=None,
                    message="transient",
                    is_retriable=True,
                )
                cursor = await conn.execute(
                    "SELECT COUNT(*) FROM error_log WHERE source_id = ? AND error_class = ?",
                    (_SOURCE, ALERT_ERROR_CLASS),
                )
                row = await cursor.fetchone()
                assert row[0] == 0
        finally:
            await close_pool()

    asyncio.run(_run())

    mock_critical.assert_not_called()
