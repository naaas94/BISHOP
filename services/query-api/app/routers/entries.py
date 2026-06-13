"""Entry detail route — read-only SQLite (M7 T5)."""

from __future__ import annotations

import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.models import EntryResponse
from app.sqlite_reader import read_entry

logger = logging.getLogger(__name__)

router = APIRouter(tags=["entries"])


@router.get("/entries/{source_id}", response_model=EntryResponse)
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
