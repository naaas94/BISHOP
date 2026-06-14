"""DuckDB metadata mirror reader for query-api (M7 T3)."""

from __future__ import annotations

import json
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Iterator

import duckdb

from bishop_shared.indexing_config import DUCKDB_PATH

TABLE_NAME = "entries_mirror"

_READ_LOCK_RETRIES = 3
_READ_LOCK_BACKOFF_SEC = 0.025


class DuckDbLockUnavailableError(Exception):
    """Read-only DuckDB access failed after retries (writer likely holds the file)."""


@dataclass(frozen=True)
class RecentEntry:
    source_id: str
    source: str
    title: str
    ingested_at: str
    domain: str
    entry_type: str | None
    relevance_score: float | None
    summary: str | None


@dataclass(frozen=True)
class EntryMetadataRow:
    source_id: str
    title: str
    summary: str | None
    relevance_score: float | None
    entry_type: str | None
    tags: list[str] | None


def _is_lock_conflict(exc: BaseException) -> bool:
    return isinstance(exc, duckdb.IOException) and "Conflicting lock" in str(exc)


class DuckDbReader:
    """Read-only DuckDB access to the M6 metadata mirror."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        self._db_path = str(db_path or DUCKDB_PATH)

    def close(self) -> None:
        """No-op — connections are scoped per operation."""

    def _connect_read_only(self) -> duckdb.DuckDBPyConnection:
        last_exc: duckdb.IOException | None = None
        for attempt in range(_READ_LOCK_RETRIES):
            try:
                return duckdb.connect(self._db_path, read_only=True)
            except duckdb.IOException as exc:
                if _is_lock_conflict(exc) and attempt < _READ_LOCK_RETRIES - 1:
                    last_exc = exc
                    time.sleep(_READ_LOCK_BACKOFF_SEC)
                    continue
                if _is_lock_conflict(exc):
                    raise DuckDbLockUnavailableError(str(exc)) from exc
                raise
        if last_exc is not None:
            raise DuckDbLockUnavailableError(str(last_exc)) from last_exc
        raise DuckDbLockUnavailableError("DuckDB read retry exhausted")

    @contextmanager
    def _read_conn(self) -> Iterator[duckdb.DuckDBPyConnection]:
        conn = self._connect_read_only()
        try:
            yield conn
        finally:
            conn.close()

    def _table_exists(self, conn: duckdb.DuckDBPyConnection) -> bool:
        if not Path(self._db_path).is_file():
            return False
        row = conn.execute(
            """
            SELECT COUNT(*)
            FROM information_schema.tables
            WHERE table_schema = 'main' AND table_name = ?
            """,
            [TABLE_NAME],
        ).fetchone()
        return row is not None and int(row[0]) > 0

    def _fetchall(self, sql: str, params: list[Any]) -> list[tuple[Any, ...]]:
        with self._read_conn() as conn:
            return conn.execute(sql, params).fetchall()

    def filter_source_ids(
        self,
        *,
        domain: str | None = None,
        source: str | None = None,
        tags: list[str] | None = None,
        min_relevance: float | None = None,
        days: int | None = None,
        entry_type: str | None = None,
        reading_status: str | None = None,
    ) -> list[str]:
        if not Path(self._db_path).is_file():
            return []

        with self._read_conn() as conn:
            if not self._table_exists(conn):
                return []

            clauses: list[str] = []
            params: list[Any] = []

            if domain is not None:
                clauses.append("domain = ?")
                params.append(domain)
            if source is not None:
                clauses.append("source = ?")
                params.append(source)
            if entry_type is not None:
                clauses.append("entry_type = ?")
                params.append(entry_type)
            if reading_status is not None:
                clauses.append("reading_status = ?")
                params.append(reading_status)
            if min_relevance is not None:
                clauses.append("relevance_score >= ?")
                params.append(min_relevance)
            if days is not None:
                cutoff = (datetime.now(tz=UTC) - timedelta(days=days)).isoformat()
                clauses.append("ingested_at >= ?")
                params.append(cutoff)
            if tags:
                tag_clauses = []
                for tag in tags:
                    tag_clauses.append(
                        "list_contains(CAST(json_extract(tags, '$') AS VARCHAR[]), ?)"
                    )
                    params.append(tag)
                clauses.append("(tags IS NOT NULL AND (" + " OR ".join(tag_clauses) + "))")

            where_sql = f" WHERE {' AND '.join(clauses)}" if clauses else ""
            sql = f"SELECT source_id FROM {TABLE_NAME}{where_sql} ORDER BY ingested_at DESC"
            rows = conn.execute(sql, params).fetchall()
            return [str(row[0]) for row in rows]

    def recent(
        self,
        *,
        source: str | None = None,
        days: int = 7,
        domain: str | None = None,
    ) -> list[RecentEntry]:
        if not Path(self._db_path).is_file():
            return []

        with self._read_conn() as conn:
            if not self._table_exists(conn):
                return []

            clauses = ["ingested_at >= ?"]
            params: list[Any] = [
                (datetime.now(tz=UTC) - timedelta(days=days)).isoformat(),
            ]
            if source is not None:
                clauses.append("source = ?")
                params.append(source)
            if domain is not None:
                clauses.append("domain = ?")
                params.append(domain)

            where_sql = " AND ".join(clauses)
            sql = f"""
                SELECT source_id, source, title, ingested_at, domain,
                       entry_type, relevance_score, summary
                FROM {TABLE_NAME}
                WHERE {where_sql}
                ORDER BY ingested_at DESC
            """
            rows = conn.execute(sql, params).fetchall()
            return [
                RecentEntry(
                    source_id=str(row[0]),
                    source=str(row[1]),
                    title=str(row[2]),
                    ingested_at=str(row[3]),
                    domain=str(row[4]),
                    entry_type=str(row[5]) if row[5] is not None else None,
                    relevance_score=float(row[6]) if row[6] is not None else None,
                    summary=str(row[7]) if row[7] is not None else None,
                )
                for row in rows
            ]

    def fetch_hit_metadata(self, source_ids: list[str]) -> dict[str, dict[str, Any]]:
        """Return per-source metadata for search hits; empty on lock conflict."""
        if not source_ids or not Path(self._db_path).is_file():
            return {}
        try:
            rows = self._fetch_entry_metadata_rows(source_ids)
        except DuckDbLockUnavailableError:
            return {}
        return {
            row.source_id: {
                "title": row.title,
                "summary": row.summary,
                "relevance_score": row.relevance_score,
                "entry_type": row.entry_type,
                "tags": row.tags,
            }
            for row in rows
        }

    def fetch_top_entry_metadata(
        self,
        source_ids: list[str],
        *,
        limit: int,
    ) -> list[EntryMetadataRow]:
        """Top entries by relevance for batch detail enrichment."""
        if not source_ids or not Path(self._db_path).is_file():
            return []
        placeholders = ",".join("?" for _ in source_ids)
        sql = f"""
            SELECT source_id, title, summary, relevance_score, entry_type, tags
            FROM {TABLE_NAME}
            WHERE source_id IN ({placeholders})
            ORDER BY relevance_score DESC NULLS LAST
            LIMIT ?
        """
        try:
            raw_rows = self._fetchall(sql, [*source_ids, limit])
        except DuckDbLockUnavailableError:
            return []
        return [self._row_to_metadata(row) for row in raw_rows]

    def _fetch_entry_metadata_rows(self, source_ids: list[str]) -> list[EntryMetadataRow]:
        placeholders = ",".join("?" for _ in source_ids)
        sql = f"""
            SELECT source_id, title, summary, relevance_score, entry_type, tags
            FROM {TABLE_NAME}
            WHERE source_id IN ({placeholders})
        """
        raw_rows = self._fetchall(sql, source_ids)
        return [self._row_to_metadata(row) for row in raw_rows]

    def _row_to_metadata(self, row: tuple[Any, ...]) -> EntryMetadataRow:
        tags_raw = row[5]
        tags: list[str] | None = None
        if tags_raw is not None:
            if isinstance(tags_raw, str):
                tags = json.loads(tags_raw)
            else:
                tags = list(tags_raw)
        return EntryMetadataRow(
            source_id=str(row[0]),
            title=str(row[1]),
            summary=str(row[2]) if row[2] is not None else None,
            relevance_score=float(row[3]) if row[3] is not None else None,
            entry_type=str(row[4]) if row[4] is not None else None,
            tags=tags,
        )
