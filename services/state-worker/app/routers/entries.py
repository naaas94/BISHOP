"""Entry write routes — content, enrichment results, failures, retry, pre-filter."""

from __future__ import annotations

from typing import Annotated

import aiosqlite
from fastapi import APIRouter, Depends, Response
from fastapi.responses import JSONResponse

from app.db import get_db
from app.models.http import (
    ContentPostRequest,
    ContentPostResponse,
    EnrichmentStage1ResultsRequest,
    EnrichmentStage2ResultsRequest,
    FailedPostRequest,
    IndexedPostRequest,
    PreFilterResultsRequest,
    PreFilterResultsResponse,
    RetryPostRequest,
    RetryPostResponse,
)
from app.transitions import (
    InvalidTransitionError,
    NotFoundError,
    ProvenanceIncompleteError,
    TerminalStateError,
    TransitionError,
    apply_enrichment_stage1_results,
    apply_enrichment_stage2_results,
    apply_pre_filter_results,
    create_entry_from_content,
    manual_retry,
    mark_indexed,
    record_failure,
)

router = APIRouter(tags=["entries"])


async def _db_conn() -> aiosqlite.Connection:
    async with get_db() as conn:
        yield conn


DbConn = Annotated[aiosqlite.Connection, Depends(_db_conn)]


def _transition_error_response(exc: TransitionError) -> JSONResponse:
    if isinstance(exc, NotFoundError):
        return JSONResponse(
            status_code=404,
            content={"error": "not_found", "source_id": exc.source_id},
        )
    if isinstance(exc, ProvenanceIncompleteError):
        return JSONResponse(
            status_code=409,
            content={"error": "provenance_incomplete", "source_id": exc.source_id},
        )
    if isinstance(exc, InvalidTransitionError):
        return JSONResponse(
            status_code=409,
            content={
                "error": "invalid_transition",
                "source_id": exc.source_id,
                "from_state": exc.from_state,
                "to_state": exc.to_state,
            },
        )
    if isinstance(exc, TerminalStateError):
        return JSONResponse(
            status_code=409,
            content={"error": "terminal_state", "source_id": exc.source_id},
        )
    raise exc


@router.post(
    "/manifest/pre-filter-results",
    response_model=PreFilterResultsResponse,
)
async def post_pre_filter_results(
    body: PreFilterResultsRequest,
    conn: DbConn,
) -> PreFilterResultsResponse | JSONResponse:
    try:
        result = await apply_pre_filter_results(
            conn,
            body.batch_id,
            body.profile_version,
            body.entries,
        )
    except TransitionError as exc:
        return _transition_error_response(exc)
    return PreFilterResultsResponse(
        updated=result.updated,
        passed=result.passed,
        rejected=result.rejected,
    )


@router.post("/entries/content", response_model=ContentPostResponse)
async def post_entries_content(
    body: ContentPostRequest,
    conn: DbConn,
) -> ContentPostResponse | JSONResponse:
    try:
        entry_id, processing_state = await create_entry_from_content(
            conn,
            body.source_id,
            body.content_raw,
        )
    except TransitionError as exc:
        return _transition_error_response(exc)
    return ContentPostResponse(
        entry_id=entry_id,
        processing_state=processing_state,
    )


@router.post("/entries/enrichment-stage1-results")
async def post_enrichment_stage1_results(
    body: EnrichmentStage1ResultsRequest,
    conn: DbConn,
) -> Response:
    try:
        await apply_enrichment_stage1_results(
            conn,
            body.batch_id,
            body.entries,
        )
    except TransitionError as exc:
        return _transition_error_response(exc)
    return Response(status_code=204)


@router.post("/entries/enrichment-stage2-results")
async def post_enrichment_stage2_results(
    body: EnrichmentStage2ResultsRequest,
    conn: DbConn,
) -> Response:
    try:
        await apply_enrichment_stage2_results(
            conn,
            body.batch_id,
            body.entries,
        )
    except TransitionError as exc:
        return _transition_error_response(exc)
    return Response(status_code=204)


@router.post("/entries/indexed")
async def post_entries_indexed(
    body: IndexedPostRequest,
    conn: DbConn,
) -> Response:
    try:
        await mark_indexed(conn, body.source_id)
    except TransitionError as exc:
        return _transition_error_response(exc)
    return Response(status_code=204)


@router.post("/entries/failed")
async def post_entries_failed(
    body: FailedPostRequest,
    conn: DbConn,
) -> Response:
    try:
        await record_failure(
            conn,
            source_id=body.source_id,
            state_at_failure=body.state_at_failure,
            error_class=body.error_class,
            http_status=body.http_status,
            message=body.message,
            is_retriable=body.is_retriable,
        )
    except TransitionError as exc:
        return _transition_error_response(exc)
    return Response(status_code=204)


@router.post("/entries/retry", response_model=RetryPostResponse)
async def post_entries_retry(
    body: RetryPostRequest,
    conn: DbConn,
) -> RetryPostResponse | JSONResponse:
    try:
        processing_state = await manual_retry(conn, body.source_id)
    except TransitionError as exc:
        return _transition_error_response(exc)
    return RetryPostResponse(
        source_id=body.source_id,
        processing_state=processing_state,
    )
