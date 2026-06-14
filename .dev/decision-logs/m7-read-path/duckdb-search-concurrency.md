# DuckDB search concurrency — short-lived connections

**Context:** `.dev/duckdb-search-concurrency.md` · **Date:** 2026-06-13

## Chosen approach

- **vector-writer `DuckDbMirror`:** Open read-write connection only inside `upsert()`, close in `finally`. Writer retries lock conflicts (8 × 50 ms) — indexing wins over transient query-api reads.
- **query-api `DuckDbReader`:** Per-operation `read_only=True` connect/close; no cached `_conn`. Brief read retries (3 × 25 ms), then degrade:
  - `fetch_hit_metadata` / `fetch_top_entry_metadata` → empty (search/batch fall back to `source_id` or SQLite)
  - `run_search` metadata pre-filter → skip filter, log `duckdb_prefilter_lock_skip`
  - `/recent` → empty list, log `duckdb_recent_lock_skip`
- **Routers:** `_fetch_hit_metadata` moved into `DuckDbReader.fetch_hit_metadata`; batches use `fetch_top_entry_metadata`.

Closes M6 T6 / M7 T3 deferred item: DuckDB mixed RW+RO disallowed; steady-state assumes file released between upserts.

## Alternatives rejected

- **Process-lifetime RW mirror (status quo):** Blocks all search metadata reads while vector-writer runs.
- **Symmetric retry only (no degradation):** Search could still 500 on lock exhaustion; write path could fail if query-api cached RO.
- **Removing DuckDB mount from query-api:** Connection lifetime is the fix; mounts unchanged per ops note.

## Assumptions made

- Upsert duration stays short (single `INSERT OR REPLACE`); writer retry window sufficient for query-api RO release.
- Pre-filter skip on lock (wider recall) is acceptable vs empty results or HTTP 500 — write priority over strict filter semantics during indexing bursts.
- `bishop_spec_0_6.md` §8.3 “read_only while writer holds write lock” prose is incorrect for DuckDB; not amended in this change.

## Items deferred

- **Spec §8.3 correction:** Mixed-mode DuckDB rule documented here and in ops note; normative spec edit deferred.
- **Live compose smoke:** `bishop search` while vector-writer indexing — manual per M3–M7 pattern.
- **Named Docker volume for `duckdb/` on Windows:** Ops hardening per `db_hardening.md`, not required for lock fix.

## Files touched

- `services/vector-writer/app/stores/duckdb_mirror.py`
- `services/query-api/app/stores/duckdb_reader.py`
- `services/query-api/app/routers/search.py`, `batches.py`, `recent.py`
- `services/query-api/app/retrieval/search.py`
- `tests/test_duckdb_mirror.py`, `tests/test_duckdb_concurrent_read.py`, `tests/test_query_api_duckdb_reader.py`, `tests/test_query_api_routes_search.py`, `tests/test_query_api_routes_batches.py`
