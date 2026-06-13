"""DuckDB metadata mirror store (spec §8.3; plan Flag 2 DDL binding)."""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import duckdb

from bishop_shared.indexing_config import DUCKDB_PATH

TABLE_NAME = "entries_mirror"

_DDL = f"""
CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
    source_id VARCHAR PRIMARY KEY,
    source VARCHAR NOT NULL,
    url VARCHAR NOT NULL,
    title VARCHAR NOT NULL,
    published_at VARCHAR,
    ingested_at VARCHAR NOT NULL,
    domain VARCHAR NOT NULL,
    entry_type VARCHAR,
    relevance_score DOUBLE,
    reading_status VARCHAR NOT NULL,
    summary VARCHAR,
    tags JSON,
    concepts JSON,
    challenge_hooks JSON
)
"""

_UPSERT_SQL = f"""
INSERT OR REPLACE INTO {TABLE_NAME} (
    source_id, source, url, title, published_at, ingested_at, domain,
    entry_type, relevance_score, reading_status, summary,
    tags, concepts, challenge_hooks
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""


@dataclass(frozen=True)
class EntryMirrorRow:
    source_id: str
    source: str
    url: str
    title: str
    published_at: datetime | None
    ingested_at: datetime
    domain: str
    entry_type: str | None
    relevance_score: float | None
    reading_status: str
    summary: str | None
    tags: Sequence[str] | None
    concepts: Sequence[str] | None
    challenge_hooks: Sequence[str] | None


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt is not None else None


def _json_col(values: Sequence[str] | None) -> str | None:
    if values is None:
        return None
    return json.dumps(list(values))


class DuckDbMirror:
    """Upserts entry metadata into DuckDB for M7 query-api metadata filters."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        self._db_path = str(db_path or DUCKDB_PATH)
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = duckdb.connect(self._db_path)
        self._conn.execute(_DDL)

    def upsert(self, entry: EntryMirrorRow) -> None:
        self._conn.execute(
            _UPSERT_SQL,
            [
                entry.source_id,
                entry.source,
                entry.url,
                entry.title,
                _iso(entry.published_at),
                _iso(entry.ingested_at),
                entry.domain,
                entry.entry_type,
                entry.relevance_score,
                entry.reading_status,
                entry.summary,
                _json_col(entry.tags),
                _json_col(entry.concepts),
                _json_col(entry.challenge_hooks),
            ],
        )

    def close(self) -> None:
        self._conn.close()
