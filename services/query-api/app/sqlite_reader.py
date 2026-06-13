"""Read-only SQLite entry access for query-api (M7 T5)."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from bishop_shared.constants import SQLITE_DB_PATH

from app.models import BatchEntrySummary, EntryResponse

JSON_LIST_FIELDS = frozenset(
    {
        "concepts",
        "tags",
        "challenge_hooks",
        "references",
        "cited_by",
    }
)


def _decode_json_list_fields(row: dict[str, Any]) -> dict[str, Any]:
    decoded = dict(row)
    for key in JSON_LIST_FIELDS:
        value = decoded.get(key)
        if value is not None and isinstance(value, str):
            decoded[key] = json.loads(value)
    if isinstance(decoded.get("flagged_for_review"), int):
        decoded["flagged_for_review"] = bool(decoded["flagged_for_review"])
    return decoded


def _parse_datetime(value: str | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromisoformat(value)


def _row_to_entry(row: dict[str, Any]) -> EntryResponse:
    normalized = _decode_json_list_fields(row)
    return EntryResponse(
        id=str(normalized["id"]),
        source_id=str(normalized["source_id"]),
        source=str(normalized["source"]),
        url=str(normalized["url"]),
        title=str(normalized["title"]),
        content_raw=str(normalized["content_raw"]),
        published_at=_parse_datetime(normalized.get("published_at")),
        ingested_at=datetime.fromisoformat(str(normalized["ingested_at"])),
        domain=str(normalized["domain"]),
        profile_version=str(normalized["profile_version"]),
        pre_filter_batch_id=str(normalized["pre_filter_batch_id"]),
        pre_filter_rationale=str(normalized["pre_filter_rationale"]),
        summary=normalized.get("summary"),
        concepts=normalized.get("concepts"),
        tags=normalized.get("tags"),
        entry_type=normalized.get("entry_type"),
        challenge_hooks=normalized.get("challenge_hooks"),
        enrichment_stage1_batch_id=normalized.get("enrichment_stage1_batch_id"),
        relevance_score=normalized.get("relevance_score"),
        relevance_reason=normalized.get("relevance_reason"),
        value_rationale=normalized.get("value_rationale"),
        enrichment_stage2_batch_id=normalized.get("enrichment_stage2_batch_id"),
        references=normalized.get("references"),
        cited_by=normalized.get("cited_by"),
        reading_status=str(normalized["reading_status"]),
        flagged_for_review=bool(normalized["flagged_for_review"]),
        processing_state=str(normalized["processing_state"]),
    )


def read_entry(
    source_id: str,
    *,
    db_path: str | Path | None = None,
) -> EntryResponse | None:
    """Read a single entry by source_id using a read-only SQLite connection."""
    path = str(db_path or SQLITE_DB_PATH)
    uri = f"file:{path}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.execute(
            "SELECT * FROM entries WHERE source_id = ?",
            (source_id,),
        )
        row = cursor.fetchone()
    finally:
        conn.close()
    if row is None:
        return None
    return _row_to_entry(dict(row))


def read_entries_by_source_ids(
    source_ids: list[str],
    *,
    db_path: str | Path | None = None,
    limit: int = 20,
) -> list[BatchEntrySummary]:
    """Return entry summaries ordered by relevance_score desc (SQLite fallback)."""
    if not source_ids:
        return []

    path = str(db_path or SQLITE_DB_PATH)
    uri = f"file:{path}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    placeholders = ",".join("?" for _ in source_ids)
    try:
        cursor = conn.execute(
            f"""
            SELECT source_id, title, summary, relevance_score, entry_type, tags
            FROM entries
            WHERE source_id IN ({placeholders})
            ORDER BY relevance_score DESC NULLS LAST
            LIMIT ?
            """,
            [*source_ids, limit],
        )
        rows = cursor.fetchall()
    finally:
        conn.close()

    results: list[BatchEntrySummary] = []
    for row in rows:
        normalized = _decode_json_list_fields(dict(row))
        results.append(
            BatchEntrySummary(
                source_id=str(normalized["source_id"]),
                title=str(normalized["title"]),
                summary=normalized.get("summary"),
                relevance_score=normalized.get("relevance_score"),
                entry_type=normalized.get("entry_type"),
                tags=normalized.get("tags"),
            )
        )
    return results
