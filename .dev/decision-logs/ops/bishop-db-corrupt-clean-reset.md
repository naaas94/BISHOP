# bishop.db corrupt host volume — clean reset (Path B)

**Date:** 2026-06-13  
**Scope:** ops / host data volumes (`~/bishop_data`)  
**Trigger:** Live compose showed HTTP 500 on every state-worker SQLite touch (`GET /manifest/poll`, `POST /entries/content`, etc.). On-disk `bishop.db` contained ArXiv HTML page content embedded in database pages (`Back to arXiv` at byte offset ~266k) while the SQLite header was intermittently valid; queries failed with `database disk image is malformed`. No application code path writes scraped HTML to `bishop.db` — only `state-worker` writes SQLite, and content-scraper posts `content_raw` via REST.

## Problem

1. **Pipeline hard stop:** After mid-session corruption, all workers depending on state-worker polls/writes received 500. Batch-poller and enrichment paths that had already completed in-flight work appeared healthy briefly; new claims and writes failed uniformly.

2. **Unrecoverable in place:** Partial HTML overwrite is not repairable with `sqlite3 .recover` or Alembic re-run in a trustworthy way for pipeline state. No pre-outage backup was available.

3. **Index store drift risk:** Resetting SQLite alone would leave LanceDB, DuckDB, and BM25 artifacts from prior `INDEXED` rows while manifest/entry state is empty — query-api could serve stale hits.

## Decision

**Path B — clean reset (approved 2026-06-13)**

1. `docker compose down` (stack was already stopped).
2. Quarantine host data under `~/bishop_data/_quarantine_2026-06-13_corrupt-reset/`:
   - `sqlite/` — corrupt `bishop.db` (+ any `-wal`/`-shm` if present)
   - `lancedb/`, `duckdb/`, `bm25/` — prior index artifacts for consistency with empty state kernel
3. Recreate empty `sqlite/`, `lancedb/`, `duckdb/`, `bm25/` directories.
4. `docker compose up -d` — state-worker lifespan runs Alembic `upgrade head` on empty `bishop.db`, enables WAL, starts sweep task.
5. Let scraper re-ingest from empty `scraper_state` (ArXiv backfill window).

**Not done:** SQLite backup restore (no valid backup). Application code changes (symptom is host volume integrity, not logic). Anthropic orphan batch cancellation (external batches from pre-reset submit-before-register failures have no local rows after reset).

## Rationale

**Why quarantine instead of delete?** Preserves corrupt `bishop.db` for optional forensics (accidental `curl -o`, sync tool, editor save) without risking further writes.

**Why wipe vector stores too?** Spec single-writer discipline: SQLite owns pipeline truth. Orphaned LanceDB/DuckDB/BM25 rows would violate read-path consistency after manifest/entries tables are empty.

**Why not patch state-worker?** `file is not a database` / `malformed` errors are correct failure modes; masking them would hide data loss.

## Alternatives considered

| Option | Rejected because |
|--------|------------------|
| Path A — restore from backup | No trustworthy pre-outage copy |
| `sqlite3 .recover` / manual page surgery | High effort, low confidence; pipeline state not worth salvage |
| SQLite-only reset, keep vector stores | query-api would serve INDEXED rows with no matching SQLite entries |
| Application guard writing HTML detection | Does not prevent external overwrite; wrong layer |

## Verification

After `docker compose up -d`:

- `GET /health` → 200
- `GET /manifest/poll?state=DISCOVERED` → 200 (empty poll acceptable immediately post-reset)
- Fresh `bishop.db` on host with valid `SQLite format 3` header and queryable `manifest` table

## Post-reset expectations

- Scraper runs full ArXiv backfill window (empty `scraper_state`).
- Pre-filter / poller / enrichment proceed on fresh `DISCOVERED` rows; prior in-flight Anthropic batch IDs are ignored locally.
- Secondary 409 issues (registration race, stale batch `01GXbz…`) from pre-reset session are moot — new state kernel.

## Deferred

- Root-cause forensics on quarantined `bishop.db` (shell history, OneDrive on `bishop_data`, accidental download paths).
- Pre-filter claim release on `invalid_source_state` 409 (unchanged from M3 decision log).
- Automated host-volume integrity check before state-worker pool init (ops hardening, not required for recovery).
