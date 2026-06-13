"""Batch list and enriched detail routes (M7 T5)."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

from app.config import STATE_WORKER_BASE_URL
from app.models import BatchDetailEnrichedResponse, BatchEntrySummary
from app.sqlite_reader import read_entries_by_source_ids
from app.stores.duckdb_reader import DuckDbReader

router = APIRouter(tags=["batches"])

TABLE_NAME = "entries_mirror"
_TOP_ENTRIES_LIMIT = 20


def _state_worker_get(path: str, *, query: str = "") -> tuple[int, dict[str, Any] | None]:
    base = STATE_WORKER_BASE_URL.rstrip("/")
    url = f"{base}{path}"
    if query:
        url = f"{url}?{query}"
    request = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read()
            status = response.status
    except urllib.error.HTTPError as exc:
        return exc.code, None
    except urllib.error.URLError:
        return 502, None

    payload: dict[str, Any] = json.loads(body) if body else {}
    return status, payload


def _fetch_top_entries_duckdb(
    metadata: DuckDbReader,
    source_ids: list[str],
    *,
    limit: int = _TOP_ENTRIES_LIMIT,
) -> list[BatchEntrySummary]:
    if not source_ids:
        return []

    placeholders = ",".join("?" for _ in source_ids)
    sql = f"""
        SELECT source_id, title, summary, relevance_score, entry_type, tags
        FROM {TABLE_NAME}
        WHERE source_id IN ({placeholders})
        ORDER BY relevance_score DESC NULLS LAST
        LIMIT ?
    """
    conn = metadata.connect()
    rows = conn.execute(sql, [*source_ids, limit]).fetchall()
    results: list[BatchEntrySummary] = []
    for row in rows:
        tags_raw = row[5]
        tags: list[str] | None = None
        if tags_raw is not None:
            if isinstance(tags_raw, str):
                tags = json.loads(tags_raw)
            else:
                tags = list(tags_raw)
        results.append(
            BatchEntrySummary(
                source_id=str(row[0]),
                title=str(row[1]),
                summary=str(row[2]) if row[2] is not None else None,
                relevance_score=float(row[3]) if row[3] is not None else None,
                entry_type=str(row[4]) if row[4] is not None else None,
                tags=tags,
            )
        )
    return results


@router.get("/batches")
def get_batches(status: str = Query(...)) -> JSONResponse:
    code, payload = _state_worker_get("/batches", query=f"status={status}")
    if payload is None:
        return JSONResponse(
            status_code=code,
            content={"error": "upstream_error", "status": code},
        )
    return JSONResponse(status_code=code, content=payload)


@router.get("/batches/{batch_id}", response_model=BatchDetailEnrichedResponse)
def get_batch_detail(
    batch_id: str,
    request: Request,
) -> BatchDetailEnrichedResponse | JSONResponse:
    code, payload = _state_worker_get(f"/batches/{batch_id}")
    if payload is None:
        return JSONResponse(
            status_code=code,
            content={"error": "upstream_error", "status": code},
        )
    if code != 200:
        return JSONResponse(status_code=code, content=payload)

    batch = payload.get("batch", {})
    source_ids = batch.get("source_ids") or batch.get("top_entries") or []
    if not isinstance(source_ids, list):
        source_ids = []

    stores = request.app.state.stores
    entries = _fetch_top_entries_duckdb(stores.metadata, source_ids)
    if not entries and source_ids:
        entries = read_entries_by_source_ids(source_ids, limit=_TOP_ENTRIES_LIMIT)

    return BatchDetailEnrichedResponse(batch=batch, entries=entries)
