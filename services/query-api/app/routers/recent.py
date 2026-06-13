"""Recent entries route — DuckDB ingested_at ordering (M7 T5)."""

from __future__ import annotations

from fastapi import APIRouter, Query, Request

from app.models import RecentHit, RecentResponse

router = APIRouter(tags=["recent"])


@router.get("/recent", response_model=RecentResponse)
def get_recent(
    request: Request,
    source: str | None = None,
    days: int = Query(default=7, ge=1),
    domain: str | None = None,
) -> RecentResponse:
    stores = request.app.state.stores
    rows = stores.metadata.recent(source=source, days=days, domain=domain)
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
