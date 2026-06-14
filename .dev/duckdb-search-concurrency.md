# DuckDB search concurrency — `bishop.duckdb` lock model

Operational / design note from live `docker compose up` — **2026-06-13**.

Related: M6 vector-writer mirror, M7 query-api read path. Distinct from [SQLite hardening](./db_hardening.md) (`bishop.db`).

---

## Symptom

After vector-writer indexes entries, host search fails:

```bash
bishop search "agent evaluation"
# Internal Server Error
```

query-api logs:

```
_duckdb.IOException: Could not set lock on file "/app/data/duckdb/bishop.duckdb":
Conflicting lock is held in PID 0
```

Stack: `GET /search` → `run_search()` (BM25 + LanceDB + embedding) **succeeds** → `_fetch_hit_metadata()` → `DuckDbReader.connect(read_only=True)` **throws** → HTTP **500**.

`/health` on query-api stays **200** — misleading if only health is monitored.

---

## DuckDB rule (why this happens)

On a **single database file**, DuckDB allows:

| Pattern | Allowed? |
|---------|----------|
| Multiple read-write connections | Yes |
| Multiple read-only connections | Yes |
| **Read-write + read-only at the same time** | **No** |

query-api uses `read_only=True`. vector-writer uses a normal read-write connection. If both are open on `bishop.duckdb` simultaneously → lock error.

This is **not** SQLite; it is a separate file under `${BISHOP_DATA_ROOT}/duckdb/bishop.duckdb`.

---

## Misconception: “locked only while writing”

**No.** With current code the file is effectively locked for the **whole time vector-writer is running**, including idle sleep between index cycles.

### vector-writer (today)

`DuckDbMirror` opens once at startup and keeps the connection until container shutdown:

- `services/vector-writer/app/stores/duckdb_mirror.py` — `duckdb.connect()` in `__init__`
- `services/vector-writer/app/main.py` — single `DuckDbMirror()` for process lifetime; `close()` only in `finally` on exit

The RW lock is **not** scoped to the `upsert()` call.

### query-api (today)

`DuckDbReader` lazily opens `read_only=True` and **caches** `_conn` on first use:

- `services/query-api/app/stores/duckdb_reader.py` — `connect()`
- Used by `/search` (`_fetch_hit_metadata`), metadata pre-filter in `run_search`, and `/recent`

Once search opens RO successfully, query-api can also **block** vector-writer from opening RW (same rule, reversed).

### Timeline (current)

```
vector-writer start ──► duckdb.connect(RW) ──► held for hours ──► container stop ──► close
query-api search    ──► duckdb.connect(RO) ──► fails if RW still open (500)
```

### Why it “wasn’t happening before”

Search worked (or returned empty) when:

- `bishop.duckdb` did not exist yet, or
- vector-writer was not running, or
- No indexed hits reached `_fetch_hit_metadata`

First live session with **both** services up and populated indexes surfaces the conflict.

---

## Intended model (deferred at M6/M7 build)

**Goal:** search available **almost always**; DuckDB locked only while a connection is actually open — typically milliseconds around each upsert/read.

```
vector-writer:  [closed] ── open RW ── upsert ── close ── [encode / BM25 / LanceDB / sleep]
query-api:      [closed] ── open RO ── read  ── close ── [per request]
```

Overlap window = rare race when writer holds RW during upsert and search tries RO at the same instant.

Authoritative test intent:

- `tests/test_duckdb_concurrent_read.py` — `test_read_only_connection_after_mirror_releases_write` documents M7 steady-state: RO succeeds **after** mirror closes.
- Comment on `test_separate_connection_reads_while_mirror_holds_write`: M7 query-api uses read_only when vector-writer has **released** the file between upserts.

CHANGELOG deferred item (M6 T6 / M7 T3):

> DuckDB read_only while vector-writer holds write connection deferred — DuckDB allows multiple RW or multiple RO connections, not mixed.

---

## Proposed implementation (when ready)

### 1. vector-writer — short-lived write connection

Open DuckDB only around `upsert()`, close immediately after.

| Granularity | Lock window | Notes |
|-------------|-------------|-------|
| Per upsert (recommended) | ~ms per entry | Search can run during encode + BM25 persist (majority of index time) |
| Per index cycle | Up to N entries × upsert | Worse for search; simpler but longer exclusion |

`index_entry()` already calls `stores.duckdb.upsert()` once per entry (`services/vector-writer/app/index_entry.py`). Refactor `DuckDbMirror` to connect/disconnect per upsert (or context-manager), not per process.

Remove process-lifetime `DuckDbMirror()` connection from `_build_stores()` semantics — mirror object can remain, connection should not.

### 2. query-api — short-lived read connection

Do **not** cache `_conn` across requests.

Options (pick one):

- Open + close inside each `filter_source_ids` / `_fetch_hit_metadata` / `recent()` call, or
- Context manager on `DuckDbReader` used per `/search` request

Lifespan `stores.metadata.close()` on shutdown remains valid.

### 3. query-api — retry on lock conflict (recommended)

On `duckdb.IOException` with “Conflicting lock”, retry with small backoff (e.g. 2–3 attempts, tens of ms). Upsert window is short; retry usually succeeds.

Optional degradation: return search hits with `source_id` + RRF score only, omitting title/summary if metadata read fails after retries (better than 500).

---

## Safety assessment

| Question | Answer |
|----------|--------|
| Safe to implement? | **Yes** — matches original M6/M7 design and existing tests |
| Single writer on DuckDB? | **Yes** — only vector-writer mutates `bishop.duckdb` |
| Stale metadata risk? | **Low** — readers see last committed upsert after writer closes |
| Affects LanceDB/BM25? | **No** — separate paths under `/app/data/lancedb` and `/app/data/bm25` |
| Zero risk? | **No** — rare races; need retry or brief 500 |

### Residual risks

| Risk | Mitigation |
|------|------------|
| RO open during RW upsert | Retry on query-api; keep upsert fast |
| query-api caches RO (blocks writer) | Per-request close; do not cache |
| Windows bind-mount flakiness | Prefer Docker named volume for `duckdb/` (see `db_hardening.md`) |
| Cross-store non-atomic index | Pre-existing; not worsened by this change |

### Does not fix

- SQLite `bishop.db` corruption / 500 on state-worker polls
- Enrichment stage2 `ENRICHMENT_STAGE2_CLAIMED` orphan claims
- Empty search when nothing is indexed yet

---

## Code references

| File | Role |
|------|------|
| `services/vector-writer/app/stores/duckdb_mirror.py` | RW mirror; holds connection today |
| `services/vector-writer/app/main.py` | Process-lifetime stores |
| `services/vector-writer/app/index_entry.py` | `duckdb.upsert()` per indexed entry |
| `services/query-api/app/stores/duckdb_reader.py` | RO reader; caches connection |
| `services/query-api/app/routers/search.py` | `_fetch_hit_metadata` after `run_search` |
| `services/query-api/app/retrieval/search.py` | Optional DuckDB pre-filter when query params set |
| `bishop_shared/indexing_config.py` | `DUCKDB_PATH` constant |
| `tests/test_duckdb_concurrent_read.py` | Concurrency contract tests |
| `tests/test_query_api_duckdb_reader.py` | `read_only=True` falsifier |

---

## Compose note

Both services mount `${BISHOP_DATA_ROOT}/duckdb` (vector-writer RW, query-api RO intent). Only **connection lifetime**, not mount removal, is required for this fix — but named volumes on Windows remain a good ops hardening step.

---

## Implementation checklist (future PR)

- [x] `DuckDbMirror`: connect before `upsert`, close after (idempotent `close()`)
- [x] `DuckDbReader`: per-operation connection or per-request scope; remove long-lived `_conn`
- [x] query-api `/search`: retry DuckDB lock errors; optional metadata-degraded response
- [x] Update / extend `test_duckdb_concurrent_read.py` for per-upsert release pattern
- [ ] Integration smoke: `bishop search` while vector-writer indexing same stack
- [x] CHANGELOG + `.dev/decision-logs/m7-read-path/` entry when implemented

---

## Related artifacts

- [db_hardening.md](./db_hardening.md) — SQLite volume / corruption (separate store)
- `.dev/decision-logs/m7-read-path/T3-lancedb-duckdb-embedding.md` — original DuckDB reader design
- CHANGELOG M6 T6 / M7 T3 — deferred concurrent-read note
