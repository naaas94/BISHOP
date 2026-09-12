# Bishop SQLite — agent reference

Standing note for live `bishop.db`. Cursor rule: `.cursor/rules/bishop-sqlite.mdc`.
Spec tables: `bishop_spec_0_6.md` §7. Enums: `services/state-worker/app/enums.py`.

## Paths

| Role | Path |
|------|------|
| Filename constant | `bishop_shared/constants.py` → `SQLITE_DB_FILENAME = "bishop.db"` |
| Container | `/app/data/sqlite/bishop.db` (`SQLITE_DB_PATH`) |
| Host | `${BISHOP_DATA_ROOT}/sqlite/bishop.db` (canonical). **This host, 2026-09-11 evening:** live file is `${BISHOP_DATA_ROOT}/sqlite_live/bishop.db` — Docker leaked handles on the old `sqlite/bishop.db-wal`; compose override remounts `sqlite_live`. Snapshots stay in `sqlite/snapshots/`. |
| Sidecars | `bishop.db-wal`, `bishop.db-shm` when WAL is on |
| Migrations | `alembic/versions/m1_001_initial_schema.py`, `m3_001_batch_source_ids.py` |
| Domain models | `services/state-worker/app/models/domain.py` |
| Transitions | `services/state-worker/app/transitions.py` |
| Query-api read | `services/query-api/app/sqlite_reader.py` (`file:…?mode=ro`) |

`.env` is gitignored. `BISHOP_DATA_ROOT` must be an explicit path on Windows.

## Access doctrine

- **Single writer:** `state-worker` (aiosqlite pool, WAL). Migrations run sync at startup (`run_migrations()`), then the async pool starts.
- **Readers:** query-api (stdlib `sqlite3` read-only URI), humans/scripts with `mode=ro`.
- **Workers** (scraper, pre-filter, content-scraper, enrichment, batch-poller, vector-writer) never open the file. They POST `/manifest/*`, `/entries/*`, `/batches/*`.
- **Transactions:** aiosqlite `async with conn` is not a transaction. Multi-step writes use explicit `BEGIN` / `COMMIT` / `ROLLBACK`.
- **Do not** write scraped HTML or shell redirects into `bishop.db`. See `.dev/db_hardening.md` (2026-06-13 corruption).

## Tables

Six application tables + `alembic_version`.

### `manifest` — every discovered item

Identity: `source_id` PK (`arxiv:2606.xxxxx`), `source`, `url`, `title`, `abstract`, `published_at`, `discovered_at`, `domain`.

Pre-filter: `profile_version`, `pre_filter_batch_id`, `relevance_decision` (0/1/NULL), `pre_filter_rationale`.

State: `processing_state`, `retry_count`, `next_retry_at`.

### `entries` — KB rows (pre-filter pass only)

Created at scrape. Enrichment fields start NULL.

Identity: `id` (UUID PK), `source_id` unique, `content_raw`, `ingested_at`.

Carried from manifest: `profile_version`, `pre_filter_batch_id`, `pre_filter_rationale`.

Call 1: `summary`, `concepts`, `tags`, `entry_type`, `challenge_hooks`, `enrichment_stage1_batch_id`.

Call 2: `relevance_score`, `relevance_reason`, `value_rationale`, `enrichment_stage2_batch_id`.

UI: `reading_status`, `flagged_for_review`, `processing_state`.

JSON-text list columns: `concepts`, `tags`, `challenge_hooks`, `references`, `cited_by` — `json.dumps` / `json.loads` at the Pydantic boundary.

### Other

- `batches` — Anthropic batch lifecycle; `source_ids` JSON added in `m3_001`.
- `error_log` — failures + ALERT siblings.
- `oov_tags_log` — tags stripped from Call 1.
- `scraper_state` — per-source `last_successful_run_at`.

## `processing_state` (not “processed”)

Happy path:

```
DISCOVERED → RELEVANCE_QUEUED → RELEVANCE_PASSED | RELEVANCE_REJECTED
RELEVANCE_PASSED → SCRAPE_QUEUED → SCRAPED
→ ENRICHMENT_STAGE1_* → ENRICHMENT_STAGE2_*
→ VECTOR_WRITE_QUEUED → INDEXED
```

`RELEVANCE_REJECTED` is terminal on `manifest` (no `entries` row).
`INDEXED` is terminal success on both tables (manifest is also flipped to `INDEXED` after index).

## Relevance (two gates)

| Gate | When | Fields | Meaning |
|------|------|--------|---------|
| Pre-filter | title + abstract | `manifest.relevance_decision`, `pre_filter_rationale` | Binary. Prompt from `config/profiles/professional_v1.0.0.yaml` via `bishop_shared/profile_renderer.py` |
| Enrichment Call 2 | title + summary | `entries.relevance_score`, `relevance_reason`, `value_rationale` | 0–1 score. Same profile. |

Do not treat `relevance_score` as the pre-filter gold. Eval gold lives in `eval/prefilter_v0/`.

## Recipes (host Python, read-only)

```python
import sqlite3
from pathlib import Path

db = Path(r"C:/Users/Ale/bishop_data/sqlite/bishop.db")
conn = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
conn.row_factory = sqlite3.Row
```

Indexed knowledge-base rows (all columns):

```sql
SELECT * FROM entries
WHERE processing_state = 'INDEXED'
ORDER BY ingested_at DESC;
```

Pre-filter passed, including not-yet-scraped:

```sql
SELECT * FROM manifest
WHERE relevance_decision = 1
ORDER BY discovered_at DESC;
```

Pre-filter rejected:

```sql
SELECT * FROM manifest
WHERE relevance_decision = 0
ORDER BY discovered_at DESC;
```

State histogram:

```sql
SELECT processing_state, relevance_decision, COUNT(*)
FROM manifest
GROUP BY 1, 2;
```

Join for calibration (abstract + score):

```sql
SELECT e.*, m.abstract, m.discovered_at, m.relevance_decision
FROM entries e
JOIN manifest m ON m.source_id = e.source_id
WHERE e.processing_state = 'INDEXED';
```

## Frozen vs live

| Artifact | What it is |
|----------|------------|
| Live `bishop.db` | Current pipeline state. Mutates when compose is up. |
| `calibration/` | One-off export from 2026-09-09. Working notes. |
| `eval/prefilter_v0/items.json` | Frozen 129-item eval inputs. Do not edit after freeze. |
| `eval/prefilter_v0/labels.json` | Human gold. Schema in `contract.json`. |
| `eval/prefilter_v0/suggested.json` | Clustering prior only — not gold. |

Replay protocol and reason vocab: `eval/prefilter_v0/contract.json`.
Metrics: `python scripts/eval_prefilter_metrics.py`.

## Snapshots and restore

Integrity-gated snapshots run every 30 minutes; the live filename never rotates.

| Thing | Value |
|-------|-------|
| Snapshot dir | `${BISHOP_DATA_ROOT}/sqlite/snapshots/` |
| Name | `bishop-YYYYmmdd-HHMMSS.db` |
| TTL | 24h (~48 snapshots, ~0.8GB/day) |
| Scheduled task | `BishopSqliteSnapshot` (register via `scripts/register-snapshot-task.ps1`) |

Only files that pass `integrity_check` are published — both the live source and the
finished copy are checked, and a failing attempt is deleted. Copies use the SQLite online
backup API from a `mode=ro` connection, so it is safe while state-worker is writing.
Never `copy` a live WAL database and call it a backup.

```powershell
python scripts/sqlite_snapshot.py              # one snapshot + prune (what the task runs)
python scripts/sqlite_snapshot.py --prune-only
```

Restore is explicit and never automatic:

```powershell
docker compose down
python scripts/sqlite_restore.py --latest      # or --file <snapshot>  (--dry-run to preview)
docker compose up -d
```

It refuses if compose is up (exit 2), refuses a snapshot that fails integrity (exit 3),
keeps the replaced file as `bishop.db.pre-restore-<ts>`, deletes stale `-wal`/`-shm`, and
re-verifies the installed file (exit 4). In-flight Anthropic batches in the restored
`batches` table are re-fetched — not re-submitted — by batch-poller's startup scan.

## If the file looks wrong

state-worker now **refuses to start** on a database that fails `integrity_check`, before
Alembic runs. It logs `event=sqlite_integrity_failed`, the newest passing snapshot names
and the remediation command. `GET /health/db` does real DB I/O and returns 503 when the
database is unusable; the compose healthcheck uses it, so a bad DB blocks the whole stack
instead of letting workers crash-loop. `GET /health` is liveness only — a green `/health`
does **not** mean the DB is fine.

Check the first bytes are `SQLite format 3`. HTML at byte 0 means the file was overwritten
(2026-06-13 incident). But `Back to arXiv` *inside* the file is normal — that is
`entries.content_raw` holding scraped HTML on overflow pages, and it is not evidence of
overwrite. Quarantine; do not run `init_pool` against a second writer while state-worker
is up.

**2026-09-11 torn-page corruption — salvaged, root-caused, hardened.** Read
`.dev/decision-logs/ops/sqlite-snapshot-and-integrity-gate.md` before ever considering
another Path B wipe. Salvage recovered 1764 manifest / 160 entries / 69 batches and
re-paid nothing. Root cause was **not** the bind mount: a sweep raised mid-write and
`get_db()` returned the connection to the pool with its write transaction open, which held
the single WAL write lock and 500'd everything while `/health` stayed green. Salvage tool:
`scripts/sqlite_salvage.py`. Evidence: `_quarantine_2026-09-11_corrupt-salvage/` and
`_salvage_2026-09-11/` under `BISHOP_DATA_ROOT`.

## Named-volume migration (proposed, not yet cut over)

**Status:** proposal + tooling landed 2026-09-11; **live sqlite mount is still the bind
mount today.** Full design, cutover runbook, and rollback plan:
`.dev/decision-logs/ops/sqlite-named-volume-migration.md`. Do not treat any recipe below
as changed until an operator has run that runbook and updated this line.

Summary for future reference once cut over:
- Both `scripts/sqlite_snapshot.py` and `scripts/sqlite_restore.py` gained a `--volume NAME`
  mode that runs the identical snapshot/restore logic inside a throwaway
  `docker run --rm` container mounting the named volume — no forked/duplicate logic.
- `docker-compose.override.named-volume.yml` (repo root) is an opt-in overlay that swaps
  only the `state-worker`/`query-api` sqlite mount from a bind mount to a named volume
  `bishop-sqlite`. It is invisible to a plain `docker compose up -d` (Compose only
  auto-loads a file literally named `docker-compose.override.yml`).
- The `snapshots/` subdirectory does **not** move — it is written by host-side Python, not
  by any container mount, so it stays at `${BISHOP_DATA_ROOT}/sqlite/snapshots/` regardless
  of where the live `bishop.db` lives.
- Container path `/app/data/sqlite/bishop.db` (`SQLITE_DB_PATH`) does not change either way.
