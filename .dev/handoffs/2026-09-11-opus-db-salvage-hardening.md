# Opus brief — salvage `bishop.db` + SQLite hardening + snapshot rotator

**Date:** 2026-09-11  
**Author:** prior agent (Grok) after a live compose session with the operator  
**Audience:** a higher-authority agent (Opus) that will **execute**, not re-litigate, unless a locked decision is actually unsafe  
**Repo:** `C:/Users/Ale/Documents/Repos/BISHOP`  
**Host data:** `C:/Users/Ale/bishop_data` (`BISHOP_DATA_ROOT` in `.env`)  
**Stack state when this was written:** `docker compose down` already ran. Do **not** `compose up` against the live corrupt file.

This is a work packet. Read it end-to-end before touching the live `bishop.db`. The operator explicitly asked you to: salvage and repair the current DB, re-fetch Anthropic batch results, keep as much data as possible, apply the hardening we locked, and land the snapshot rotator + restore path.

---

## 1. What Bishop is (only what you need)

Local-first ingest: scrape → pre-filter (Anthropic Message Batches) → content scrape → enrichment Call 1/2 (Anthropic) → vector write → query/UI.

**SQLite is pipeline truth.** Only `state-worker` may open `bishop.db` for write. Everyone else POSTs HTTP or (today, unfortunately) query-api opens `mode=ro`. There is no `processed` column; progress is `processing_state`.

Standing refs (do not rediscover from the README — it is M0 compose only):

| Doc | Why |
|-----|-----|
| `AGENTS.md` | Agent entry |
| `.cursor/rules/bishop-sqlite.mdc` | Writer rule, paths, relevance gates |
| `.dev/sqlite.md` | Live DB recipes |
| `.dev/db_hardening.md` | 2026-06-13 incident + recommended hardening (mostly **not implemented**) |
| `.dev/decision-logs/ops/bishop-db-corrupt-clean-reset.md` | Last time we **wiped**. Do not default to this. |
| `.dev/still_open.md` OPEN-007 | Hardening backlog this session is meant to close part of |
| `bishop_shared/constants.py` | `SQLITE_DB_PATH = /app/data/sqlite/bishop.db` |
| `services/state-worker/app/db.py` | Alembic then aiosqlite pool, `PRAGMA journal_mode=WAL` |
| `services/state-worker/app/main.py` | `/health` does **not** touch SQLite (this is why the writer looked healthy while everything 500'd) |
| `bishop_spec_0_6.md` §7 | Schema / states |

Host live file: `C:/Users/Ale/bishop_data/sqlite/bishop.db` (~16.8MB after shutdown).

---

## 2. Chronology of this session (2026-09-11, UTC-3)

### Morning — pipeline up, adapter/worker crashes

Operator ran `docker compose up` after M8 source expansion + a soft-launch overlay (1-day backfill, parked inbox). Logs showed four real failures plus rate limits.

**Diagnosed and already patched in the working tree (uncommitted unless the operator committed later — check `git status`):**

1. **Papers With Code** — `GET https://paperswithcode.com/api/v1/papers/` returns **302 → huggingface.co/papers**. The v1 API is discontinued (Meta/HF shut PwC; no drop-in replacement). `failure_envelope` treated 302 as `PermanentFailureError` (not in retriable 429/5xx or escalatable 401/403/404/422).  
   **Fix landed:** `services/scraper/app/adapters/paperswithcode.py` `_paperswithcode_api_unavailable()` → log WARNING, return `[]`. Test: `tests/test_scraper_adapters_paperswithcode.py::test_fetch_manifest_skips_when_api_redirects`.  
   **Do not** `follow_redirects=True` — that would ingest HF trending HTML as papers.

2. **HuggingFace `source_id` killed pre-filter** — `ValueError: source_id exceeds 48 UTF-8 bytes: 'huggingface:model:beiyurobotics/recognize_black_label_book_3'`. Anthropic `custom_id` is `^[a-zA-Z0-9_-]{1,64}$`. Old encoder base64url'd the whole id (fits only ≤48 bytes). HF `{source}:{kind}:{org/repo}` routinely exceeds that; worker exited (no restart policy).  
   **Fix landed:** `bishop_shared/batch_custom_id.py` — short IDs still reversible base64url; long IDs → `h` + sha256 digest (deterministic). Poller looks up by **re-encoding** `batch.source_ids` (`services/batch-poller/app/loop.py`); production never needs reverse decode (see `.dev/decision-logs/m3-batch-pipeline/batch-custom-id-encoding.md`). Tests: `tests/test_batch_custom_id.py`.  
   **Must rebuild** any image that copies `bishop_shared`: pre-filter-worker, enrichment-batcher, **batch-poller** (lookup), scraper, ui.

3. **Enrichment-batcher tiktoken crash** — scraped body contained literal `<|endoftext|>`; default `disallowed_special` raised; process died.  
   **Fix landed:** `bishop_shared/content_truncation.py` `_encode(..., disallowed_special=())`. Test: `tests/test_enrichment_truncation.py::test_literal_endoftext_does_not_raise`.

4. **UI never started** — `POST /entries/{source_id}/reading-status` uses `Form(...)` (`services/ui/app/main.py` ~L344). Image lacked `python-multipart`.  
   **Fix landed:** `services/ui/requirements.txt` + `pyproject.toml` dev extra.

**Not bugs, still true:**

- Semantic Scholar **429 → retry exhausted**. Operator requested an API key; **not in `.env` yet**. Leave adapter as-is.
- GitHub page-10 **403** was unauthenticated search. Operator added `GITHUB_TOKEN` to `.env` (classic PAT). Compose already has `GITHUB_TOKEN: ${GITHUB_TOKEN:-}`. After recreate, pages 1–10 returned 200. **Do not print, commit, or echo that token.** It was pasted into chat — operator was told to rotate if the transcript is shared.
- OpenReview empty chunks were 200s (nothing in window), not errors.
- vector-writer warned about unauthenticated HF Hub downloads for `all-MiniLM-L6-v2`. Unrelated to the scraper HF adapter.

**Soft-launch overlay (ad hoc, not long-term):** `.dev/decision-logs/ops/soft-launch-precision-overlay.md`, `CHANGELOG.MD` top section. `BISHOP_BACKFILL_WINDOW_OVERRIDE_DAYS=1`, parked inbox, profile `professional_v1.2.0_soft_launch.yaml`. Do not silently revert.

After rebuild, all 9 containers stayed up. PwC warned and skipped. Pre-filter registered batches. GitHub authenticated. Then the DB died mid-session.

### Mid-morning — second `bishop.db` corruption

Same **symptom class** as 2026-06-13 (every SQLite-touching route 500; `/health` green), **not** the same on-disk signature.

While compose was up (file locked):

- Size ~16,306,176  
- Header read as 16 zero bytes → `DatabaseError: file is not a database`  
- `Back to arXiv` at offset **385848** (and more)

After `docker compose down` (file unlocked, WAL checkpointed into main):

- Size **16,809,984**  
- Header **valid** `SQLite format 3`  
- `PRAGMA integrity_check` **fails** (btreeInitPage error 11, overflow list length mismatches, unused pages). Worst damage on **overflow pages** and the **`batches` table**.  
- Tables still visible in `sqlite_master`: `alembic_version`, `manifest`, `entries`, `batches`, `error_log`, `oov_tags_log`, `scraper_state`

**Direct reads that worked (mode=ro, keyset / rowid walks; aggregates often throw):**

| Surface | Result |
|---------|--------|
| `COUNT(*)` manifest (one lucky query) | 1900 |
| `COUNT(*)` entries (one lucky query) | 178 |
| Rowid walk manifest | **1625 unique** rows |
| Rowid walk entries | **75 unique**, all `INDEXED`, all had `content_raw` + summary + `relevance_score` |
| `scraper_state` | 6 rows, intact: arxiv, huggingface, lesswrong, openreview, github, paperswithcode (timestamps ~2026-09-11T13:12–13:13Z) |
| `batches` | `COUNT` / group-by throw `database disk image is malformed` |

Manifest walk mix (1625):

| State | n |
|-------|---|
| `RELEVANCE_REJECTED` / decision 0 | 1234 |
| `RELEVANCE_QUEUED` / decision NULL | 125 |
| `INDEXED` / 1 | 97 |
| `RELEVANCE_PARKED` / 1 | 85 |
| `VECTOR_WRITE_QUEUED` / 1 | 39 |
| `ENRICHMENT_STAGE2_QUEUED` / 1 | 21 |
| `RELEVANCE_PASSED` / 1 | 13 |
| `ENRICHMENT_STAGE1_SUBMITTED` / 1 | 10 |
| `ENRICHMENT_STAGE1_FAILED` / 1 | 1 |

Sources in that walk: github 715, huggingface 485, arxiv 375, lesswrong 50. (OpenReview/PwC empty or not in the walked slice.)

**69 unique `msgbatch_*` IDs** appear as raw strings in the file (appendix A). Several also appear as structured rows in the recover dump’s `lost_and_found`, **including `source_ids` JSON and `processing`/`submitted`/`complete` status**. That is enough to re-download Anthropic results without re-paying.

`sqlite3 .recover` via `docker run --rm -v C:/Users/Ale/bishop_data/sqlite:/data nouchka/sqlite3 /data/bishop.db ".recover"` produced a 30MB dump. **PowerShell `>` wrote it as UTF-16 LE + BOM** (`FF FE`). Path: `C:/Users/Ale/bishop_data/sqlite/bishop.recovered.sql`. Re-run recover with a UTF-8 redirect (Python subprocess, or `cmd /c`, or write inside the container to `/data/bishop.recovered.utf8.sql`). Tail of that dump showed real `INSERT INTO lost_and_found` rows for in-flight pre_filter / enrichment_stage1 batches with `msgbatch_…` + full `source_ids` arrays.

Also present after down: `bishop.db-shm` (32KB), `bishop.db-wal` (**0 bytes**). Keep them with the quarantined original; do not mix WAL from one copy onto another file.

### Operator questions we answered

- **Do we have to pay Anthropic again?** No, not for work already submitted. Message Batch results are downloadable ~29 days. `messages.batches.results(id)` is not a new bill. Re-pay only holes we cannot map.
- **Do we have to scrape everything again?** Manifest/content HTTP is free. Re-scrape only rows we cannot salvage. The walked INDEXED entries already have full `content_raw`.
- **Is there a backup?** No scheduled backup. `.recover` + readable pages **are** the salvage path. June Path B (wipe sqlite + indexes) is the last resort, not the plan.
- **Can we stop this?** Snapshots survive the next hit. They do not stop it. Hardening the mount/health/integrity story is what reduces recurrence. OPEN-007 was written in June and never implemented.

---

## 3. Attribution — do not confuse the two incidents

### 2026-06-13 (`.dev/db_hardening.md`)

Header at failure time was **ArXiv HTML from byte 0** (`Back to arXiv` replacing `SQLite format 3`). That is **file replacement**, not torn pages. Ruled out: app code writing HTML to `bishop.db`. Suspected: host overwrite (`curl -o`, editor, sync tool) and/or Windows bind-mount WAL footgun.

Recovery then: Path B — quarantine sqlite + lancedb + duckdb + bm25, empty dirs, Alembic on fresh file. All ingest re-paid.

### 2026-09-11 (this file)

After shutdown the header is valid SQLite. `Back to arXiv` **inside** the file is **expected**: `entries.content_raw` stores scraped ArXiv HTML on overflow pages. That string is **not** proof of overwrite this time.

The smoking gun is `integrity_check`: torn btree/overflow pages (`overflow list length is 12 but should be 14`), unused pages, `batches` unreadable. That matches **WAL + large overflow blobs + extra processes opening the same bind-mounted file on Docker Desktop for Windows**.

Compose still mounts `${BISHOP_DATA_ROOT}/sqlite` on:

| Service | Need |
|---------|------|
| `state-worker` | Required RW writer (`docker-compose.yml` L10) |
| `batch-poller` | **Not used.** Dead mount. L99. Remove. |
| `query-api` | Direct `mode=ro` per request (`services/query-api/app/sqlite_reader.py`). L138. Medium-term: HTTP-only. |

`state-worker` pool: 5 aiosqlite connections, WAL, no `busy_timeout`, no startup `integrity_check` (`services/state-worker/app/db.py`). Health: L51–53 of `main.py` returns `{status: ok}` with zero DB I/O.

We **cannot** name the guilty `source_id` (batching). We **can** name the failure class. Do not spend the Opus budget re-deriving “maybe Anthropic corrupted the DB.” Anthropic never opens the file.

---

## 4. Locked decisions (operator + prior agent, 2026-09-11)

Treat these as constraints. Escalate to the operator only if you discover they would lose data or spend money the salvage can avoid.

1. **Salvage first. Do not Path B wipe** unless salvage cannot produce a file that passes `integrity_check` and can accept writes. Even then, ask the operator — wipe re-pays pre-filter + enrichment for everything.

2. **Live filename stays `bishop.db`.** Snapshots are copies beside it (`sqlite/snapshots/bishop-YYYYmmdd-HHMMSS.db`). Do **not** point state-worker at a rotating suffix during normal run (split-brain + WAL mismatch).

3. **No auto-swap of the live file while compose is up.** A bad automatic rollback during a write is worse than a 30-second scripted restore.

4. **Snapshot only files that pass `integrity_check` at snapshot time.** Delete failing snapshot attempts. TTL 24h (12h acceptable). Interval 30 minutes. Space is ~16MB × 48 ≈ 0.8GB/day.

5. **Restore =** `compose down` → copy newest **passing** snapshot over `bishop.db` → delete `-wal`/`-shm` → `compose up`. Optional next step: replay in-flight `msgbatch_` ids from the snapshot / ledger.

6. **Anthropic: re-fetch, don’t re-submit** for IDs we already have. Rebuild local `batches` rows + `source_ids` from recover/`lost_and_found`, then use existing batch-poller apply path (or a one-shot script that POSTs the same state-worker result routes).

7. **Indexes (Lance / Duck / BM25) are not source of truth.** After salvage, prefer SQLite. If index stores have rows SQLite lacks (or the reverse), rebuild the **delta** from SQLite; do not keep orphan index hits. June Path B wiped indexes for this reason. If salvage restores INDEXED rows, you may keep existing index files **only if** you verify source_id overlap; otherwise quarantine indexes with the old sqlite and let vector-writer refill from `VECTOR_WRITE_QUEUED` / re-queue.

8. **Hardening in this change (must land, not just the rotator):**
   - Remove sqlite volume from `batch-poller`.
   - `PRAGMA integrity_check` on state-worker startup; **refuse to start the pool** (loud ERROR) if not `ok`.
   - `PRAGMA busy_timeout=5000` (or env) on every pool connection.
   - `/health` must fail (or add `/health/db` and make compose healthcheck use it) when the DB is missing/corrupt/`file is not a database`. Today’s green health is a lie.

9. **Do not** follow PwC 302s. Do not revert the custom_id hash / tiktoken / multipart fixes. Rebuild images that copy `bishop_shared`.

10. **Secrets:** `.env` has `ANTHROPIC_API_KEY` (may be in the user environment rather than the file) and `GITHUB_TOKEN`. Never commit `.env`. Never write tokens into the handoff, changelog, or tests.

11. **Writer rule unchanged:** only state-worker writes SQLite. Snapshot job must use `VACUUM INTO` / `sqlite3.backup` / `.backup` against a **read connection**, or run only when the stack is down. Do not `copy` a live WAL database and call it consistent. Preferred: HTTP or a small endpoint on state-worker that runs `VACUUM INTO` so the writer coordinates the snapshot. Acceptable v1: host scheduled task that uses `VACUUM INTO` via `sqlite3.connect` **read-only URI is not enough for VACUUM INTO** — use the backup API (`conn.backup(dest)`) from a Python script on the host, or `docker compose exec state-worker` a one-shot that the writer exposes. **Do not** open a second RW `init_pool` against the live path (`.dev/db_hardening.md` explicitly forbids this).

12. **Uncommitted morning fixes** are in the working tree. Include them. Do not revert. Check `git status` before committing; only commit if the operator asks.

---

## 5. Ordered execution (do this, in this order)

### Gate 0 — freeze the crime scene

1. Confirm compose is down: `docker compose ps` empty.
2. Quarantine **copies** (do not delete the live files until the new DB is verified):

```
C:/Users/Ale/bishop_data/_quarantine_2026-09-11_corrupt-salvage/
  sqlite/bishop.db
  sqlite/bishop.db-wal
  sqlite/bishop.db-shm
  sqlite/bishop.recovered.sql   # UTF-16, keep as evidence
```

3. Work only on copies / a new `bishop.db` path until `integrity_check` is `ok`.

### Phase A — salvage (highest value, do before hardening if they conflict)

Goal: a **new** `bishop.db` that:

- passes `PRAGMA integrity_check`
- has Alembic head `m8_001_pre_filter_tier` (see `alembic/versions/`)
- contains as many manifest + entries + scraper_state + reconstructed batches as possible
- does not contain HTML-as-schema or duplicate PKs

Suggested procedure:

1. Re-run `.recover` to a **UTF-8** SQL file (do not reuse the UTF-16 dump as-is unless you decode it).
2. Import recover SQL into a throwaway DB. SQLite `.recover` often emits `lost_and_found` plus reconstructed tables. Deduplicate by `source_id` (manifest/entries PK/unique).
3. Also walk the original with `WHERE rowid > ? ORDER BY rowid LIMIT N` and INSERT OR IGNORE into the new DB — the walk already proved 1625 manifest + 75 entries are directly readable; recover may get the rest of the 1900 / 178.
4. Rebuild `batches` from `lost_and_found` rows that look like batch records (uuid, `pre_filter` / `enrichment_stage1` / `enrichment_stage2`, profile_version, status, counts, `msgbatch_…`, `source_ids` JSON). Schema: `services/state-worker/app/models/domain.py` + `alembic/versions/m1_001_initial_schema.py` + `m3_001_batch_source_ids.py` + `m8_001_pre_filter_tier.py`.
5. Restore `scraper_state` from the readable 6 rows so incremental scrape does not re-window and re-pay.
6. Extract every `msgbatch_[A-Za-z0-9]+` (appendix A + recover dump). List Anthropic batches (`client.messages.batches.list` if available) and intersect. For each id: `retrieve` + if ended, `results`.
7. Apply results **without re-submit**:
   - Pre-filter: same mapping as `services/batch-poller/app/loop.py` `_handle_pre_filter_complete` — `source_id_to_batch_custom_id` then parse JSON decision. Long HF ids need the `source_ids` list (hash is not reversible).
   - Enrichment stage1/2: same files, `_handle_enrichment_stage1_complete` / `_handle_enrichment_stage2_complete`.
   - Prefer POSTing through state-worker HTTP once a clean DB + state-worker is up on the salvaged file, so transitions stay honest.
   - In-flight (`processing`/`submitted`) batches: if Anthropic says `ended`, apply; if still running, register them locally and let batch-poller finish.
8. States: do not mark INDEXED unless Lance/Duck/BM25 actually have the row **or** you re-queue `VECTOR_WRITE_QUEUED`. Safer: after salvage, set INDEXED rows that have no index hit back to `VECTOR_WRITE_QUEUED` and let vector-writer refill. Inverse: index-only orphans get deleted or ignored.
9. Verify: `integrity_check` ok; histograms; spot-check a few `arxiv:` INDEXED rows still have `content_raw`; `scraper_state` present; in-flight batch ids either applied or registered.

**Success bar:** we do **not** re-pay the 1234 rejects / 97+ indexed / parked / already-enriched rows we can see. Holes (unwalkable pages, unmapped hashed custom_ids without `source_ids`) may need re-scrape (free) or re-prefilter (paid) — log them; do not silently drop.

### Phase B — hardening (OPEN-007 slice we locked)

| Change | File | Notes |
|--------|------|--------|
| Remove sqlite mount from batch-poller | `docker-compose.yml` | Update `tests/test_compose.py` if it asserts that mount |
| `busy_timeout` + startup `integrity_check` | `services/state-worker/app/db.py` | Fail startup if not ok; log `event=sqlite_integrity_failed` |
| Health reflects DB | `services/state-worker/app/main.py` + compose `healthcheck` | Either `/health` opens SQLite or `/health/db` and compose uses it |
| Tests | new + existing state-worker main/db tests | Corrupt-file fixture: startup/health fails. Happy path still 200. |

Optional in this PR if cheap: `query-api` keep RO mount (HTTP-only is a larger cut — follow-up).

### Phase C — snapshot rotator + restore script

Live path remains `C:/Users/Ale/bishop_data/sqlite/bishop.db`.

```
C:/Users/Ale/bishop_data/sqlite/snapshots/bishop-YYYYmmdd-HHMMSS.db
```

Requirements:

- Every 30 minutes while the stack is intended to be up (Windows scheduled task **or** a tiny compose sidecar **or** a loop in state-worker). Prefer a **repo script** the operator can run / Task Scheduler can call: `scripts/sqlite_snapshot.py` (name as you like).
- Use SQLite backup API / `VACUUM INTO` to a temp file in the same directory, `fsync`, then rename (same atomicity idea as `bishop_shared/atomic_persist.py`).
- Run `integrity_check` on the snapshot; delete it if not `ok`.
- Delete snapshots older than 24h.
- Never snapshot by `shutil.copy` of a live WAL db.
- Restore script: `scripts/sqlite_restore.py --latest` (or `--file …`) that refuses if compose is up, refuses if the chosen snapshot fails integrity, replaces `bishop.db`, removes wal/shm.

Document operator usage in `.dev/sqlite.md` (short). Decision log under `.dev/decision-logs/ops/`. Changelog entry in `CHANGELOG.MD`.

Do **not** auto-restore on startup in v1. Startup integrity failure = die loudly with the newest passing snapshot path printed.

### Phase D — bring the stack back

1. Point host `sqlite/bishop.db` at the salvaged file (original still in quarantine).
2. `docker compose up --build` so morning shared-library fixes are in images.
3. Confirm all 9 services stay up; `/health/db` 200; one pre-filter cycle does not ValueError; PwC is WARNING not ERROR; GitHub token still injected from `.env`.
4. Watch one enrichment cycle; no tiktoken crash; no silent 500 on `ENRICHMENT_STAGE2_QUEUED` (that 500 at boot was likely Alembic-not-ready **or** already-corrupt pages — distinguish).

---

## 6. Files you will likely touch

**Salvage (host data, not necessarily git):**

- `C:/Users/Ale/bishop_data/sqlite/bishop.db` (replace only after quarantine)
- `C:/Users/Ale/bishop_data/_quarantine_2026-09-11_corrupt-salvage/`
- New scripts under `scripts/` for recover import / Anthropic replay (ok to keep in repo if they are reusable)

**Hardening + snapshots (git):**

- `docker-compose.yml`
- `tests/test_compose.py`
- `services/state-worker/app/db.py`
- `services/state-worker/app/main.py`
- `services/state-worker/app/models/` if HealthResponse grows
- `tests/test_state_worker_main.py` (and/or new integrity tests)
- `scripts/sqlite_snapshot.py`, `scripts/sqlite_restore.py`
- `.dev/sqlite.md`
- `.dev/decision-logs/ops/sqlite-snapshot-and-integrity-gate.md` (create)
- `CHANGELOG.MD`
- `.dev/still_open.md` OPEN-007 — mark what you closed vs still deferred

**Already dirty / do not revert:**

- `bishop_shared/batch_custom_id.py`
- `bishop_shared/content_truncation.py`
- `services/scraper/app/adapters/paperswithcode.py`
- `services/ui/requirements.txt`
- `pyproject.toml`
- matching tests listed in §2

**Do not** “refresh” `.dev/architecture/bishop/` unless you are already there; that folder is flagged stale after 2026-07-13 (`AGENTS.md`).

---

## 7. How Anthropic replay actually works in this codebase

- Submit: `services/pre-filter-worker/app/anthropic_batch_client.py`, `services/enrichment-batcher/app/anthropic_batch_client.py` — `custom_id = source_id_to_batch_custom_id(source_id)`.
- Register: state-worker `POST /batches` stores local uuid, `external_batch_id`, `source_ids` JSON (`m3_001`).
- Poll/apply: `services/batch-poller/app/loop.py` + `services/batch-poller/app/clients/anthropic.py` (`client.messages.batches.retrieve` / `.results`).
- Decode helper is **tests/debug only**. Hashed custom_ids (`h` + 43 chars) **cannot** be reversed; you **must** have `source_ids`.

If you write a one-shot replay script, reuse those parsers (`parse_pre_filter_response`, enrichment parsers in `bishop_shared/enrichment_parsers.py`). Do not invent a second decision schema.

---

## 8. Follow-ups — your authority to decide vs ask

**You may decide (in scope, operator already wants them):**

- Exact snapshot trigger (Task Scheduler vs compose sidecar vs state-worker loop). Prefer the smallest thing that runs on this Windows host without a new always-on service if a sidecar is heavy.
- Whether `/health` itself hits SQLite or a dedicated `/health/db` (compose must use the one that can go red).
- Whether INDEXED-without-index rows get demoted to `VECTOR_WRITE_QUEUED`.
- How aggressive recover dedupe is, as long as you log dropped/conflicting rows.

**Ask the operator before:**

- Path B wipe of sqlite + indexes
- Re-submitting Anthropic batches that already have an `msgbatch_` id
- Moving `BISHOP_DATA_ROOT` sqlite to a Docker **named volume** (right long-term fix for bind-mount WAL; changes their host-path workflow and `.dev/sqlite.md` recipes)
- Making query-api HTTP-only (more routes, M7 seam)
- Auto-restore on startup
- Spending a new pre-filter pass over all 1234+ rejects “to be sure”
- Committing `.env` or any token
- `git commit` (operator rule: only when asked)

**Investigate if salvage is clean and you have budget (do not block Phase A–C):**

- Is `C:/Users/Ale/bishop_data` under OneDrive / AV realtime scan? June suspected host-side overwrite; this incident looks like torn overflow pages, but AV+bind-mount is a known combo.
- aiosqlite **pool of 5 writers** on one WAL file on a Windows bind mount — is that itself load-bearing for corruption? Single connection would be a behavior change; measure/discuss, don’t silently cut the pool.
- Should `content_raw` live outside SQLite (blob dir + atomic persist) so overflow pages shrink? Spec/architecture change; proposal only.
- `batch-poller` crash-loop on 500 (`restart: unless-stopped`) + startup_scan — after health-gate, this should stop. Still worth making startup_scan retry instead of process-exit.
- Soft-launch parked overlay vs salvage: 85 `RELEVANCE_PARKED` rows should remain parked, not get promoted.
- Named-volume migration design note for a later milestone.

---

## 9. Tests / verification

Already passing on the morning fixes (run again after your edits):

```
pytest tests/test_batch_custom_id.py tests/test_enrichment_truncation.py tests/test_scraper_adapters_paperswithcode.py tests/test_prefilter_anthropic_client.py tests/test_prefilter_loop.py tests/test_ui_parked.py tests/test_ui_escalations.py tests/test_ui_explorer.py tests/test_enrichment_batcher_stage1_loop.py tests/test_batch_poller_loop.py
```

Add/keep tests for: compose mount removal, integrity-fail startup, health red on missing/corrupt db, snapshot TTL deletion, restore refuses when compose is up (if you can detect it), restore refuses a corrupt snapshot.

Live: do not declare done on a screenshot. After `compose up --build`, hit `/health` + `/health/db` (or whatever you add), `GET /manifest/poll?state=DISCOVERED`, and confirm workers are not 500-looping. Browser-check UI only if you touch UI (you should not need to, beyond the already-landed multipart dep).

---

## 10. HALTs

- Missing/unreadable quarantined original before you replace `bishop.db`.
- Salvage DB fails `integrity_check` — do not start state-worker on it.
- Cannot map hashed `custom_id`s and you are about to re-submit those batches — stop and use `source_ids` from recover first.
- Ambiguity about wiping indexes vs keeping Lance data — default: quarantine indexes with sqlite; refill from salvaged SQLite.
- Second writer: no `docker compose exec state-worker python … init_pool(...)` against the live path.

---

## Appendix A — `msgbatch_` IDs extracted from the corrupt file

These are raw string hits (may include historical/complete batches). Intersect with Anthropic and with recover `lost_and_found`.

```
msgbatch_011bzbaXH3GXdPuEpT6ntyiE
msgbatch_011yoo9X6Snm5ccswp8hvtfY
msgbatch_01295ZXEgsf6GBfhTpitDEK1
msgbatch_012PRbfTv5YSXYUZiC7SXi9c
msgbatch_012bFg9VrwKnoJkkw5fkmho9
msgbatch_013QZY7teUS9fhQoQFU6tCPc
msgbatch_014xHhN2SZNfjWkg1RNaCinQ
msgbatch_015BFUdqY4G9K5iWwKrWBPym
msgbatch_015TXPQRygA1Jc8bLfvdb7dC
msgbatch_0169JfxEtrar11H1iySoatTQ
msgbatch_016WTSC2EJq8hyV26Rn81iUr
msgbatch_016eLtFGiAo8FfzgHMjeCSdw
msgbatch_017T1NccXxx2bZPs3rM5m88S
msgbatch_018C6aniVzC3GnPFjfZ1MvkQ
msgbatch_018CVfE8T6DDnLJo6m2Y52Js
msgbatch_018dq1XYWMQ9pj52U9teRbuu
msgbatch_019ATenoMafuULzUrofEZfT9
msgbatch_019GgJhXUzWPKq7A9CpUZ8gu
msgbatch_019dQo4g9x5SbVPxnAtvcY2w
msgbatch_019imMtyfym5U5tLrzXCqbL1
msgbatch_01A5HYtYKZeLp2b4ByaTt3pG
msgbatch_01BNKwzhde39H2P3qoPb4SuB
msgbatch_01C95axL1fwAj5TUCwVQkyhU
msgbatch_01CNF6fbZjTP7rmTo1E1ZFAi
msgbatch_01CYTvNiaKbZiro1fryi9QcZ
msgbatch_01CfBvF3Ebc3ScSamFq9sAWr
msgbatch_01CfpYoTAynM6ptPz7S1bCuF
msgbatch_01DSvV8ewRtfi24nBj7mNWXB
msgbatch_01DZffivXdtkaiMtmuwLUeG4
msgbatch_01Dz4W8mxVkGUZWdR1pmNK26
msgbatch_01E4P8pkzXKbarxHJACST4DA
msgbatch_01E7zTHPsnPCKjQs4ycrywcJ
msgbatch_01E84zbuZPmp2eYMss7wu74L
msgbatch_01F4MPn2PiXuFDVPMx2npkCb
msgbatch_01F66yF6zjJY7nP1DYiWZvpc
msgbatch_01FMyJFAAdxZ4P1vHGJ51nU3
msgbatch_01FSMYiC3ZUD25bfHGNLxwqE
msgbatch_01Fj4jknttokYdXdECMnxYxn
msgbatch_01G5gsRNHxBTbfmWCWmNGU5d
msgbatch_01GWryeiCozmFJPhDsqLh7sp
msgbatch_01Gdiq4ynDRvML6S5nJyfeHD
msgbatch_01GtnZg4AAV8oZKxbmyyBHuK
msgbatch_01Gw85ALcqtDVu3ZWNxpkMAG
msgbatch_01HtEX7V6NrU9f6VLTGdBUco
msgbatch_01JHkNy4Mdcn21so4dza1dUK
msgbatch_01Jm9eaNX3xZMu5XgHxr18vk
msgbatch_01JpGRFSp17PaE2hZYLo3K7Q
msgbatch_01Jwb74paGQTEXUUgdVHDrpS
msgbatch_01K2mNt7AFYRK5G9ZnNRhoA8
msgbatch_01KDs7hCPptEsHLyAkDq9faq
msgbatch_01KfgUsYMSzMoMrR9YdWXqtY
msgbatch_01LB2u6iZs2NfHaFdHcqXPQ9
msgbatch_01Lg9cfYgQqtHR1bpynsZFDc
msgbatch_01NrixRLa1f4UNDfeUPRf1Hq
msgbatch_01Q4meZzVEQtmQm9VJLwDqZt
msgbatch_01Q6VaxuVCiTbBrb2bEsf7pJ
msgbatch_01R5oqNF3wvdNQzdzYZzMnaH
msgbatch_01ScstKHFkbTsfcPLhM3UgNE
msgbatch_01SgRH6rXhPyz15XdRBXxZkZ
msgbatch_01SwDoX52aXDnB8z8Ed4TWRA
msgbatch_01T7SpQd9jhrWzvD849dxmAu
msgbatch_01T83UMZ9tJ3B327wRHCpmBK
msgbatch_01UE7TDKfJ1qsotAEECM3d1q
msgbatch_01UKxeeUWvY6RWe18AGfat1d
msgbatch_01VhjMamP1B4hUHHmf2sj3ED
msgbatch_01VmYBvwNy9N4b2nj4Z9uJ1n
msgbatch_01WCjmNGk9fNYP4JfHA8GTEn
msgbatch_01YKnuVE4cDHjeGxZuihWgKE
msgbatch_01YL9jMQkZxzKGbpNtY6RQXf
```

Examples already seen as structured recover rows (not exhaustive): `msgbatch_01DZffivXdtkaiMtmuwLUeG4` (pre_filter processing, 50 HF datasets/spaces), `msgbatch_01Jm9eaNX3xZMu5XgHxr18vk` (enrichment_stage1 submitted, 10 github), `msgbatch_012PRbfTv5YSXYUZiC7SXi9c` / `msgbatch_01UKxeeUWvY6RWe18AGfat1d` (pre_filter complete, arxiv — these were applied before corruption if those manifest rows survived).

---

## Appendix B — one-line operator intent

> Salvage what we paid for, repair the file, apply results from Anthropic, land integrity/health/mount hardening and a 30-minute integrity-gated snapshot rotator with a boring restore script, keep the live name `bishop.db`, do not auto-swap while up, do not wipe unless salvage is hopeless.
