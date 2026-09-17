"""Entry routes — read-only SQLite GET and state-worker write proxies (M7/M8 T6)."""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.config import STATE_WORKER_BASE_URL
from app.models import EntryResponse
from app.sqlite_reader import read_entry

logger = logging.getLogger(__name__)

router = APIRouter(tags=["entries"])

READING_STATUS_VALUES = frozenset({"unread", "reading", "read", "archived"})


class ReadingStatusPatchBody(BaseModel):
    reading_status: str = Field(..., min_length=1)


def _proxy_state_worker(
    method: str,
    path: str,
    *,
    body: dict[str, Any] | None = None,
) -> JSONResponse:
    base = STATE_WORKER_BASE_URL.rstrip("/")
    url = f"{base}{path}"
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"} if data is not None else {}
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read()
            status = response.status
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        try:
            payload = json.loads(raw) if raw else {"error": "upstream_error", "status": exc.code}
        except json.JSONDecodeError:
            payload = {"error": "upstream_error", "status": exc.code}
        return JSONResponse(status_code=exc.code, content=payload)
    except urllib.error.URLError:
        return JSONResponse(
            status_code=502,
            content={"error": "upstream_error", "status": 502},
        )

    payload: dict[str, Any] = json.loads(raw) if raw else {}
    return JSONResponse(status_code=status, content=payload)


@router.get("/entries/{source_id:path}", response_model=EntryResponse)
def get_entry(source_id: str) -> EntryResponse | JSONResponse:
    try:
        entry = read_entry(source_id)
    except Exception:
        logger.exception(
            "sqlite read failed",
            extra={"event": "sqlite_read_failed", "source_id": source_id},
        )
        return JSONResponse(
            status_code=500,
            content={"error": "sqlite_read_failed"},
        )

    if entry is None:
        return JSONResponse(
            status_code=404,
            content={"error": "not_found", "source_id": source_id},
        )
    return entry


@router.post("/entries/{source_id:path}/retry")
def post_entry_retry(source_id: str) -> JSONResponse:
    logger.info(
        "manual retry proxy",
        extra={"event": "manual_retry", "source_id": source_id},
    )
    return _proxy_state_worker(
        "POST",
        "/entries/retry",
        body={"source_id": source_id},
    )


@router.post("/entries/{source_id:path}/permanent-fail")
def post_entry_permanent_fail(source_id: str) -> JSONResponse:
    logger.info(
        "manual permanent-fail proxy",
        extra={"event": "manual_permanent_fail", "source_id": source_id},
    )
    return _proxy_state_worker(
        "POST",
        "/entries/permanent-fail",
        body={"source_id": source_id},
    )


@router.patch("/entries/{source_id:path}/reading-status")
def patch_entry_reading_status(
    source_id: str,
    body: ReadingStatusPatchBody,
) -> JSONResponse:
    if body.reading_status not in READING_STATUS_VALUES:
        return JSONResponse(
            status_code=422,
            content={"error": "validation_error", "detail": "invalid reading_status"},
        )
    logger.info(
        "reading-status proxy",
        extra={
            "event": "manual_reading_status",
            "source_id": source_id,
            "reading_status": body.reading_status,
        },
    )
    quoted = urllib.parse.quote(source_id, safe="")
    return _proxy_state_worker(
        "PATCH",
        f"/entries/{quoted}/reading-status",
        body={"reading_status": body.reading_status},
    )
