"""§14.3 alert dual-write — CRITICAL log plus error_log ALERT row."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

import aiosqlite

from app.enums import ProcessingState
from app.models.domain import ErrorLog

logger = logging.getLogger(__name__)


async def _insert_row(
    conn: aiosqlite.Connection, table: str, row: dict[str, Any]
) -> None:
    columns = ", ".join(f'"{key}"' for key in row)
    placeholders = ", ".join("?" for _ in row)
    await conn.execute(
        f'INSERT INTO "{table}" ({columns}) VALUES ({placeholders})',
        tuple(row.values()),
    )

ALERT_ERROR_CLASS = "ALERT"


async def emit_alert(
    conn: aiosqlite.Connection,
    *,
    source_id: str,
    alert_type: str,
    message: str,
    state_at_failure: ProcessingState,
    attempt_number: int,
) -> None:
    """Write CRITICAL structured log and error_log row with error_class ALERT."""
    logger.critical(
        message,
        extra={
            "alert_type": alert_type,
            "source_id": source_id,
            "state_at_failure": state_at_failure.value,
            "attempt_number": attempt_number,
        },
    )
    now = datetime.now(UTC)
    alert_row = ErrorLog(
        id=str(uuid.uuid4()),
        source_id=source_id,
        attempt_number=attempt_number,
        state_at_failure=state_at_failure,
        error_class=ALERT_ERROR_CLASS,
        http_status=None,
        message=message,
        is_retriable=False,
        timestamp=now,
        next_retry_at=None,
    )
    await _insert_row(conn, "error_log", alert_row.to_db_row())
