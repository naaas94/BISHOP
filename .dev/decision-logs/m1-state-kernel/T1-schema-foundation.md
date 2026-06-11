# T1 — schema foundation

**Plan:** m1-state-kernel · **Date:** 2026-06-11

## Chosen approach

- **SQLite path:** `SQLITE_DB_FILENAME = "bishop.db"` and `SQLITE_DB_PATH = "/app/data/sqlite/bishop.db"` frozen in `bishop_shared/constants.py`, derived from the existing sqlite volume mount (plan flag 2 resolution).
- **Enum placement:** All `ProcessingState` and §20 enums live in `services/state-worker/app/enums.py` only — not `bishop_shared` (plan flag 1 resolution).
- **Schema migration:** Alembic at repo root (`alembic.ini`, `alembic/env.py`, revision `m1_001_initial_schema`) creates six tables (`manifest`, `entries`, `batches`, `error_log`, `oov_tags_log`, `scraper_state`) with ISO8601 text datetimes, integer booleans, and JSON-encoded text for `list[str]` columns per §7.2.
- **Domain models:** Pydantic v2 models in `app/models/domain.py` with `to_db_row()` / `from_db_row()` encoding `concepts`, `tags`, `challenge_hooks`, `references`, `cited_by`, `top_entries` via `json.dumps` / `json.loads`.
- **HTTP wire models:** Documented §9.1 shapes in `app/models/http.py` plus derived models for undocumented endpoints (below).
- **DB layer:** `run_migrations()` runs sync Alembic `upgrade head` then sets WAL via sync SQLAlchemy; `init_pool()` / `get_db()` provide an aiosqlite queue pool with WAL per connection.
- **Config:** `RETRY_MAX_ATTEMPTS` (default 3), `SWEEP_INTERVAL_SEC` (300), `STUCK_THRESHOLD_SEC` (900) with `BISHOP_*` env overrides.
- **M0 models split:** `app/models.py` replaced by `app/models/` package (`__init__.py` re-exports `HealthResponse`; `domain.py`, `http.py` added) so `from app.models import HealthResponse` remains valid.

### Derived wire models (undocumented §9.1 bodies)

| Endpoint | Request | Response |
|----------|---------|----------|
| `POST /manifest/pre-filter-results` | `PreFilterResultsRequest`: `{batch_id, profile_version, entries: [{source_id, decision: 0\|1, pre_filter_rationale}]}` — derived from §5.2 steps 8–9 | `PreFilterResultsResponse`: `{updated, passed, rejected}` counts |
| `POST /entries/retry` | `RetryPostRequest`: `{source_id}` — derived from §14.2 manual retry | `RetryPostResponse`: `{source_id, processing_state}` after transition |
| `GET /batches?status=...` | query param `status` comma-separated | `BatchesListResponse`: `{batches: [BatchRecord]}` |
| `GET /batches/{batch_id}` | path `batch_id` | `BatchDetailResponse`: `{batch: BatchRecord}` |
| `GET /escalations` | — | `EscalationsResponse`: `{entries: [{source_id, title, source, url, processing_state, error_log: [ErrorLog]}]}` per §14.2 panel fields |

`POST /manifest/batch` response `{inserted, skipped}` and `POST /entries/content` response `{entry_id, processing_state}` are plan §2 derived envelopes (not full spec JSON).

## Alternatives rejected

- **Enums in `bishop_shared`:** Rejected — plan flag 1 assigns M1 ownership to state-worker; downstream services read SQLite strings, not Python enums.
- **SQLAlchemy ORM models for runtime:** Rejected for T1 — runtime uses aiosqlite + Pydantic domain models; Alembic migration uses raw `op.create_table` without ORM metadata to keep the async/sync split explicit per §8.1.
- **Native SQLite JSON type for list columns:** Rejected — spec §7.2 explicitly documents `json.dumps`/`json.loads` on text columns at the state-worker boundary.

## Assumptions made

- ISO8601 text storage for all datetime columns is sufficient for MVP ordering and filtering; no separate migration for native SQLite datetime affinity.
- `entries.source_id` unique index enforces one Entry per manifest source at the DB layer.
- `app/models/__init__.py` creation and `app/models.py` removal are implied by the packet paths `app/models/domain.py` and `app/models/http.py`; import path `app.models.HealthResponse` is preserved.
- Alembic `repo_root` resolution via `Path(__file__).parents[3]` from `app/db.py` matches repo-root Docker build context.

## Items deferred

- **JSON list column read path outside state-worker:** batch-poller/query-api raw SQL reads return JSON text, not Python lists — documented coupling; no reader services exist until M2+.
- **Docker image build verification for Alembic COPY:** deferred to T5/T6 compose smoke; Dockerfile COPY lines added per packet risk mitigation.
- **CHECK constraints on `processing_state` enum values:** application-layer validation via enum tests only; DB-level CHECK deferred to avoid migration churn if spec adds states.
