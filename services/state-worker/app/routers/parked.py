"""Soft-launch parked inbox — list and promote."""

from __future__ import annotations

from typing import Annotated

import aiosqlite
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.db import get_db
from app.models.http import (
    ParkedEntryWire,
    ParkedListResponse,
    PromoteParkedRequest,
    PromoteParkedResponse,
)
from app.transitions import (
    TransitionError,
    list_parked_manifests,
    promote_parked,
)

from app.routers.entries import _transition_error_response

router = APIRouter(tags=["parked"])


async def _db_conn() -> aiosqlite.Connection:
    async with get_db() as conn:
        yield conn


DbConn = Annotated[aiosqlite.Connection, Depends(_db_conn)]


@router.get("/parked", response_model=ParkedListResponse)
async def get_parked(conn: DbConn) -> ParkedListResponse:
    rows = await list_parked_manifests(conn)
    return ParkedListResponse(
        entries=[
            ParkedEntryWire(
                source_id=row.source_id,
                title=row.title,
                abstract=row.abstract,
                source=row.source,
                url=row.url,
                pre_filter_rationale=row.pre_filter_rationale,
                pre_filter_tier=row.pre_filter_tier,
                discovered_at=row.discovered_at,
                processing_state=row.processing_state,
            )
            for row in rows
        ]
    )


@router.post("/parked/promote", response_model=PromoteParkedResponse)
async def post_parked_promote(
    body: PromoteParkedRequest,
    conn: DbConn,
) -> PromoteParkedResponse | JSONResponse:
    try:
        processing_state = await promote_parked(conn, body.source_id)
    except TransitionError as exc:
        return _transition_error_response(exc)
    return PromoteParkedResponse(
        source_id=body.source_id,
        processing_state=processing_state,
    )
