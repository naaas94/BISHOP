# Architectural decisions — execution-time divergence log

Runtime counterpart to program rationale: absorbed intent drift from milestone execution.

---

## M6 — 2026-06-13

**Spec intent:** Charter M6 requires a single per-domain file lock covering both BM25 indices in the **same write operation**.

**Execution decision:** `Bm25DualIndex` uses one lock file at the domain root but acquires it in separate `with` blocks for `add_main`, `add_challenge_hooks`, and `persist`.

**Rationale:** T3 decision log documents single lock file (not single critical section); acceptable for single-writer MVP; handoff §8.4 waiver F-006.

**Status:** absorbed

---

## M7 — 2026-06-13

**Spec intent:** Plan §0 Flag 2 binds entry reads on query-api to a read-only `aiosqlite` connection at `SQLITE_DB_PATH`.

**Execution decision:** `sqlite_reader.py` uses stdlib `sqlite3.connect` with `file:…?mode=ro` URI; no `aiosqlite` dependency in query-api.

**Rationale:** Sync SQLite reads match FastAPI sync route handlers; `test_read_entry_opens_sqlite_read_only` falsifies writable connections. Read-only behavioral contract honored.

**Status:** absorbed

---

## M7 — 2026-06-13 (DuckDB connection lifetime)

**Spec intent:** §8.3 — `query-api` opens DuckDB `read_only=True` so metadata reads can run concurrently while `vector-writer` holds the read-write lock on `bishop.duckdb`.

**Execution decision:** Both services use short-lived connections only (RW per `upsert`, RO per read). Writer retries lock conflicts; query-api degrades reads (partial search metadata, skipped pre-filter, empty `/recent`) rather than HTTP 500.

**Rationale:** DuckDB disallows mixed read-write + read-only on one file (M6 `test_duckdb_concurrent_read.py`); process-lifetime mirror connection caused live search 500s. Deferred at M6 T6 / M7 T3; implemented post-M7 per `.dev/decision-logs/m7-read-path/duckdb-search-concurrency.md`. Spec §8.3 prose not amended — normative correction deferred.

**Status:** absorbed

---

## Ops — 2026-09-11 (soft-launch precision overlay)

**Spec intent:** Calibrated pre-filter pin `professional_v1.2.0.yaml`; `decision=1` → `RELEVANCE_PASSED` regardless of tier; backfill windows from `BACKFILL_CONFIG`.

**Execution decision:** Ad hoc overlay parks `decision=1` + `tier=peripheral` as `RELEVANCE_PARKED`; prefilter pin `professional_v1.2.0_soft_launch.yaml`; compose default `BISHOP_BACKFILL_WINDOW_OVERRIDE_DAYS=60` (retuned 1 → 7 → 60 on 2026-09-15 after option 1; still overlay, not `BACKFILL_CONFIG`).

**Rationale:** First-week spend and inbox quality. Not a charter slice. Revert or formally promote after the first-week window. See `.dev/decision-logs/ops/soft-launch-precision-overlay.md`.

**Status:** absorbed (overlay still live as of 2026-09-13)

---

## Ops — 2026-09-11 (sqlite_live bind overlay)

**Spec intent:** Live DB at `${BISHOP_DATA_ROOT}/sqlite/bishop.db`.

**Execution decision:** This-host `docker-compose.override.yml` remounts state-worker and query-api sqlite volume onto `sqlite_live` after leaked Docker Desktop WAL handles. Snapshots stay under `sqlite/snapshots/`.

**Rationale:** Ops salvage. Remove the override when handles are gone. SQLITE_DB_PATH inside the container is unchanged.

**Status:** absorbed (this-host; overlay still present)

---

## Prompt-caching — 2026-09-12 (custom_id encoding)

**Spec intent (historical architecture v1.2.0):** Anthropic `custom_id` equals manifest `source_id`.

**Execution decision:** `source_id_to_batch_custom_id` (URL-safe base64, or hashed `h`+sha256 when over 48 UTF-8 bytes). Poller re-encodes `batches.source_ids` to join.

**Rationale:** Anthropic `custom_id` charset/length constraints. Planned in prompt-caching T1-bis.

**Status:** absorbed
