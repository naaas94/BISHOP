"""Batch query and lifecycle routes."""

from __future__ import annotations

from typing import Annotated

import aiosqlite
from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse

from app.db import get_db
from app.enums import BatchStatusEnum
from app.models.domain import BatchRecord
from app.models.http import (
    BatchDetailResponse,
    BatchPatchRequest,
    BatchRegisterRequest,
    BatchRegisterResponse,
    BatchTimeoutResponse,
    BatchesListResponse,
)
from app.transitions import (
    BatchConflictError,
    BatchInvalidStateError,
    BatchNotFoundError,
    BatchSourceStateError,
    NotFoundError,
    TransitionError,
    apply_batch_timeout,
    patch_batch,
    register_batch,
)

router = APIRouter(tags=["batches"])


async def _db_conn() -> aiosqlite.Connection:
    async with get_db() as conn:
        yield conn


DbConn = Annotated[aiosqlite.Connection, Depends(_db_conn)]


def _batch_error_response(exc: TransitionError) -> JSONResponse:
    if isinstance(exc, NotFoundError):
        return JSONResponse(
            status_code=404,
            content={"error": "not_found", "source_id": exc.source_id},
        )
    if isinstance(exc, BatchNotFoundError):
        return JSONResponse(
            status_code=404,
            content={"error": "not_found", "batch_id": exc.batch_id},
        )
    if isinstance(exc, BatchConflictError):
        return JSONResponse(
            status_code=409,
            content={"error": "batch_conflict", "batch_id": exc.batch_id},
        )
    if isinstance(exc, BatchSourceStateError):
        return JSONResponse(
            status_code=409,
            content={
                "error": "invalid_source_state",
                "source_id": exc.source_id,
                "state": exc.state,
            },
        )
    if isinstance(exc, BatchInvalidStateError):
        return JSONResponse(
            status_code=409,
            content={
                "error": "invalid_batch_state",
                "batch_id": exc.batch_id,
                "status": exc.status,
            },
        )
    raise exc


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


@router.post(
    "/batches",
    response_model=BatchRegisterResponse,
    status_code=status.HTTP_201_CREATED,
)
async def post_batches(
    body: BatchRegisterRequest,
    conn: DbConn,
) -> BatchRegisterResponse | JSONResponse:
    try:
        record = await register_batch(conn, body)
    except TransitionError as exc:
        return _batch_error_response(exc)
    return BatchRegisterResponse(batch_id=record.batch_id, status=record.status)


@router.patch("/batches/{batch_id}", response_model=BatchDetailResponse)
async def patch_batches(
    batch_id: str,
    body: BatchPatchRequest,
    conn: DbConn,
) -> BatchDetailResponse | JSONResponse:
    try:
        record = await patch_batch(conn, batch_id, body)
    except TransitionError as exc:
        return _batch_error_response(exc)
    return BatchDetailResponse(batch=record)


@router.post("/batches/{batch_id}/timeout", response_model=BatchTimeoutResponse)
async def post_batch_timeout(
    batch_id: str,
    conn: DbConn,
) -> BatchTimeoutResponse | JSONResponse:
    try:
        result = await apply_batch_timeout(conn, batch_id)
    except TransitionError as exc:
        return _batch_error_response(exc)
    return BatchTimeoutResponse(
        batch_id=result.batch_id,
        status=result.status,
        entries_reset=result.entries_reset,
    )


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
