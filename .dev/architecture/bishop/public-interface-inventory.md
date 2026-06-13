Section:      public-interface-inventory
Version:      1.2.0
Last updated: 2026-06-13

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
| `DomainEnum` | `bishop_shared.enums` | enum | §20.3 domain vocabulary (`professional`, `personal`) | scraper adapters, profile_renderer, pre-filter-worker | stable |
| `PROFILES_CONTAINER_DIR` | `bishop_shared.profile_renderer` | constant | Container mount path `/app/config/profiles` | `resolve_profile_path`, pre-filter-worker | active |
| `ProfileDocument` | `bishop_shared.profile_renderer` | class | Pydantic model for NL profile YAML core fields (§11.2) | `load_profile`, tests | active |
| `ProfileAnchor` | `bishop_shared.profile_renderer` | class | Anchor row: `id`, `label`, `rationale`, `weight` | `ProfileDocument` | active |
| `ProfileOutput` | `bishop_shared.profile_renderer` | class | Output spec: `format`, `include_rationale`, `rationale_max_tokens`, `instruction` | `ProfileDocument` | active |
| `resolve_profile_path` | `bishop_shared.profile_renderer` | function | Maps `DomainEnum` → profile YAML path; M3: professional only | pre-filter-worker loop | active |
| `compute_profile_hash` | `bishop_shared.profile_renderer` | function | SHA-256 canonical hash per §11.3 (excludes `canonical_hash` key) | pre-filter-worker, tests | active |
| `load_profile` | `bishop_shared.profile_renderer` | function | Load and validate YAML → `ProfileDocument` | pre-filter-worker loop | active |
| `render_profile_prompt` | `bishop_shared.profile_renderer` | function | Deterministic system prompt from `ProfileDocument` | pre-filter-worker Anthropic client | active |
| `ANTHROPIC_MODEL_PREFILTER` | `bishop_shared.anthropic_config` | constant | Pinned model `claude-haiku-4-5-20251001` (§12.1) | pre-filter-worker, batch-poller, G3 gate | stable |
| `get_anthropic_api_key` | `bishop_shared.anthropic_config` | function | Reads `ANTHROPIC_API_KEY` from environment | G3 gate, workers | stable |
| `verify_model_string` | `bishop_shared.anthropic_config` | function | Live Messages API probe; returns False on HTTP 400 | G3 scripts, pre-filter-worker `ensure_g3_verified` | stable |

## state-worker — HTTP routes (§9.1)

| Symbol | Module | Kind | Signature summary | Consumed by | Stability |
|--------|--------|------|-------------------|-------------|-----------|
| `health` | `services/state-worker/app/main.py` | route | `GET /health` → `HealthResponse` | compose healthcheck, verify-g1/g2/m3 | stable |
| `post_manifest_batch` | `services/state-worker/app/routers/manifest.py` | route | `POST /manifest/batch` — idempotent manifest ingest | scraper `StateWorkerClient`, G2 tests | stable |
| `get_manifest_poll` | `services/state-worker/app/routers/manifest.py` | route | `GET /manifest/poll?state=&limit=` — atomic poll-and-claim | pre-filter-worker `StateWorkerClient` | stable |
| `get_entries_poll` | `services/state-worker/app/routers/poll.py` | route | `GET /entries/poll?state=` — atomic poll-and-claim; omits `content_raw` at `VECTOR_WRITE_QUEUED` | future workers, G2 contract test | stable |
| `post_pre_filter_results` | `services/state-worker/app/routers/entries.py` | route | `POST /manifest/pre-filter-results` | batch-poller `StateWorkerClient` | stable |
| `post_entries_content` | `services/state-worker/app/routers/entries.py` | route | `POST /entries/content` | future content-scraper | stable |
| `post_enrichment_stage1_results` | `services/state-worker/app/routers/entries.py` | route | `POST /entries/enrichment-stage1-results` | future enrichment-batcher | stable |
| `post_enrichment_stage2_results` | `services/state-worker/app/routers/entries.py` | route | `POST /entries/enrichment-stage2-results` | future batch-poller (enrichment) | stable |
| `post_entries_indexed` | `services/state-worker/app/routers/entries.py` | route | `POST /entries/indexed` | future vector-writer | stable |
| `post_entries_failed` | `services/state-worker/app/routers/entries.py` | route | `POST /entries/failed` | all pipeline workers | stable |
| `post_entries_retry` | `services/state-worker/app/routers/entries.py` | route | `POST /entries/retry` — manual retry | ui / ops (future) | stable |
| `post_batches` | `services/state-worker/app/routers/batches.py` | route | `POST /batches` — register batch at submit time (201) | pre-filter-worker `StateWorkerClient` | active |
| `patch_batches` | `services/state-worker/app/routers/batches.py` | route | `PATCH /batches/{batch_id}` — lifecycle status update | batch-poller `StateWorkerClient` | active |
| `post_batch_timeout` | `services/state-worker/app/routers/batches.py` | route | `POST /batches/{batch_id}/timeout` — reset RELEVANCE_QUEUED rows | batch-poller `StateWorkerClient` | active |
| `get_batches` | `services/state-worker/app/routers/batches.py` | route | `GET /batches?status=` — CSV status filter | batch-poller startup scan and poll loop | stable |
| `get_batch_detail` | `services/state-worker/app/routers/batches.py` | route | `GET /batches/{batch_id}` | batch-poller, tests | stable |
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
| `register_batch` | `services/state-worker/app/transitions.py` | function | Insert batch row at Anthropic submit; 409 on duplicate `batch_id` | batches router | active |
| `patch_batch` | `services/state-worker/app/transitions.py` | function | Update batch status and counters | batches router | active |
| `apply_batch_timeout` | `services/state-worker/app/transitions.py` | function | Reset `RELEVANCE_QUEUED` manifests to `DISCOVERED`; batch → `batch_timed_out` | batches router | active |
| `apply_pre_filter_results` | `services/state-worker/app/transitions.py` | function | Apply decision 0/1 to `RELEVANCE_QUEUED` manifests | entries router | active |
| `record_failure` | `services/state-worker/app/transitions.py` | function | Failure transition + ErrorLog + optional alert | entries router, sweeps | stable |
| `emit_alert` | `services/state-worker/app/alerts.py` | function | Dual-write CRITICAL log + ALERT `error_log` row | `record_failure`, M1 triggers, pre-filter profile hash mismatch | stable |
| `BatchNotFoundError` | `services/state-worker/app/transitions.py` | class | Batch ID not in DB → 404 | batches router | active |
| `BatchConflictError` | `services/state-worker/app/transitions.py` | class | Duplicate batch registration → 409 | batches router | active |
| `BatchInvalidStateError` | `services/state-worker/app/transitions.py` | class | Illegal batch state transition → 409 | batches router | active |
| `run_migrations` | `services/state-worker/app/db.py` | function | Sync Alembic upgrade to head | lifespan startup | stable |
| `init_pool` / `get_db` | `services/state-worker/app/db.py` | function | Async aiosqlite connection pool (WAL) | all routers | stable |
| `ProcessingState` | `services/state-worker/app/enums.py` | enum | Complete §6.1 state machine (22 values) | transitions, routers, tests | stable |
| `BatchRecord` | `services/state-worker/app/models/domain.py` | class | Domain model for `batches` table incl. `source_ids` | transitions, batches router | active |
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

## pre-filter-worker

| Symbol | Module | Kind | Signature summary | Consumed by | Stability |
|--------|--------|------|-------------------|-------------|-----------|
| `prefilter_cycle` | `services/pre-filter-worker/app/loop.py` | function | Poll DISCOVERED manifests, render profile, submit Anthropic batch | scheduler, tests | active |
| `ensure_g3_verified` | `services/pre-filter-worker/app/loop.py` | function | One-time G3 probe or `BISHOP_G3_VERIFIED=1` bypass | `prefilter_cycle` | active |
| `StateWorkerClient` | `services/pre-filter-worker/app/state_worker_client.py` | class | httpx client: manifest poll + batch register | `loop.py`, tests | active |
| `AnthropicBatchClient` | `services/pre-filter-worker/app/anthropic_batch_client.py` | class | Build requests and `messages.batches.create` | `loop.py`, tests | active |
| `submit_pre_filter_batch_or_fatal` | `services/pre-filter-worker/app/anthropic_batch_client.py` | function | Submit batch; fatal on model-string 400 | `prefilter_cycle` | active |
| `ModelStringFatalError` | `services/pre-filter-worker/app/anthropic_batch_client.py` | class | Non-recoverable invalid model string | loop | active |
| `emit_profile_hash_mismatch_alert` | `services/pre-filter-worker/app/alerts.py` | function | CRITICAL log on profile hash mismatch | `prefilter_cycle` | active |
| `run_scheduler` | `services/pre-filter-worker/app/main.py` | function | asyncio loop on `BISHOP_PREFILTER_POLL_INTERVAL_SEC` | Docker CMD | active |

## batch-poller

| Symbol | Module | Kind | Signature summary | Consumed by | Stability |
|--------|--------|------|-------------------|-------------|-----------|
| `startup_scan` | `services/batch-poller/app/startup.py` | function | Reconcile in-flight batches on process start | `main.py`, tests | active |
| `poll_loop` / `poll_once` | `services/batch-poller/app/loop.py` | function | Poll Anthropic batch status; post results or timeout | `main.py`, tests | active |
| `parse_pre_filter_response` | `services/batch-poller/app/loop.py` | function | Parse Anthropic result JSON → decision + rationale | `poll_once` | active |
| `StateWorkerClient` | `services/batch-poller/app/clients/state_worker.py` | class | httpx client: batches list/patch/timeout + pre-filter results | loop, startup | active |
| `AnthropicBatchPollerClient` | `services/batch-poller/app/clients/anthropic.py` | class | `batches.retrieve` + `batches.results` | loop | active |
| `PRE_FILTER_BATCH_TYPE` | `services/batch-poller/app/models.py` | constant | `"pre_filter"` — rejects non-pre-filter batches | loop | active |
| `run_poller` | `services/batch-poller/app/main.py` | function | Startup scan then asyncio poll loop | Docker CMD | active |

## M0 stubs (unchanged surface)

| Symbol | Module | Kind | Signature summary | Consumed by | Stability |
|--------|--------|------|-------------------|-------------|-----------|
| `main` | `services/<stub>/stub_main.py` | function | Long-running loop or HTTP server entry | Docker CMD (content-scraper, enrichment-batcher, vector-writer, query-api, ui) | experimental |
| `RootHandler` | `services/query-api/stub_main.py`, `services/ui/stub_main.py` | class | `GET /` → `200 ok` | stub HTTP servers, tests | experimental |

**Re-exports:** `bishop_shared/__init__.py` re-exports constants, `VolumeMount`, `SourceEnum`, `DomainEnum` only — `profile_renderer` and `anthropic_config` are direct imports.

**Not yet public:** `fetch_content` implementation (M4), additional source adapters beyond ArXiv, `personal` domain profile, enrichment batch wire formats, query-api read surface, LanceDB/DuckDB/BM25 access.
