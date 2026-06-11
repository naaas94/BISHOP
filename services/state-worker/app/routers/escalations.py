"""Escalation panel query routes."""

from __future__ import annotations

from typing import Annotated

import aiosqlite
from fastapi import APIRouter, Depends

from app.db import get_db
from app.enums import ProcessingState, SourceEnum
from app.models.domain import ErrorLog
from app.models.http import EscalationEntryWire, EscalationsResponse

router = APIRouter(tags=["escalations"])


async def _db_conn() -> aiosqlite.Connection:
    async with get_db() as conn:
        yield conn


DbConn = Annotated[aiosqlite.Connection, Depends(_db_conn)]


@router.get("/escalations", response_model=EscalationsResponse)
async def get_escalations(conn: DbConn) -> EscalationsResponse:
    conn.row_factory = aiosqlite.Row
    cursor = await conn.execute(
        """
        SELECT source_id, title, source, url, processing_state
        FROM manifest
        WHERE processing_state = ?
        ORDER BY discovered_at
        """,
        (ProcessingState.ESCALATION_FLAGGED.value,),
    )
    rows = await cursor.fetchall()
    entries: list[EscalationEntryWire] = []
    for row in rows:
        source_id = row["source_id"]
        err_cursor = await conn.execute(
            """
            SELECT * FROM error_log
            WHERE source_id = ?
            ORDER BY timestamp
            """,
            (source_id,),
        )
        error_rows = await err_cursor.fetchall()
        error_log = [ErrorLog.from_db_row(dict(item)) for item in error_rows]
        entries.append(
            EscalationEntryWire(
                source_id=source_id,
                title=row["title"],
                source=SourceEnum(row["source"]),
                url=row["url"],
                processing_state=ProcessingState(row["processing_state"]),
                error_log=error_log,
            )
        )
    return EscalationsResponse(entries=entries)
