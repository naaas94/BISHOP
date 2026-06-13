"""DuckDB metadata mirror reader for query-api (M7 T3)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import duckdb

from bishop_shared.indexing_config import DUCKDB_PATH

TABLE_NAME = "entries_mirror"


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


class DuckDbReader:
    """Read-only DuckDB access to the M6 metadata mirror."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        self._db_path = str(db_path or DUCKDB_PATH)
        self._conn: duckdb.DuckDBPyConnection | None = None

    def connect(self) -> duckdb.DuckDBPyConnection:
        if self._conn is None:
            self._conn = duckdb.connect(self._db_path, read_only=True)
        return self._conn

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def _table_exists(self) -> bool:
        if not Path(self._db_path).is_file():
            return False
        conn = self.connect()
        row = conn.execute(
            """
            SELECT COUNT(*)
            FROM information_schema.tables
            WHERE table_schema = 'main' AND table_name = ?
            """,
            [TABLE_NAME],
        ).fetchone()
        return row is not None and int(row[0]) > 0

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
        if not self._table_exists():
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
        conn = self.connect()
        rows = conn.execute(sql, params).fetchall()
        return [str(row[0]) for row in rows]

    def recent(
        self,
        *,
        source: str | None = None,
        days: int = 7,
        domain: str | None = None,
    ) -> list[RecentEntry]:
        if not self._table_exists():
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
        conn = self.connect()
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
