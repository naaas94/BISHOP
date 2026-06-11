"""Entry poll routes."""

from __future__ import annotations

from typing import Annotated, Any

import aiosqlite
from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from app.db import get_db
from app.enums import DomainEnum, ProcessingState
from app.models.domain import Entry
from app.models.http import PollResponse
from app.transitions import ENTRIES_CLAIM_MAP, claim_entries_poll

router = APIRouter(tags=["poll"])

ENTRIES_POLL_STATES = frozenset(ENTRIES_CLAIM_MAP.keys()) | {
    ProcessingState.VECTOR_WRITE_QUEUED,
}


async def _db_conn() -> aiosqlite.Connection:
    async with get_db() as conn:
        yield conn


DbConn = Annotated[aiosqlite.Connection, Depends(_db_conn)]


def _invalid_poll_state(state: str) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content={"error": "invalid_poll_state", "state": state},
    )


def _parse_entries_poll_state(state: str) -> ProcessingState | JSONResponse:
    try:
        processing_state = ProcessingState(state)
    except ValueError:
        return _invalid_poll_state(state)
    if processing_state not in ENTRIES_POLL_STATES:
        return _invalid_poll_state(state)
    return processing_state


def _serialize_entry(entry: Entry, *, omit_content_raw: bool) -> dict[str, Any]:
    payload = entry.model_dump(mode="json")
    if omit_content_raw:
        payload.pop("content_raw", None)
    return payload


@router.get("/entries/poll", response_model=PollResponse)
async def get_entries_poll(
    conn: DbConn,
    state: str = Query(...),
    domain: DomainEnum | None = None,
    limit: int = Query(default=50),
) -> PollResponse | JSONResponse:
    parsed = _parse_entries_poll_state(state)
    if isinstance(parsed, JSONResponse):
        return parsed
    result = await claim_entries_poll(
        conn,
        parsed,
        domain=domain,
        limit=limit,
    )
    omit_content_raw = parsed == ProcessingState.VECTOR_WRITE_QUEUED
    return PollResponse(
        entries=[
            _serialize_entry(entry, omit_content_raw=omit_content_raw)
            for entry in result.entries
        ],
        claimed_count=result.claimed_count,
        transitioned_to=result.transitioned_to,
    )
