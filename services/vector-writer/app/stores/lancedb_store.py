"""LanceDB vector store with source_id idempotency (M6 T2)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import lancedb
import pyarrow as pa

from bishop_shared.indexing_config import EMBEDDING_DIM, LANCEDB_TABLE_NAME


@dataclass(frozen=True)
class LanceRow:
    source_id: str
    vector: list[float]
    title: str
    summary: str
    domain: str
    tags: list[str]
    challenge_hooks: list[str]
    relevance_score: float | None


def _entries_schema() -> pa.Schema:
    return pa.schema(
        [
            pa.field("source_id", pa.string()),
            pa.field("vector", pa.list_(pa.float32(), EMBEDDING_DIM)),
            pa.field("title", pa.string()),
            pa.field("summary", pa.string()),
            pa.field("domain", pa.string()),
            pa.field("tags", pa.list_(pa.string())),
            pa.field("challenge_hooks", pa.list_(pa.string())),
            pa.field("relevance_score", pa.float32()),
        ]
    )


def _escape_sql_string(value: str) -> str:
    return value.replace("'", "''")


def _row_to_record(row: LanceRow) -> dict[str, object]:
    return {
        "source_id": row.source_id,
        "vector": [float(v) for v in row.vector],
        "title": row.title,
        "summary": row.summary,
        "domain": row.domain,
        "tags": list(row.tags),
        "challenge_hooks": list(row.challenge_hooks),
        "relevance_score": row.relevance_score,
    }


class LanceDbStore:
    """LanceDB entries table with check-before-write on source_id."""

    def __init__(self, lancedb_dir: str | Path) -> None:
        self._db = lancedb.connect(str(lancedb_dir))

    def _table_names(self) -> list[str]:
        return list(self._db.list_tables().tables)

    def exists(self, source_id: str) -> bool:
        if LANCEDB_TABLE_NAME not in self._table_names():
            return False
        table = self._db.open_table(LANCEDB_TABLE_NAME)
        escaped = _escape_sql_string(source_id)
        rows = table.search().where(f"source_id = '{escaped}'").limit(1).to_list()
        return len(rows) > 0

    def write(self, row: LanceRow) -> bool:
        if len(row.vector) != EMBEDDING_DIM:
            raise ValueError(
                f"vector dimension {len(row.vector)} does not match EMBEDDING_DIM {EMBEDDING_DIM}"
            )
        if self.exists(row.source_id):
            return False

        record = _row_to_record(row)
        if LANCEDB_TABLE_NAME in self._table_names():
            table = self._db.open_table(LANCEDB_TABLE_NAME)
            table.add([record])
        else:
            self._db.create_table(
                LANCEDB_TABLE_NAME,
                data=[record],
                schema=_entries_schema(),
                mode="create",
            )
        return True
