# T1 — Query shared contracts

**Plan:** m7-read-path · **Date:** 2026-06-13

## Chosen approach

- **Shared constants:** `bishop_shared/query_config.py` pins `RRF_K=60`, `DEFAULT_SEARCH_DOMAIN="professional"`, and env-backed `BM25_RELOAD_INTERVAL_SEC` (default 300).
- **Tokenize contract:** `bishop_shared/bm25_tokenize.py` exports `tokenize_bm25` (`text.lower().split()`); vector-writer `bm25_store` imports it (one-line swap) so index and query paths share one surface.
- **Query-api scaffold:** FastAPI `app/main.py` with `GET /health`, `lifespan.py` G7 cold-start probes that WARN with `event=store_cold_start_empty` on missing BM25 dir / LanceDB table / DuckDB file and never raise; Dockerfile CMD `python -m app.main`.

## Alternatives rejected

- **Query-api importing vector-writer bm25_store:** Rejected per plan Flag 1 — read modules live under query-api; only shared constants/tokenize cross the service boundary.
- **LanceDB table probe via `lancedb` import at T1:** Rejected — requirements skeleton is fastapi/uvicorn only; table presence checked via `{LANCEDB_TABLE_NAME}.lance` directory heuristic until T3 reader lands.

## Assumptions made

- LanceDB on-disk layout exposes `{table}.lance` under `LANCEDB_DIR` matching vector-writer `create_table` naming; T3 reader will validate with real `lancedb.connect`.
- DuckDB cold-start stub treats missing **file** as empty metadata filter; empty file with no `entries_mirror` table deferred to T3 `DuckDbReader`.
- `DEFAULT_SEARCH_DOMAIN` cold-start probe uses professional domain only at startup; per-request domain switching for BM25 load is T2.

## Items deferred

- **DuckDB table-exists probe:** File-presence only at T1; `entries_mirror` DDL check moves to T3.
- **BM25 pickle load/search:** `Bm25QueryIndex` implementation and reload COW deferred to T2.
- **test_service_stubs graduation for query-api:** Stub removal test deferred to T8 per plan coupling.
