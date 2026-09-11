# SQLite salvage, integrity gate, and snapshot rotation — 2026-09-11

**Status:** landed · **Incident date:** 2026-09-11 (UTC-3) · **Work packet:** `.dev/handoffs/2026-09-11-opus-db-salvage-hardening.md`
**Predecessor incident:** 2026-06-13 (`.dev/db_hardening.md`, `.dev/decision-logs/ops/bishop-db-corrupt-clean-reset.md`)
**Closes:** most of OPEN-007. Partially addresses OPEN-018.

---

## 1. What happened

`bishop.db` became unreadable mid-session for the second time. Symptom class matched
2026-06-13 — every SQLite-touching route returned HTTP 500 while `/health` stayed
green — but the on-disk signature was different.

| | 2026-06-13 | 2026-09-11 |
|---|---|---|
| Header at failure | ArXiv HTML from byte 0 | valid `SQLite format 3` after shutdown |
| Cause class | file replacement (host overwrite) | torn btree + overflow pages |
| `Back to arXiv` in file | proof of overwrite | expected — it is `entries.content_raw` on overflow pages |
| Recovery | Path B wipe, all ingest re-paid | salvage, nothing re-paid |

`PRAGMA integrity_check` on the quarantined original returns **101 issue lines**:
`btreeInitPage() returns error code 11`, `overflow list length is 12 but should be 14`,
`2nd reference to page 2976`, and a long tail of `never used` pages. The `batches`
root page was among the dead ones, so `COUNT(*) FROM batches` threw.

**`Back to arXiv` inside the file is not evidence of overwrite this time.** That string
is scraped ArXiv HTML legitimately stored in `entries.content_raw`. Do not re-derive
the June conclusion from it.

## 2. Root cause — found, and it is not the bind mount

The packet attributed the damage to "WAL + large overflow blobs + extra processes on a
Windows bind mount." Bringing the stack up on the salvaged file reproduced the *symptom*
within seconds and showed the actual mechanism, which is a code defect:

1. `run_retry_sweep` never called `_prepare_conn`, so `row_factory` was unset on the
   pooled connection it borrowed. `_fetch_entry` → `_row_to_entry` → `Entry.from_db_row(dict(row))`
   raised `ValueError: dictionary update sequence element #0 has length 36; 2 is required`
   (element #0 being a 36-char UUID read positionally).
2. The sweep had already issued `UPDATE manifest ...`, so an implicit **write transaction
   was open**. The exception skipped `conn.commit()` and there was no rollback.
3. `sweeps.py` caught it with a bare `except Exception`, and `async with get_db()`
   returned the connection **to the pool with its write transaction still open**.
4. WAL permits exactly one writer. That connection held the write lock indefinitely, so
   every other connection failed `database is locked`, and the next borrower of that
   connection failed `cannot start a transaction within a transaction`.
5. The sweep runs on a timer, poisoning one more connection per iteration until all five
   pooled connections were dead. Every route 500'd. `/health` did no DB I/O, so it stayed
   green the entire time — in both incidents.

A separate, independent defect amplified this: the claim paths used deferred `BEGIN`.
A deferred transaction takes no write lock, so the first `UPDATE` must *upgrade*, and
SQLite cannot safely back off an upgrade — it returns `SQLITE_BUSY` immediately
**without honouring `busy_timeout`**. Setting `busy_timeout` alone did not stop the
`database is locked` 500s; `BEGIN IMMEDIATE` did.

Finally, `alembic/env.py` called `fileConfig(config.config_file_name)`, whose default is
`disable_existing_loggers=True`. `run_migrations()` runs in-process at startup, so every
logger created at import time — `app.main`, `app.db`, all `app.routers.*` — was disabled
for the life of the process. **That is why the corruption was invisible:** the service
could not emit an ERROR after boot. Verified directly: `app.main.disabled` flips
`False → True` across a `run_migrations()` call.

The bind mount is still a plausible contributor to the *physical* page tearing, and the
named-volume migration remains a follow-up. But the write-lock deadlock, the 500 storm,
and the silence were all in our code.

## 3. Locked decisions honoured

1. **Salvage first, no Path B wipe.** Done; see §4. Nothing was re-paid.
2. **Live filename stays `bishop.db`.** Snapshots are copies under `sqlite/snapshots/`.
3. **No auto-swap while compose is up.** `sqlite_restore.py` refuses (exit 2) when
   `docker compose ps -q` is non-empty.
4. **Snapshot only integrity-passing files.** Both source and destination are checked;
   a failing snapshot is deleted, never published.
5. **Restore = down → copy newest passing → drop `-wal`/`-shm` → up.** Scripted.
6. **Re-fetch Anthropic, never re-submit.** Achieved without a replay script — see §5.
7. **Indexes are not source of truth.** Verified consistent instead of rebuilt — see §4.
8. **Hardening lands with the rotator.** See §6.
11. **Snapshot never opens a second RW connection.** Source is `mode=ro`; the copy uses
    the SQLite online backup API. `VACUUM INTO` was rejected because a read-only
    connection cannot run it.

## 4. Salvage result

Tool: `scripts/sqlite_salvage.py` (kept — it is parameterised and re-runnable).
It merges two independent sources into a freshly migrated database and trusts neither
alone: the `sqlite3 .recover` dump, and a rowid walk of the torn file that steps over
pages which raise.

The earlier `.recover` dump was unusable as-is because PowerShell `>` wrote it UTF-16 LE
with a BOM. Re-run with the redirect **inside** the container: 15.4 MB UTF-8 (the 30 MB
UTF-16 file held the same content).

`.recover` reconstructed `manifest`/`entries`/`scraper_state`/`error_log`/`oov_tags_log`
in place. `batches` could not be reconstructed as a table — its root page was torn — but
81 rows landed in `lost_and_found`, and 69 of them carry exactly the 15-column `batches`
shape at head, so they were re-attributed positionally by arity plus a `batch_type`
discriminator and a UUID-shaped `c0`.

| Table | Salvaged | Notes |
|---|---|---|
| `manifest` | 1764 | 0 invalid rows |
| `entries` | 160 | 168 recovered, 8 torn rows dropped |
| `batches` | 69 | 69 distinct `external_batch_id` — exactly the 69 `msgbatch_` ids in the packet's Appendix A |
| `scraper_state` | 6 | all sources, so no window re-scrape |
| `oov_tags_log` | 43 | |
| `error_log` | 2 | |

**The rowid walk added zero rows**, which proves `.recover` was a strict superset and
1764 is the real ceiling. The walk saw rowids up to 1900 (matching the packet's lucky
`COUNT`), so roughly 136 manifest rows sit on pages that are simply gone.

**Paid work retained:** 1622 pre-filter decisions, 153 stage-1 summaries, 135 stage-2
scores, and all 160 bodies. This is the spend that Path B would have re-bought.

**Torn rows.** `.recover` reassembles some rows from partial pages, leaving content text
in enum columns (`processing_state = 'a Forget set (e.g., copy'`) or empty strings where a
value is required. Eight `entries` rows were affected. Such a row fails Pydantic at the
first read and would 500 the route, so they are deleted rather than served, with the full
row recorded in a quarantine JSON. Seven had a surviving `relevance_decision = 1` manifest
row and were reset to `RELEVANCE_PASSED`, so content-scraper re-fetches the body over
plain HTTP — free; only those few enrichment calls are re-paid. One
(`arxiv:2609.10315`) had no manifest row and needs re-discovery.

**Index reconciliation.** All 97 `INDEXED` rows were present in LanceDB, DuckDB *and*
BM25 main, with zero orphans in any store and zero `VECTOR_WRITE_QUEUED` rows already in
Lance. Per decision 7 the index files were therefore kept rather than quarantined, and
**no `INDEXED` row was demoted** — the demote-to-`VECTOR_WRITE_QUEUED` option the packet
authorised was not needed.

Verdict: the salvaged file passes `integrity_check`, sits at Alembic head
`m8_001_pre_filter_tier`, and has no orphaned entries and no foreign-key violations.

## 5. Anthropic replay — no script needed

Because salvage restored the `batches` rows *with* their `submitted`/`processing` status
and full `source_ids`, batch-poller's existing `startup_scan`
(`GET /batches?status=submitted,processing`) picked up the four in-flight batches by
itself and drove the normal apply path. Confirmed live: `POST /manifest/pre-filter-results
200`, `PATCH /batches/{id} 200`. Nothing was re-submitted and no second decision schema
was invented. The hashed-`custom_id` problem never arose because the poller looks results
up by re-encoding `batch.source_ids`, which salvage recovered intact.

## 6. Hardening landed

| Change | Where |
|---|---|
| Dropped the dead sqlite mount from `batch-poller` (verified: no `sqlite3`/`aiosqlite` anywhere in that service) | `docker-compose.yml` |
| `enforce_integrity()` as the **first** lifespan action, before Alembic — running migrations against a torn file can worsen it | `app/main.py`, `app/db.py` |
| `GET /health/db` does real I/O (`SELECT version_num FROM alembic_version`) and returns **503** on failure; compose healthcheck now targets it, so a corrupt DB blocks all 8 dependents instead of letting them crash-loop against 500s. `/health` stays a pure liveness probe. | `app/main.py`, `docker-compose.yml` |
| `PRAGMA busy_timeout` on every pooled connection and the migration engine | `app/db.py` |
| `row_factory` set **once** at pool creation instead of per call site | `app/db.py` |
| `get_db()` rolls back any transaction left open before returning a connection to the pool; if rollback fails the connection is discarded and replaced | `app/db.py` |
| `BEGIN` → `BEGIN IMMEDIATE` at all five write-transaction sites | `app/transitions.py` |
| `_prepare_conn` + rollback-on-failure in both sweeps | `app/transitions.py` |
| `fileConfig(..., disable_existing_loggers=False)` | `alembic/env.py` |

Startup integrity behaviour is **refuse loudly, never auto-repair**: it logs
`event=sqlite_integrity_failed`, the first 20 issue lines, the snapshot directory, the
newest passing snapshot names, and the literal remediation command, then raises
`SqliteIntegrityError` so the process exits non-zero. There is deliberately no
auto-restore.

Gate verified against the real artifacts, not just fixtures: it **refuses** the
quarantined original, **allows** the salvaged file, and treats a missing path as a fresh
install *without creating it*.

## 7. Snapshots and restore

`scripts/sqlite_snapshot.py` — source is gated first (a corrupt live file must never
become "the newest passing snapshot"), copied via the online backup API from a read-only
connection into a hidden temp file in the target directory, fsynced, integrity-checked,
then `os.replace`d into `snapshots/bishop-YYYYmmdd-HHMMSS.db`. Failing attempts are
deleted. Prune drops anything older than 24h, matching only the snapshot glob inside the
snapshot directory. `shutil.copy` of a live WAL database is never used — a test writes
rows and deliberately does not checkpoint to prove WAL-resident data is captured.

`scripts/sqlite_restore.py` — refuses if compose is up (exit 2, `--force` to override),
refuses a snapshot that fails integrity (exit 3), preserves the current live file as
`bishop.db.pre-restore-<ts>` so the restore is itself reversible, installs atomically,
deletes stale `-wal`/`-shm`, and re-verifies the installed file (exit 4 on failure).
`--dry-run` supported.

Registered on this host as scheduled task `BishopSqliteSnapshot`, every 30 minutes, via
`scripts/register-snapshot-task.ps1`. TTL 24h ⇒ ~48 snapshots ⇒ ~0.8 GB/day.

Verified a snapshot **while the stack was up and writing**: 16.5 MB, `integrity_check` ok,
and `sqlite_restore.py --latest` correctly refused with exit 2.

## 8. Live verification

Rebuilt and ran the full stack. Before the transaction fixes, a short run produced
`ValueError`, 2 × `database is locked`, 4 × 500, and `scraper` exited 1 on a
`ReadTimeout`. After them, a 4-minute run under live load:

```
database is locked                   0
cannot start a transaction           0
ValueError                           0
500 Internal Server Error            0
sqlite_pool_rollback_on_release      0
Traceback                            0
```

All 9 services up, state-worker healthy via `/health/db`. Pipeline progressed:
manifest 1764 → 2114, entries 160 → 183, batches 69 → 80, **INDEXED 97 → 145**, with
stage-1 and stage-2 results applied and PapersWithCode skipping as a warning.
`integrity_check` on the live file after the run: `ok`.

Tests: `python scripts/run_tests.py` → **127 files, 127 clean, 0 failing**. (Plain
single-process `pytest -q` fails ~82 tests for a pre-existing reason unrelated to this
work: every service has its own `app` package and they collide in one interpreter. That
is why the repo has an isolated-subprocess runner.)

## 9. Deliberately not done

- **Path B wipe** — unnecessary; salvage succeeded.
- **Re-submitting any batch with an existing `msgbatch_` id** — never happened.
- **Cutting the pool from 5** — needs an operator decision; with `BEGIN IMMEDIATE` plus
  `busy_timeout` the contention is gone, so it may no longer be warranted.
- **Moving sqlite to a Docker named volume** — the right long-term fix for bind-mount
  tearing, but it changes the host workflow and every `.dev/sqlite.md` recipe.
- **query-api HTTP-only** — larger M7 seam cut; it keeps its read-only mount.
- **Auto-restore on startup** — explicitly rejected.
- **Moving `content_raw` out of SQLite** — would shrink the overflow pages that tore, but
  it is a spec change and needs a proposal.
- **Re-pre-filtering the ~136 lost manifest rows** — they will be re-discovered free by
  the scraper; re-deciding them costs money and was not authorised.

## 10. Evidence

Quarantine (do not delete until the operator is satisfied):
`C:/Users/Ale/bishop_data/_quarantine_2026-09-11_corrupt-salvage/sqlite/` — original
`bishop.db` (SHA256 verified identical to the live file at capture time), `-wal`, `-shm`,
and the UTF-16 recover dump.

Working artifacts: `C:/Users/Ale/bishop_data/_salvage_2026-09-11/` —
`recovered.utf8.sql`, `integrity_check.txt` (101 lines), `salvage-report.json`,
`quarantined-rows.json`, `index-overlap-report.json`, captured service logs.

## 11. Security note

`.env` contains a live `GITHUB_TOKEN` that was pasted into a chat transcript earlier in
this session. **Rotate it.** No secret was written into any repo file, test, changelog or
log by this work; the snapshot and restore scripts read only the `BISHOP_DATA_ROOT` key
from `.env`.
