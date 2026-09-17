"""Manifest ingest and poll routes."""

from __future__ import annotations

from typing import Annotated, Any

import aiosqlite
from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from app.db import get_db
from app.enums import DomainEnum, ProcessingState
from app.models.domain import ManifestEntry
from app.models.http import (
    ManifestBatchRequest,
    ManifestBatchResponse,
    ManifestCountResponse,
    PollResponse,
)
from app.transitions import (
    MANIFEST_CLAIM_MAP,
    claim_manifest_poll,
    count_manifest,
    ingest_manifest_batch,
)

router = APIRouter(tags=["manifest"])

MANIFEST_POLL_STATES = frozenset(MANIFEST_CLAIM_MAP.keys())


async def _db_conn() -> aiosqlite.Connection:
    async with get_db() as conn:
        yield conn


DbConn = Annotated[aiosqlite.Connection, Depends(_db_conn)]


def _invalid_poll_state(state: str) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content={"error": "invalid_poll_state", "state": state},
    )


def _parse_manifest_poll_state(state: str) -> ProcessingState | JSONResponse:
    try:
        processing_state = ProcessingState(state)
    except ValueError:
        return _invalid_poll_state(state)
    if processing_state not in MANIFEST_POLL_STATES:
        return _invalid_poll_state(state)
    return processing_state


def _serialize_manifest(entry: ManifestEntry) -> dict[str, Any]:
    return entry.model_dump(mode="json")


@router.post("/manifest/batch", response_model=ManifestBatchResponse)
async def post_manifest_batch(
    body: ManifestBatchRequest,
    conn: DbConn,
) -> ManifestBatchResponse:
    result = await ingest_manifest_batch(conn, body.entries)
    return ManifestBatchResponse(inserted=result.inserted, skipped=result.skipped)


@router.get("/manifest/count", response_model=ManifestCountResponse)
async def get_manifest_count(
    conn: DbConn,
    state: list[str] = Query(default=[]),
    source: str | None = None,
) -> ManifestCountResponse | JSONResponse:
    if not state:
        return JSONResponse(
            status_code=400,
            content={"error": "invalid_state", "state": None},
        )
    parsed: list[ProcessingState] = []
    for raw in state:
        try:
            parsed.append(ProcessingState(raw))
        except ValueError:
            return JSONResponse(
                status_code=400,
                content={"error": "invalid_state", "state": raw},
            )
    count = await count_manifest(conn, source=source, states=parsed)
    return ManifestCountResponse(count=count)


@router.get("/manifest/poll", response_model=PollResponse)
async def get_manifest_poll(
    conn: DbConn,
    state: str = Query(...),
    domain: DomainEnum | None = None,
    limit: int = Query(default=50),
) -> PollResponse | JSONResponse:
    parsed = _parse_manifest_poll_state(state)
    if isinstance(parsed, JSONResponse):
        return parsed
    result = await claim_manifest_poll(
        conn,
        parsed,
        domain=domain,
        limit=limit,
    )
    return PollResponse(
        entries=[_serialize_manifest(entry) for entry in result.entries],
        claimed_count=result.claimed_count,
        transitioned_to=result.transitioned_to,
    )
