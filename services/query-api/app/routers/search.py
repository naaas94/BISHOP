"""Search route — RRF fusion with metadata pre-filter (M7 T5)."""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

from app.models import SearchHit, SearchResponse
from app.retrieval.search import run_search
from app.stores.duckdb_reader import DuckDbReader
from bishop_shared.query_config import DEFAULT_SEARCH_DOMAIN

logger = logging.getLogger(__name__)

router = APIRouter(tags=["search"])

TABLE_NAME = "entries_mirror"


def _parse_tags(raw: str | None) -> list[str] | None:
    if raw is None or not raw.strip():
        return None
    return [part.strip() for part in raw.split(",") if part.strip()]


def _fetch_hit_metadata(
    metadata: DuckDbReader,
    source_ids: list[str],
) -> dict[str, dict[str, Any]]:
    if not source_ids:
        return {}
    placeholders = ",".join("?" for _ in source_ids)
    sql = f"""
        SELECT source_id, title, summary, relevance_score, entry_type, tags
        FROM {TABLE_NAME}
        WHERE source_id IN ({placeholders})
    """
    conn = metadata.connect()
    rows = conn.execute(sql, source_ids).fetchall()
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        source_id = str(row[0])
        tags_raw = row[5]
        tags: list[str] | None = None
        if tags_raw is not None:
            if isinstance(tags_raw, str):
                tags = json.loads(tags_raw)
            else:
                tags = list(tags_raw)
        result[source_id] = {
            "title": str(row[1]),
            "summary": str(row[2]) if row[2] is not None else None,
            "relevance_score": float(row[3]) if row[3] is not None else None,
            "entry_type": str(row[4]) if row[4] is not None else None,
            "tags": tags,
        }
    return result


@router.get("/search", response_model=SearchResponse)
def get_search(
    request: Request,
    q: str = Query(..., min_length=1),
    domain: str | None = None,
    source: str | None = None,
    tags: str | None = None,
    min_relevance: float | None = Query(default=None, ge=0.0, le=1.0),
    days: int | None = Query(default=None, ge=1),
    type: str | None = None,
    reading_status: str | None = None,
) -> SearchResponse | JSONResponse:
    stores = request.app.state.stores
    parsed_tags = _parse_tags(tags)
    search_domain = domain or DEFAULT_SEARCH_DOMAIN
    truncated_query = q[:200]

    logger.info(
        "search dispatch",
        extra={
            "event": "search_dispatch",
            "query": truncated_query,
            "domain": search_domain,
        },
    )

    try:
        orchestration = run_search(
            query=q,
            bm25=stores.bm25,
            dense=stores.dense,
            metadata=stores.metadata,
            encoder=stores.encoder,
            domain=search_domain,
            source=source,
            tags=parsed_tags,
            min_relevance=min_relevance,
            days=days,
            entry_type=type,
            reading_status=reading_status,
        )
    except ValueError as exc:
        return JSONResponse(
            status_code=400,
            content={"error": "invalid_query", "detail": str(exc)},
        )

    metadata_map = _fetch_hit_metadata(
        stores.metadata,
        [source_id for source_id, _ in orchestration.hits],
    )

    hits: list[SearchHit] = []
    for source_id, rrf_score in orchestration.hits:
        fields = metadata_map.get(source_id, {})
        hits.append(
            SearchHit(
                source_id=source_id,
                rrf_score=rrf_score,
                title=fields.get("title", source_id),
                summary=fields.get("summary"),
                relevance_score=fields.get("relevance_score"),
                entry_type=fields.get("entry_type"),
                tags=fields.get("tags"),
            )
        )

    return SearchResponse(
        query=orchestration.query,
        problem_shaped=orchestration.problem_shaped,
        channels_active=list(orchestration.channels_active),
        hits=hits,
        total=len(hits),
    )
