"""DuckDB metadata mirror store (spec §8.3; plan Flag 2 DDL binding)."""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TypeVar

import duckdb

from bishop_shared.indexing_config import DUCKDB_PATH

TABLE_NAME = "entries_mirror"

_WRITE_LOCK_RETRIES = 8
_WRITE_LOCK_BACKOFF_SEC = 0.05

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

_T = TypeVar("_T")


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


def _is_lock_conflict(exc: BaseException) -> bool:
    return isinstance(exc, duckdb.IOException) and "Conflicting lock" in str(exc)


class DuckDbMirror:
    """Upserts entry metadata into DuckDB for M7 query-api metadata filters."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        self._db_path = str(db_path or DUCKDB_PATH)
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)

    def upsert(self, entry: EntryMirrorRow) -> None:
        def _write(conn: duckdb.DuckDBPyConnection) -> None:
            conn.execute(_DDL)
            conn.execute(
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

        self._with_write_retry(_write)

    def _with_write_retry(
        self,
        operation: Callable[[duckdb.DuckDBPyConnection], _T],
    ) -> _T:
        last_exc: duckdb.IOException | None = None
        for attempt in range(_WRITE_LOCK_RETRIES):
            conn: duckdb.DuckDBPyConnection | None = None
            try:
                conn = duckdb.connect(self._db_path)
                return operation(conn)
            except duckdb.IOException as exc:
                if conn is not None:
                    conn.close()
                    conn = None
                if _is_lock_conflict(exc) and attempt < _WRITE_LOCK_RETRIES - 1:
                    last_exc = exc
                    time.sleep(_WRITE_LOCK_BACKOFF_SEC)
                    continue
                raise
            finally:
                if conn is not None:
                    conn.close()
        if last_exc is not None:
            raise last_exc
        raise RuntimeError("DuckDB write retry exhausted without exception")

    def close(self) -> None:
        """No-op — connections are scoped per upsert."""
