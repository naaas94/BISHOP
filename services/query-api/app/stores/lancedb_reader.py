"""LanceDB dense retrieval reader for query-api (M7 T3)."""

from __future__ import annotations

from pathlib import Path

import lancedb

from bishop_shared.indexing_config import EMBEDDING_DIM, LANCEDB_DIR, LANCEDB_TABLE_NAME


def _escape_sql_string(value: str) -> str:
    return value.replace("'", "''")


class LanceDbSearcher:
    """Cosine top-k search over the M6 `entries` LanceDB table."""

    def __init__(self, lancedb_dir: str | Path | None = None) -> None:
        self._lancedb_dir = str(lancedb_dir or LANCEDB_DIR)
        self._db = lancedb.connect(self._lancedb_dir)

    def _table_names(self) -> list[str]:
        return list(self._db.list_tables().tables)

    def search(
        self,
        vector: list[float],
        k: int,
        domain: str | None = None,
    ) -> list[tuple[str, float]]:
        if len(vector) != EMBEDDING_DIM:
            raise ValueError(
                f"vector dimension {len(vector)} does not match EMBEDDING_DIM {EMBEDDING_DIM}"
            )
        if LANCEDB_TABLE_NAME not in self._table_names():
            return []

        table = self._db.open_table(LANCEDB_TABLE_NAME)
        query = table.search(vector).metric("cosine").limit(k)
        if domain is not None:
            escaped = _escape_sql_string(domain)
            query = query.where(f"domain = '{escaped}'")

        hits: list[tuple[str, float]] = []
        for row in query.to_list():
            source_id = str(row["source_id"])
            distance = float(row.get("_distance", 0.0))
            score = 1.0 - distance
            hits.append((source_id, score))
        hits.sort(key=lambda item: item[1], reverse=True)
        return hits
