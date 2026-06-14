# SQLite hardening — `bishop.db` corruption incident

Operational note from live `docker compose up` on Windows — **2026-06-13**.

---

## Symptom

Mid-session pipeline stall after batch-poller / orphan-batch fixes were deployed:

| Caller | Endpoint | Result |
|--------|----------|--------|
| pre-filter-worker | `GET /manifest/poll?state=DISCOVERED` | **500** |
| content-scraper | `POST /entries/content` | **500** (intermittent) |
| enrichment-batcher | `GET /entries/poll?state=SCRAPED` | **500** |
| vector-writer | `GET /entries/poll?state=VECTOR_WRITE_QUEUED` | **500** |

state-worker stayed **healthy** on `/health` (no DB touch). All failures were on routes that read or write SQLite.

Earlier in the same session, batch-poller and enrichment paths were still returning **200** — the DB was valid at startup and failed later.

---

## What we found on disk

Host path: `${BISHOP_DATA_ROOT}/sqlite/bishop.db` (default `~/bishop_data/sqlite/bishop.db`).

### At failure time

| Check | Expected | Observed |
|-------|----------|----------|
| File header (first 16 bytes) | `SQLite format 3\x00` | `\x00\x00\x01DBack to arXiv Why HTML?...` |
| `sqlite3` / `aiosqlite` open | OK | `DatabaseError: file is not a database` |
| File content | Binary SQLite pages | Readable **ArXiv HTML / scraped paper text** from byte 0 |
| WAL / SHM | optional | **Absent** initially (only `bishop.db` present) |

The file was not merely “corrupt SQLite pages” — the **entire file had been replaced** with web-page content matching what content-scraper fetches from `https://arxiv.org/html/{id}`.

### After partial recovery attempt

| Check | Observed |
|-------|----------|
| Header | `SQLite format 3\x00` (valid magic) |
| Open | `database disk image is malformed` |
| Sidecar files | `bishop.db-wal`, `bishop.db-shm` present |

A valid header with `malformed` body indicates **partial / incomplete recovery**, not a clean database. Treat as data loss for pipeline state unless a known-good backup exists.

---

## What did **not** cause it (ruled out in-repo)

Code review of all writers to `/app/data/sqlite`:

| Component | Mounts sqlite? | Opens `bishop.db`? | Writes HTML to disk? |
|-----------|----------------|--------------------|----------------------|
| state-worker | yes | yes (aiosqlite pool, RW) | no — SQL only |
| query-api | yes | yes (`mode=ro` per request) | no |
| batch-poller | yes | **no** | no |
| content-scraper | no | no | no — POSTs JSON to state-worker |
| pre-filter / enrichment / scraper / vector-writer | no | no | no |

`bishop_shared/atomic_persist` writes BM25 pickles under `/app/data/bm25`, not sqlite.

**Conclusion:** No application code path intentionally writes scraped ArXiv HTML to `bishop.db`. The HTML-at-byte-0 signature points to **external file replacement** or a **host/filesystem event**, amplified by an unsafe multi-consumer sqlite volume layout.

---

## Likely causes (ranked)

### 1. Accidental host-side overwrite (best fit for HTML at byte 0)

Something wrote raw HTTP/HTML bytes directly to:

```
~/bishop_data/sqlite/bishop.db
```

Examples:

- `curl https://arxiv.org/html/... > ~/bishop_data/sqlite/bishop.db`
- Wrong path in a script, editor “Save as”, or debug redirect
- Tooling/agent diagnostic that saved fetch output to the DB filename

The content (“Back to arXiv”, paper body text) matches ArXiv HTML — the same material content-scraper processes in memory — but the scraper **never** persists it to the sqlite volume.

### 2. Multi-container SQLite on a Windows bind mount (best fit for ongoing fragility)

`docker-compose.yml` mounts the same host directory into three services:

| Service | Mount | Access pattern |
|---------|-------|----------------|
| state-worker | `${BISHOP_DATA_ROOT}/sqlite:/app/data/sqlite` | RW pool (5 connections), WAL |
| query-api | same | New RO URI connection per `/entries/{id}` and batch detail |
| batch-poller | same | **RW mount, unused in code** |

SQLite WAL on **Docker Desktop for Windows bind mounts** is a known footgun under concurrent readers + a writer. Typical failure mode: `database disk image is malformed`, torn pages, or WAL desync — not usually a clean HTML file from offset 0, unless the host file was replaced or truncated externally while containers held open handles.

### 3. Heavy write load as an accelerant

During the incident window, content-scraper was posting large `content_raw` blobs (success and failure interleaved) while query-api opened concurrent read-only handles. This is plausible stress on an already fragile mount but does not explain HTML replacing the file header by itself.

### 4. Unsafe live diagnostics

Running `docker compose exec state-worker python ... init_pool('/app/data/sqlite/bishop.db')` while the running service already holds the pool opens a **second writer** on the same file. This can worsen corruption; it does not inject ArXiv HTML.

---

## Blast radius

When `bishop.db` is invalid:

- All state-worker routes touching manifest, entries, batches, sweeps → **500**
- Workers log `state-worker poll failed` / `content POST error` and idle
- batch-poller may still talk to Anthropic but cannot deliver results
- query-api entry/batch SQLite fallback paths fail; LanceDB/BM25 may still work for already-indexed data
- `/health` stays green — **misleading** if only health is monitored

---

## Recovery (ops)

1. **Stop the stack** — `docker compose down` — to release file handles.
2. **Inspect the file:**
   ```powershell
   python -c "p=rf'$env:USERPROFILE\bishop_data\sqlite\bishop.db'; print(open(p,'rb').read(16))"
   ```
   Expect `b'SQLite format 3\x00'`. Anything else is not a valid DB.
3. **If backup exists:** restore `bishop.db` and matching `-wal` / `-shm` from the same point in time.
4. **If no backup:** rename corrupted files, restart state-worker (Alembic creates empty schema). **All manifest/batch/entry state is lost** — re-run scraper → pre-filter from scratch.
5. **Do not** try to “repair” a malformed image in place during compose up; replace or recreate.

---

## Prevention

### Compose / volume (do first)

| Action | Why |
|--------|-----|
| **Remove sqlite mount from batch-poller** | Service does not use DB; RW mount is unnecessary risk |
| **Prefer Docker named volume for sqlite on Windows** | Better semantics than `C:\Users\...\bishop_data` bind mount |
| **Backup before `docker compose up`** | Copy `bishop.db` (+ `-wal`/`-shm` if present) or snapshot volume |
| **Never redirect shell output to `bishop.db`** | Treat `${BISHOP_DATA_ROOT}/sqlite/bishop.db` as sacred |

### Architecture (medium term)

| Action | Why |
|--------|-----|
| **Single-writer doctrine** | Only state-worker opens `bishop.db` for write |
| **query-api reads entries via state-worker HTTP** | Removes concurrent RO sqlite opens on the bind mount (M7 used direct sqlite as a shortcut) |
| **Keep content-scraper / workers HTTP-only** | No sqlite mounts on workers that do not need them |

### Code hardening (follow-up PR)

| Change | Where |
|--------|-------|
| `PRAGMA integrity_check` on startup | state-worker lifespan — fail fast with clear log |
| `PRAGMA busy_timeout=5000` (or env) | state-worker pool init |
| query-api: pooled RO connection or remove direct sqlite | `services/query-api/app/sqlite_reader.py` |
| `scripts/verify-*.sh` optional integrity probe | Before long live pipeline runs |
| Extend `/health` or add `/health/db` | Surface DB integrity, not just process up |

### Operational discipline

- Do not run ad-hoc `init_pool()` / second sqlite connections via `docker compose exec` against the live DB path.
- Monitor for `database disk image is malformed` and `file is not a database` in state-worker logs (today often silent 500 only).
- After corruption: assume **poisoned volume** until file header and `PRAGMA integrity_check` pass.

---

## Current compose exposure (reference)

As of 2026-06-13, sqlite is mounted on:

```
state-worker   → RW (required)
batch-poller   → RW (not required — remove)
query-api      → RO intent, per-request opens (reduce or remove)
```

Canonical path constant: `bishop_shared/constants.py` → `SQLITE_DB_PATH = "/app/data/sqlite/bishop.db"`.

---

## Related work (same outage window)

These were fixed separately and are **not** the DB corruption cause, but appeared in the same live session:

- batch-poller Anthropic SDK namespace (`client.messages.batches.*`) — see `.dev/decision-logs/m3-batch-pipeline/batch-poller-messages-batches-namespace.md`
- Poller orphan-batch / sweep coupling — see `.dev/decision-logs/m3-batch-pipeline/batch-poller-orphan-batch-resilience.md`

---

## Deferred

- Automated scheduled backup of sqlite volume on compose up/down hooks
- Move query-api batch entry summaries off sqlite entirely (state-worker proxy only)
- CI/live gate: refuse compose up if `bishop.db` fails integrity check
