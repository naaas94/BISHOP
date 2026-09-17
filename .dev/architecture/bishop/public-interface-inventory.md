Section:      public-interface-inventory
Version:      1.4.0
Last updated: 2026-09-13

## bishop_shared

| Symbol | Module | Kind | Signature summary | Consumed by | Stability |
|--------|--------|------|-------------------|-------------|-----------|
| `VolumeMount` | `bishop_shared.constants` | class | Frozen dataclass: `host_suffix`, `container_path` | tests, init scripts | stable |
| `BISHOP_SERVICES` | `bishop_shared.constants` | constant | Tuple of nine compose service keys | compose, tests, scripts | stable |
| `BISHOP_VOLUME_MOUNTS` | `bishop_shared.constants` | constant | Six host→container volume pairs | compose, init scripts, tests | stable |
| `BISHOP_DATA_ROOT_DEFAULT` | `bishop_shared.constants` | constant | Default host data root `~/bishop_data` | `.env.example`, tests | stable |
| `STATE_WORKER_INTERNAL_PORT` | `bishop_shared.constants` | constant | Internal HTTP port `8000` | compose, state-worker, query-api | stable |
| `QUERY_API_HOST_PORT` | `bishop_shared.constants` | constant | Host-mapped port `8080` | compose, verify-g1, tests | stable |
| `UI_HOST_PORT` | `bishop_shared.constants` | constant | Host-mapped port `8081` | compose, verify-g1, tests | stable |
| `SQLITE_DB_FILENAME` / `SQLITE_DB_PATH` | `bishop_shared.constants` | constant | `bishop.db` at `/app/data/sqlite/bishop.db` | state-worker db.py, query-api sqlite_reader, snapshot scripts | stable |
| `SQLITE_SNAPSHOT_*` | `bishop_shared.constants` | constant | Snapshot dir, glob, TTL 24h, interval 30 min | snapshot/restore scripts, db.enforce_integrity | stable |
| `SQLITE_BUSY_TIMEOUT_MS` | `bishop_shared.constants` | constant | `5000` writer busy timeout | state-worker db.py | stable |
| `SourceEnum` | `bishop_shared.enums` | enum | §20.1 source vocabulary (7 members) | scraper, content-scraper, drift guard | stable |
| `DomainEnum` | `bishop_shared.enums` | enum | §20.3 `professional`, `personal` | adapters, profile_renderer | stable |
| `PROFILES_CONTAINER_DIR` | `bishop_shared.profile_renderer` | constant | `/app/config/profiles` | resolve_profile_path | active |
| `Gate` | `bishop_shared.profile_renderer` | type | `Literal["prefilter","enrichment"]` | pin map | active |
| `ProfileDocument` / `ProfileAnchor` / `ProfileOutput` / `CalibrationExample` | `bishop_shared.profile_renderer` | class | NL profile core + peripheral + calibration fields | load_profile, tests | active |
| `resolve_profile_path` | `bishop_shared.profile_renderer` | function | `(domain, gate="prefilter")` → YAML path; professional only | pre-filter-worker, enrichment-batcher | active |
| `compute_profile_hash` / `load_profile` / `render_profile_prompt` | `bishop_shared.profile_renderer` | function | Hash, load, render (`include_output` for Call 2) | both Anthropic gates | active |
| `ANTHROPIC_MODEL_PREFILTER` / `ANTHROPIC_MODEL_ENRICHMENT` | `bishop_shared.anthropic_config` | constant | Both `claude-haiku-4-5-20251001` | submitters, G3 | stable |
| `get_anthropic_api_key` / `verify_model_string` | `bishop_shared.anthropic_config` | function | Env key; live Messages probe | G3, workers | stable |
| `cached_system_blocks` | `bishop_shared.prompt_cache` | function | System blocks with one `cache_control` on last block | pre-filter, Call 1, Call 2 | stable |
| `HAIKU_CACHE_MIN_TOKENS` / `CACHE_TTL` | `bishop_shared.prompt_cache` | constant | `4096`; `"1h"` | tests, cache emitter | stable |
| `load_rubric` / `compute_rubric_hash` / `verify_rubric_hash` / `RubricDocument` | `bishop_shared.rubric_assets` | function/class | Body-only hash-or-abort | three gates | active |
| `BACKFILL_CONFIG` / `SOURCE_SCHEDULE_INTERVAL_SEC` | `bishop_shared.scraper_config` | constant | Per-source windows and cadence | scraper loop | active |
| `load_source_config` / `SourceCategoryConfig` | `bishop_shared.source_config` | function/class | Optional category include/exclude | ArxivAdapter | active |
| `build_call1_system_prompt` / `build_call2_system_prompt` | `bishop_shared.enrichment_prompts` | function | Cache keys B and C | enrichment-batcher | active |
| `parse_call1_response` / `parse_call2_response` | `bishop_shared.enrichment_parsers` | function | Model JSON → parsed dataclasses | batch-poller | active |
| `truncate_content_for_call1` | `bishop_shared.content_truncation` | function | Cap Call 1 user text at 4000 tokens | enrichment-batcher stage1 | active |
| `ENRICHMENT_TRUNCATION_MAX_TOKENS` | `bishop_shared.enrichment_config` | constant | `4000` | `content_truncation` | stable |
| `anthropic_batch_400_event` | `bishop_shared.anthropic_batch_errors` | function | Map Anthropic HTTP 400 → log event name | batch submit clients | active |
| `TAG_TAXONOMY` / `validate_tags` | `bishop_shared.tag_taxonomy` | constant/function | §20.8 scaffold + OOV strip | Call 1 parser | active |
| `EMBEDDING_MODEL` / `EMBEDDING_DIM` / `LANCEDB_*` / `DUCKDB_PATH` / `bm25_domain_root` / `build_embed_text` | `bishop_shared.indexing_config` | constant/function | Index paths and N1 embed text | vector-writer, query-api | stable |
| `tokenize_bm25` | `bishop_shared.bm25_tokenize` | function | BM25 tokenizer | writer + query-api | stable |
| `RRF_K` / `DEFAULT_SEARCH_DOMAIN` | `bishop_shared.query_config` | constant | `60`; `"professional"` | query-api search | stable |
| `source_id_to_batch_custom_id` | `bishop_shared.batch_custom_id` | function | Encode source_id for Anthropic custom_id | three submitters, poller | stable |
| `load_index_policy` / `IndexPolicy` | `bishop_shared.index_policy` | function/class | Gate-2 keep/skim/drop | vector-writer | active |
| `atomic_persist` | `bishop_shared.atomic_persist` | function | temp→fsync→replace | BM25/Lance writers | stable |

**Re-exports:** `bishop_shared/__init__.py` still re-exports constants, `VolumeMount`, `SourceEnum`, `DomainEnum` only.

## state-worker — HTTP routes

| Symbol | Module | Kind | Signature summary | Consumed by | Stability |
|--------|--------|------|-------------------|-------------|-----------|
| `health` | `main.py` | route | `GET /health` → `HealthResponse` | liveness, verify scripts | stable |
| `health_db` | `main.py` | route | `GET /health/db` → alembic version or 503 | compose healthcheck | stable |
| `post_manifest_batch` | `routers/manifest.py` | route | `POST /manifest/batch` | scraper | stable |
| `get_manifest_poll` | `routers/manifest.py` | route | `GET /manifest/poll` | pre-filter-worker, content-scraper | stable |
| `get_entries_poll` | `routers/poll.py` | route | `GET /entries/poll`; omits `content_raw` at `VECTOR_WRITE_QUEUED` | enrichment-batcher, vector-writer | stable |
| `post_pre_filter_results` | `routers/entries.py` | route | `POST /manifest/pre-filter-results` | batch-poller | stable |
| `post_entries_content` | `routers/entries.py` | route | `POST /entries/content` | content-scraper | active |
| `post_enrichment_stage1_results` | `routers/entries.py` | route | `POST /entries/enrichment-stage1-results` | batch-poller | active |
| `post_enrichment_stage2_results` | `routers/entries.py` | route | `POST /entries/enrichment-stage2-results` | batch-poller | active |
| `post_entries_indexed` | `routers/entries.py` | route | `POST /entries/indexed` | vector-writer | active |
| `post_entries_failed` | `routers/entries.py` | route | `POST /entries/failed` | pipeline workers | stable |
| `post_entries_retry` | `routers/entries.py` | route | `POST /entries/retry` | query-api proxy, ui | active |
| `patch_reading_status` | `routers/entries.py` | route | `PATCH /entries/{source_id}/reading-status` | query-api, ui | active |
| `post_entries_permanent_fail` | `routers/entries.py` | route | `POST /entries/permanent-fail` | query-api, ui | active |
| `post_batches` / `patch_batches` / `post_batch_timeout` / `get_batches` / `get_batch_detail` | `routers/batches.py` | route | Batch lifecycle | pre-filter, enrichment-batcher, batch-poller, query-api | active |
| `get_scraper_state` / `post_scraper_state` | `routers/scraper_state.py` | route | Checkpoint GET/POST | scraper | stable |
| `get_escalations` | `routers/escalations.py` | route | `GET /escalations` | query-api, ui | active |
| `get_parked` / `post_parked_promote` | `routers/parked.py` | route | Parked inbox | query-api, ui | active |
| `run` | `main.py` | function | uvicorn on `STATE_WORKER_INTERNAL_PORT` | Docker CMD | stable |

## state-worker — transition engine and infrastructure

| Symbol | Module | Kind | Signature summary | Consumed by | Stability |
|--------|--------|------|-------------------|-------------|-----------|
| `ingest_manifest_batch` / `claim_manifest_poll` / `claim_entries_poll` | `transitions.py` | function | Ingest and poll-and-claim | routers | stable |
| `register_batch` / `patch_batch` / `apply_batch_timeout` | `transitions.py` | function | Batch lifecycle | batches router | active |
| `apply_pre_filter_results` | `transitions.py` | function | decision 0/1 + peripheral → PARKED | entries router | active |
| `create_entry_from_content` | `transitions.py` | function | Persist fetch_content body | POST /entries/content | active |
| `apply_enrichment_stage1_results` / `apply_enrichment_stage2_results` | `transitions.py` | function | H3 apply | batch-poller | active |
| `mark_indexed` | `transitions.py` | function | → INDEXED | vector-writer | active |
| `list_parked_manifests` / `promote_parked` | `transitions.py` | function | Parked inbox | parked router | active |
| `update_reading_status` / `mark_permanently_failed` | `transitions.py` | function | Ops mutations | entries router | active |
| `record_failure` / `emit_alert` | `transitions.py` / `alerts.py` | function | Failure + dual-write alert | routers, sweeps | stable |
| `run_lock_state_recovery_sweep` / `run_retry_sweep` | `transitions.py` | function | Background recovery | sweeps.py | active |
| `enforce_integrity` / `run_migrations` / `init_pool` / `get_db` | `db.py` | function | Startup integrity, Alembic, WAL pool | lifespan | stable |
| `ProcessingState` | `enums.py` | enum | 22 members including `RELEVANCE_PARKED` | all workers | active |
| `BatchTypeEnum` / `ReadingStatusEnum` | `enums.py` | enum | batch types; unread/reading/read/archived | batches, PATCH | active |
| `ManifestEntry` / `Entry` / `BatchRecord` / `ErrorLog` | `models/domain.py` | class | Domain models | transitions, routers | active |
| `HealthResponse` / `DbHealthResponse` | `models/__init__.py` | class | Liveness / readiness JSON | health routes | stable |

## scraper

| Symbol | Module | Kind | Signature summary | Consumed by | Stability |
|--------|--------|------|-------------------|-------------|-----------|
| `SourceAdapter` | `adapters/base.py` | class | ABC: `fetch_manifest(since)`, `fetch_content` (default still raises; all seven impls override) | registry | active |
| `ADAPTER_REGISTRY` | `adapters/registry.py` | constant | Seven adapter classes | loop.py, content-scraper resolver | active |
| `ArxivAdapter` … `SemanticScholarAdapter` | `adapters/*.py` | class | Manifest + fetch_content | registry | active |
| `failure_envelope` / `PermanentFailureError` / `EscalatableError` / `RetryExhaustedError` | `failure_envelope.py`, `exceptions.py` | function/class | Retry wrapper + classified failures | loop | active |
| `StateWorkerClient` | `state_worker_client.py` | class | Manifest batch + scraper-state | loop | active |
| `scrape_cycle` / `run_scheduler` | `loop.py`, `main.py` | function | Discovery pass + scheduler | Docker CMD | active |
| `TokenBucketRateLimiter` / `SOURCE_RATE_LIMITS` / `RateLimit` | `rate_limit.py` | class/constant | Per-source limits (`calls`, `period_seconds`, …) | adapters | active |
| `ManifestIngestEntry` | `models.py` | class | Wire DTO for manifest POST | adapters, client | active |

## pre-filter-worker

| Symbol | Module | Kind | Signature summary | Consumed by | Stability |
|--------|--------|------|-------------------|-------------|-----------|
| `prefilter_cycle` / `ensure_g3_verified` | `loop.py` | function | Poll, hash-or-abort, cache key A, hold, submit | scheduler | active |
| `PREFILTER_MIN_BATCH_SIZE` / `PREFILTER_MAX_HOLD_MINUTES` | `config.py` | constant | Defaults 25 / 30 | hold-before-submit | active |
| `AnthropicBatchClient.build_requests` | `anthropic_batch_client.py` | method | `system_blocks: list[dict]` (not a raw system string) | cycle | active |
| `StateWorkerClient` | `state_worker_client.py` | class | Manifest poll + batch register | loop | active |

## batch-poller

| Symbol | Module | Kind | Signature summary | Consumed by | Stability |
|--------|--------|------|-------------------|-------------|-----------|
| `startup_scan` / `poll_loop` / `poll_once` | `startup.py`, `loop.py` | function | Reconcile and poll Anthropic | main | active |
| `parse_pre_filter_response` | `loop.py` | function | JSON → decision + rationale + tier | poll_once | active |
| `aggregate_batch_cache_usage` | `loop.py` | function | Sum cache_read/write; log hit_ratio | poll_once | active |
| `TRACKED_BATCH_TYPES` | `models.py` | constant | pre_filter, enrichment_stage1, enrichment_stage2 | loop | active |
| `StateWorkerClient` | `clients/state_worker.py` | class | Batches + pre-filter + enrichment result POSTs | loop | active |
| `AnthropicBatchPollerClient` | `clients/anthropic.py` | class | retrieve + results | loop | active |

## content-scraper

| Symbol | Module | Kind | Signature summary | Consumed by | Stability |
|--------|--------|------|-------------------|-------------|-----------|
| `content_scrape_cycle` / `run_scheduler` | `loop.py`, `main.py` | function | Poll RELEVANCE_PASSED → fetch_content → POST | Docker CMD | active |
| `resolve_adapter` | `adapter_resolver.py` | function | SourceEnum → vendored ADAPTER_REGISTRY instance | loop | active |
| `StateWorkerClient` | `state_worker_client.py` | class | poll + post_content + post_failed | loop | active |

## enrichment-batcher

| Symbol | Module | Kind | Signature summary | Consumed by | Stability |
|--------|--------|------|-------------------|-------------|-----------|
| `stage1_cycle` / `stage2_cycle` | `stage1_loop.py`, `stage2_loop.py` | function | Poll, hash-or-abort, hold, submit keys B/C | scheduler | active |
| `ENRICHMENT_STAGE{1,2}_MIN_BATCH_SIZE` / `MAX_HOLD_MINUTES` | `config.py` | constant | Defaults 10 / 30 | hold logic | active |
| `AnthropicBatchClient` | `anthropic_batch_client.py` | class | build_requests / build_stage2_requests | stage loops | active |
| `StateWorkerClient` | `state_worker_client.py` | class | poll + register_batch | stage loops | active |

## vector-writer

| Symbol | Module | Kind | Signature summary | Consumed by | Stability |
|--------|--------|------|-------------------|-------------|-----------|
| `index_cycle` / `index_entry` | `loop.py`, `index_entry.py` | function | Poll VECTOR_WRITE_QUEUED; write three stores | Docker CMD | active |
| `LanceDbStore` / `DuckDbMirror` / `Bm25DualIndex` / `EmbeddingEncoder` | `stores/*`, `embedding.py` | class | Triple-store write | index_entry | active |
| `StateWorkerClient` | `state_worker_client.py` | class | poll + post_indexed + post_failed | loop | active |

## query-api

| Symbol | Module | Kind | Signature summary | Consumed by | Stability |
|--------|--------|------|-------------------|-------------|-----------|
| `health` | `main.py` | route | `GET /health` | compose/ops | stable |
| `get_search` | `routers/search.py` | route | `GET /search` RRF fusion | ui | active |
| `get_recent` | `routers/recent.py` | route | `GET /recent` DuckDB order | (route exists; ui unused) | active |
| `get_entry` | `routers/entries.py` | route | `GET /entries/{source_id}` SQLite RO | ui | active |
| write proxies | `routers/entries.py`, `parked.py`, `escalations.py`, `batches.py` | route | retry, permanent-fail, reading-status, parked, escalations, batches | ui | active |
| `run_search` / `rrf_fuse` | `retrieval/search.py`, `rrf.py` | function | BM25+dense orchestration | search router | active |
| `read_entry` | `sqlite_reader.py` | function | `file:?mode=ro` | entries router | active |

## ui

| Symbol | Module | Kind | Signature summary | Consumed by | Stability |
|--------|--------|------|-------------------|-------------|-----------|
| `health` / `root` | `app/main.py` | route | `GET /health`; `GET /` → 302 `/batches` | browser, compose | active |
| page routes | `app/main.py` | route | `/batches`, `/explorer`, `/search`, `/entries/{id}`, `/parked`, `/escalations` + POSTs | browser | active |
| `_query_api_request` | `app/main.py` | function | urllib client to query-api only | all pages | active |

## bishop_cli

| Symbol | Module | Kind | Signature summary | Consumed by | Stability |
|--------|--------|------|-------------------|-------------|-----------|
| `app` | `bishop_cli/main.py` | Typer app | Host CLI wrapping query-api GET search/entry | operator shell | active |
| `QUERY_API_BASE_URL` | `bishop_cli/config.py` | constant | Default `http://localhost:8080` | CLI HTTP client | active |

**Historical only:** leftover `services/*/stub_main.py` and `RootHandler` are not Docker entrypoints. **Flag:** `tests/test_service_stubs.py::T2_WORKER_STUB_SERVICES` still names `enrichment-batcher` and asserts the leftover stub loops; Docker CMD is `python -m app.main`.

**Still not public:** `personal` domain profile YAML and routing.
