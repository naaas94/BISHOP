Section:      public-interface-inventory
Version:      1.1.0
Last updated: 2026-06-12

## bishop_shared

| Symbol | Module | Kind | Signature summary | Consumed by | Stability |
|--------|--------|------|-------------------|-------------|-----------|
| `VolumeMount` | `bishop_shared.constants` | class | Frozen dataclass: `host_suffix`, `container_path` | tests, init scripts | stable |
| `BISHOP_SERVICES` | `bishop_shared.constants` | constant | Tuple of nine compose service keys in spec order | compose, tests, scripts | stable |
| `BISHOP_VOLUME_MOUNTS` | `bishop_shared.constants` | constant | List of six host→container volume pairs per spec §8.5 | compose, init scripts, tests | stable |
| `BISHOP_DATA_ROOT_DEFAULT` | `bishop_shared.constants` | constant | Default host data root `~/bishop_data` | `.env.example`, tests | stable |
| `STATE_WORKER_INTERNAL_PORT` | `bishop_shared.constants` | constant | Internal HTTP port `8000` | compose, state-worker, query-api stub | stable |
| `QUERY_API_HOST_PORT` | `bishop_shared.constants` | constant | Host-mapped port `8080` for query-api | compose, verify-g1, tests | stable |
| `UI_HOST_PORT` | `bishop_shared.constants` | constant | Host-mapped port `8081` for ui | compose, verify-g1, tests | stable |
| `SQLITE_DB_FILENAME` | `bishop_shared.constants` | constant | SQLite filename `bishop.db` | `SQLITE_DB_PATH` derivation, tests | stable |
| `SQLITE_DB_PATH` | `bishop_shared.constants` | constant | Absolute container DB path `/app/data/sqlite/bishop.db` | `services/state-worker/app/db.py`, tests | stable |
| `SourceEnum` | `bishop_shared.enums` | enum | §20.1 source vocabulary (7 members) | scraper, drift guard test | stable |
| `DomainEnum` | `bishop_shared.enums` | enum | §20.3 domain vocabulary (`professional`, `personal`) | scraper adapters, drift guard test | stable |

## state-worker — HTTP routes (§9.1)

| Symbol | Module | Kind | Signature summary | Consumed by | Stability |
|--------|--------|------|-------------------|-------------|-----------|
| `health` | `services/state-worker/app/main.py` | route | `GET /health` → `HealthResponse` | compose healthcheck, verify-g1/g2 | stable |
| `post_manifest_batch` | `services/state-worker/app/routers/manifest.py` | route | `POST /manifest/batch` — idempotent manifest ingest | scraper `StateWorkerClient`, G2 tests | stable |
| `get_manifest_poll` | `services/state-worker/app/routers/manifest.py` | route | `GET /manifest/poll?state=` — atomic poll-and-claim | future pre-filter-worker (M3+) | stable |
| `get_entries_poll` | `services/state-worker/app/routers/poll.py` | route | `GET /entries/poll?state=` — atomic poll-and-claim; omits `content_raw` at `VECTOR_WRITE_QUEUED` | future workers, G2 contract test | stable |
| `post_pre_filter_results` | `services/state-worker/app/routers/entries.py` | route | `POST /manifest/pre-filter-results` | future pre-filter-worker | stable |
| `post_entries_content` | `services/state-worker/app/routers/entries.py` | route | `POST /entries/content` | future content-scraper | stable |
| `post_enrichment_stage1_results` | `services/state-worker/app/routers/entries.py` | route | `POST /entries/enrichment-stage1-results` | future batch-poller | stable |
| `post_enrichment_stage2_results` | `services/state-worker/app/routers/entries.py` | route | `POST /entries/enrichment-stage2-results` | future batch-poller | stable |
| `post_entries_indexed` | `services/state-worker/app/routers/entries.py` | route | `POST /entries/indexed` | future vector-writer | stable |
| `post_entries_failed` | `services/state-worker/app/routers/entries.py` | route | `POST /entries/failed` | all pipeline workers | stable |
| `post_entries_retry` | `services/state-worker/app/routers/entries.py` | route | `POST /entries/retry` — manual retry | ui / ops (future) | stable |
| `get_batches` | `services/state-worker/app/routers/batches.py` | route | `GET /batches?status=` | future enrichment-batcher, batch-poller | stable |
| `get_batch_detail` | `services/state-worker/app/routers/batches.py` | route | `GET /batches/{batch_id}` | future batch-poller | stable |
| `get_scraper_state` | `services/state-worker/app/routers/scraper_state.py` | route | `GET /scraper-state/{source}` | scraper `StateWorkerClient` | stable |
| `post_scraper_state` | `services/state-worker/app/routers/scraper_state.py` | route | `POST /scraper-state/{source}` → `204` | scraper `StateWorkerClient` | stable |
| `get_escalations` | `services/state-worker/app/routers/escalations.py` | route | `GET /escalations` | ui / ops (future) | stable |
| `run` | `services/state-worker/app/main.py` | function | Starts uvicorn on `STATE_WORKER_INTERNAL_PORT` | Docker CMD | stable |

## state-worker — transition engine and infrastructure

| Symbol | Module | Kind | Signature summary | Consumed by | Stability |
|--------|--------|------|-------------------|-------------|-----------|
| `ingest_manifest_batch` | `services/state-worker/app/transitions.py` | function | Idempotent batch insert; returns inserted/skipped counts | manifest router, G2 tests | stable |
| `claim_manifest_poll` | `services/state-worker/app/transitions.py` | function | Atomic poll-and-claim for manifest rows | manifest poll router | stable |
| `claim_entries_poll` | `services/state-worker/app/transitions.py` | function | Atomic poll-and-claim for entry rows | entries poll router | stable |
| `record_failure` | `services/state-worker/app/transitions.py` | function | Failure transition + ErrorLog + optional alert | entries router, sweeps | stable |
| `emit_alert` | `services/state-worker/app/alerts.py` | function | Dual-write CRITICAL log + ALERT `error_log` row | `record_failure`, M1 triggers | stable |
| `run_migrations` | `services/state-worker/app/db.py` | function | Sync Alembic upgrade to head | lifespan startup | stable |
| `init_pool` / `get_db` | `services/state-worker/app/db.py` | function | Async aiosqlite connection pool (WAL) | all routers | stable |
| `ProcessingState` | `services/state-worker/app/enums.py` | enum | Complete §6.1 state machine (22 values) | transitions, routers, tests | stable |
| `ManifestEntry` | `services/state-worker/app/models/domain.py` | class | Domain model for `manifest` table | transitions, routers | stable |
| `Entry` | `services/state-worker/app/models/domain.py` | class | Domain model for `entries` table | transitions, routers | stable |
| `HealthResponse` | `services/state-worker/app/models/__init__.py` | class | Pydantic: `status: Literal["ok"]` | health route | stable |

## scraper

| Symbol | Module | Kind | Signature summary | Consumed by | Stability |
|--------|--------|------|-------------------|-------------|-----------|
| `SourceAdapter` | `services/scraper/app/adapters/base.py` | class | ABC: `fetch_manifest(since)`, default `fetch_content` → `NotImplementedError("M4")` | `ArxivAdapter`, registry | active |
| `make_source_id` | `services/scraper/app/adapters/base.py` | method | Returns `"{source}:{raw_id}"` canonical ID | adapters, tests | active |
| `ADAPTER_REGISTRY` | `services/scraper/app/adapters/registry.py` | constant | List of adapter classes; M2: `[ArxivAdapter]` only | `loop.py` | active |
| `ArxivAdapter` | `services/scraper/app/adapters/arxiv.py` | class | Atom export API manifest fetch with rate limiting | registry, tests | active |
| `parse_atom_feed` | `services/scraper/app/adapters/arxiv.py` | function | Atom XML → `list[ManifestIngestEntry]` | `ArxivAdapter`, tests | active |
| `failure_envelope` | `services/scraper/app/failure_envelope.py` | function | Async retry wrapper; §6.3 HTTP classification | `loop.py`, tests | active |
| `compute_backoff` | `services/scraper/app/failure_envelope.py` | function | Exponential backoff per §15.2 | `failure_envelope` | active |
| `PermanentFailureError` | `services/scraper/app/exceptions.py` | class | Non-retriable failure (400, 410, etc.) | loop, envelope | active |
| `EscalatableError` | `services/scraper/app/exceptions.py` | class | Escalatable HTTP failure (401, 403, etc.) | loop, envelope | active |
| `RetryExhaustedError` | `services/scraper/app/exceptions.py` | class | Retries exhausted on 429/network | loop, envelope | active |
| `StateWorkerClient` | `services/scraper/app/state_worker_client.py` | class | httpx async client for manifest batch + scraper-state | `loop.py`, tests | active |
| `scrape_cycle` | `services/scraper/app/loop.py` | function | One discovery pass over `ADAPTER_REGISTRY` | scheduler, tests | active |
| `run_scheduler` | `services/scraper/app/main.py` | function | asyncio loop calling `scrape_cycle` on interval | Docker CMD | active |
| `TokenBucketRateLimiter` | `services/scraper/app/rate_limit.py` | class | Async token-bucket per §15.1 | `ArxivAdapter` | active |
| `SOURCE_RATE_LIMITS` | `services/scraper/app/rate_limit.py` | constant | Per-source `RateLimit` config dict | adapters, envelope | active |
| `ManifestIngestEntry` | `services/scraper/app/models.py` | class | Wire DTO for manifest batch POST | client, adapters | active |

## M0 stubs (unchanged surface)

| Symbol | Module | Kind | Signature summary | Consumed by | Stability |
|--------|--------|------|-------------------|-------------|-----------|
| `main` | `services/<stub>/stub_main.py` | function | Long-running loop or HTTP server entry | Docker CMD (non-scraper stubs) | experimental |
| `RootHandler` | `services/query-api/stub_main.py`, `services/ui/stub_main.py` | class | `GET /` → `200 ok` | stub HTTP servers, tests | experimental |

**Re-exports:** `bishop_shared/__init__.py` re-exports constants, `VolumeMount`, `SourceEnum`, `DomainEnum`.

**Not yet public:** `fetch_content` implementation (M4), additional source adapters beyond ArXiv, query-api read surface, LanceDB/DuckDB/BM25 access.
