"""Batch query routes."""

from __future__ import annotations

from typing import Annotated

import aiosqlite
from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from app.db import get_db
from app.enums import BatchStatusEnum
from app.models.domain import BatchRecord
from app.models.http import BatchDetailResponse, BatchesListResponse

router = APIRouter(tags=["batches"])


async def _db_conn() -> aiosqlite.Connection:
    async with get_db() as conn:
        yield conn


DbConn = Annotated[aiosqlite.Connection, Depends(_db_conn)]


def _parse_status_filter(status: str) -> list[BatchStatusEnum] | JSONResponse:
    statuses: list[BatchStatusEnum] = []
    for part in status.split(","):
        token = part.strip()
        if not token:
            continue
        try:
            statuses.append(BatchStatusEnum(token))
        except ValueError:
            return JSONResponse(
                status_code=400,
                content={"error": "invalid_batch_status", "status": token},
            )
    return statuses


async def _fetch_batches_by_status(
    conn: aiosqlite.Connection, statuses: list[BatchStatusEnum]
) -> list[BatchRecord]:
    if not statuses:
        return []
    conn.row_factory = aiosqlite.Row
    placeholders = ",".join("?" for _ in statuses)
    status_values = [item.value for item in statuses]
    cursor = await conn.execute(
        f"SELECT * FROM batches WHERE status IN ({placeholders}) ORDER BY created_at",
        status_values,
    )
    rows = await cursor.fetchall()
    return [BatchRecord.from_db_row(dict(row)) for row in rows]


@router.get("/batches", response_model=BatchesListResponse)
async def get_batches(
    conn: DbConn,
    status: str = Query(...),
) -> BatchesListResponse | JSONResponse:
    parsed = _parse_status_filter(status)
    if isinstance(parsed, JSONResponse):
        return parsed
    batches = await _fetch_batches_by_status(conn, parsed)
    return BatchesListResponse(batches=batches)


@router.get("/batches/{batch_id}", response_model=BatchDetailResponse)
async def get_batch_detail(
    batch_id: str,
    conn: DbConn,
) -> BatchDetailResponse | JSONResponse:
    conn.row_factory = aiosqlite.Row
    cursor = await conn.execute(
        "SELECT * FROM batches WHERE batch_id = ?", (batch_id,)
    )
    row = await cursor.fetchone()
    if row is None:
        return JSONResponse(
            status_code=404,
            content={"error": "not_found", "batch_id": batch_id},
        )
    return BatchDetailResponse(batch=BatchRecord.from_db_row(dict(row)))
