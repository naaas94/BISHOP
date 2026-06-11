"""Scraper state read/write routes."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

import aiosqlite
from fastapi import APIRouter, Depends, Response

from app.db import get_db
from app.enums import SourceEnum
from app.models.domain import ScraperState
from app.models.http import ScraperStateResponse, ScraperStateUpdateRequest

router = APIRouter(tags=["scraper-state"])


async def _db_conn() -> aiosqlite.Connection:
    async with get_db() as conn:
        yield conn


DbConn = Annotated[aiosqlite.Connection, Depends(_db_conn)]


@router.get("/scraper-state/{source}", response_model=ScraperStateResponse)
async def get_scraper_state(
    source: SourceEnum,
    conn: DbConn,
) -> ScraperStateResponse:
    conn.row_factory = aiosqlite.Row
    cursor = await conn.execute(
        "SELECT * FROM scraper_state WHERE source = ?", (source.value,)
    )
    row = await cursor.fetchone()
    if row is None:
        now = datetime.now(UTC)
        return ScraperStateResponse(
            source=source,
            last_successful_run_at=None,
            updated_at=now,
        )
    state = ScraperState.from_db_row(dict(row))
    return ScraperStateResponse(
        source=state.source,
        last_successful_run_at=state.last_successful_run_at,
        updated_at=state.updated_at,
    )


@router.post("/scraper-state/{source}")
async def post_scraper_state(
    source: SourceEnum,
    body: ScraperStateUpdateRequest,
    conn: DbConn,
) -> Response:
    now = datetime.now(UTC)
    conn.row_factory = aiosqlite.Row
    cursor = await conn.execute(
        "SELECT 1 FROM scraper_state WHERE source = ?", (source.value,)
    )
    exists = await cursor.fetchone()
    if exists:
        await conn.execute(
            """
            UPDATE scraper_state SET
                last_successful_run_at = ?,
                updated_at = ?
            WHERE source = ?
            """,
            (body.timestamp.isoformat(), now.isoformat(), source.value),
        )
    else:
        state = ScraperState(
            source=source,
            last_successful_run_at=body.timestamp,
            updated_at=now,
        )
        row = state.to_db_row()
        columns = ", ".join(f'"{key}"' for key in row)
        placeholders = ", ".join("?" for _ in row)
        await conn.execute(
            f'INSERT INTO scraper_state ({columns}) VALUES ({placeholders})',
            tuple(row.values()),
        )
    await conn.commit()
    return Response(status_code=204)
