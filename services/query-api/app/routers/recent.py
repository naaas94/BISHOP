"""Recent entries route — DuckDB ingested_at ordering (M7 T5)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Query, Request

from app.models import RecentHit, RecentResponse
from app.stores.duckdb_reader import DuckDbLockUnavailableError

logger = logging.getLogger(__name__)

router = APIRouter(tags=["recent"])


@router.get("/recent", response_model=RecentResponse)
def get_recent(
    request: Request,
    source: str | None = None,
    days: int = Query(default=7, ge=1),
    domain: str | None = None,
) -> RecentResponse:
    stores = request.app.state.stores
    try:
        rows = stores.metadata.recent(source=source, days=days, domain=domain)
    except DuckDbLockUnavailableError:
        logger.warning(
            "duckdb recent read skipped — writer holds file lock",
            extra={"event": "duckdb_recent_lock_skip"},
        )
        rows = []
    entries = [
        RecentHit(
            source_id=row.source_id,
            source=row.source,
            title=row.title,
            ingested_at=row.ingested_at,
            domain=row.domain,
            entry_type=row.entry_type,
            relevance_score=row.relevance_score,
            summary=row.summary,
        )
        for row in rows
    ]
    return RecentResponse(entries=entries, total=len(entries))
