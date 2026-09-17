Section:      data-contract-registry
Version:      1.3.0
Last updated: 2026-09-13

## Platform

```
Contract:       HealthResponse
Module:         services/state-worker/app/models/__init__.py
Serialization:  Pydantic model
Version:        unversioned — tracked by git blame
Purpose:        Liveness JSON for GET /health
Fields:
  - status: Literal["ok"]
Validators:     status restricted to "ok"
Consumers:      main.py, verify scripts
Last changed:   2026-06-10
```

```
Contract:       DbHealthResponse
Module:         services/state-worker/app/models/__init__.py
Serialization:  Pydantic model
Version:        unversioned — tracked by git blame
Purpose:        Readiness: SQLite I/O + alembic_version
Fields:
  - status: Literal["ok", "error"]
  - detail: str | None — revision on ok; exception on error (HTTP 503)
Validators:     empty alembic_version → error
Consumers:      GET /health/db; compose healthcheck; all depends_on: service_healthy
Last changed:   2026-09-11
```

```
Contract:       VolumeMount / BISHOP_VOLUME_MOUNTS
Module:         bishop_shared/constants.py
Serialization:  frozen dataclass + compose bind interpolation
Version:        unversioned — tracked by git blame
Purpose:        Host suffix ↔ container path
Fields:
  - sqlite, lancedb, duckdb, bm25, profiles, logs
  - prompts are NOT a volume (image-baked /app/config/prompts)
Validators:     tests/test_compose.py volume matrix
Consumers:      compose, indexing_config, SQLITE_DB_PATH
Last changed:   2026-06-10
```

```
Contract:       SQLITE_DB_PATH
Module:         bishop_shared/constants.py
Serialization:  constant string
Version:        unversioned — tracked by git blame
Purpose:        Container path for live bishop.db
Fields:
  - value: /app/data/sqlite/bishop.db
Validators:     tests/test_constants.py
Consumers:      state-worker db.py (writer); query-api sqlite_reader (mode=ro); snapshot/restore
Last changed:   2026-09-11
```

```
Contract:       STATE_WORKER_URL
Module:         docker-compose.yml (environment on dependents except ui)
Serialization:  plain string env var
Version:        unversioned — tracked by git blame
Purpose:        Internal base URL for state-worker HTTP clients
Fields:
  - value: http://state-worker:8000
Validators:     compose tests
Consumers:      scraper, pre-filter-worker, content-scraper, enrichment-batcher, batch-poller, vector-writer, query-api proxies
Last changed:   2026-06-12
```

## SQLite schema

```
Contract:       Alembic revision chain
Module:         alembic/versions/ (alembic.ini script_location = alembic)
Serialization:  Alembic revision files
Version:        head = m8_001_pre_filter_tier
Purpose:        Authoritative SQLite DDL; state-worker upgrades at startup
Fields:
  - m1_001_initial_schema: manifest, entries, batches, error_log, oov_tags_log, scraper_state
  - m3_001_batch_source_ids: batches.source_ids TEXT NOT NULL default '[]'
  - m8_001_pre_filter_tier: nullable TEXT pre_filter_tier on manifest and entries
Validators:     alembic_version.version_num; /health/db returns that string
Consumers:      services/state-worker/app/db.py::run_migrations
Last changed:   2026-09-10
```

```
Contract:       manifest (table)
Module:         alembic/versions/m1_001_initial_schema.py + m8_001_pre_filter_tier.py
Serialization:  SQLite table via Alembic
Version:        unversioned — tracked by git blame
Purpose:        Discovery records and pre-filter state (including parked inbox)
Fields:
  - source_id TEXT PK; source, url, title, abstract, published_at, discovered_at, domain
  - profile_version, pre_filter_batch_id, relevance_decision, pre_filter_rationale
  - pre_filter_tier: TEXT NULL — "core" | "peripheral" | NULL
  - processing_state, retry_count, next_retry_at
Validators:     relevance_decision ∈ {0, 1, NULL}; processing_state ∈ ProcessingState
Consumers:      transitions.py, routers, query-api (indirect)
Last changed:   2026-09-10
```

```
Contract:       entries (table)
Module:         alembic/versions/m1_001_initial_schema.py + m8_001_pre_filter_tier.py
Serialization:  SQLite table via Alembic
Version:        unversioned — tracked by git blame
Purpose:        Full-content rows after scrape through enrichment and index
Fields:
  - id TEXT PK; source_id UNIQUE; source, url, title, content_raw
  - published_at, ingested_at, domain, profile_version, pre_filter provenance + pre_filter_tier
  - Call 1: summary, concepts, tags, entry_type, challenge_hooks, enrichment_stage1_batch_id
  - Call 2: relevance_score, relevance_reason, value_rationale, enrichment_stage2_batch_id
  - references, cited_by JSON-text; reading_status default unread; flagged_for_review
  - processing_state; no retry columns; no cache_usage columns
Validators:     JSON list encode/decode; ProcessingState in transitions.py
Consumers:      transitions, poll router, query-api sqlite_reader, vector-writer poll JSON
Last changed:   2026-09-10
```

```
Contract:       batches, error_log, oov_tags_log, scraper_state (tables)
Module:         alembic/versions/m1_001_initial_schema.py + m3_001_batch_source_ids.py
Serialization:  SQLite tables via Alembic
Version:        unversioned — tracked by git blame
Purpose:        Batch lifecycle, failure log, OOV tags, scraper checkpoint
Fields:         per domain models; batches.source_ids JSON list (m3)
Validators:     enum columns match services/state-worker/app/enums.py
Consumers:      routers, transitions.py, alerts.py
Last changed:   2026-06-13
```

```
Contract:       ProcessingState
Module:         services/state-worker/app/enums.py
Serialization:  str Enum (22 members)
Version:        unversioned — tracked by git blame
Purpose:        Authoritative processing state machine
Fields:
  - DISCOVERED, RELEVANCE_QUEUED, RELEVANCE_PASSED, RELEVANCE_REJECTED, RELEVANCE_PARKED
  - SCRAPE_QUEUED, SCRAPED
  - ENRICHMENT_STAGE1_QUEUED, SUBMITTED, COMPLETE; ENRICHMENT_STAGE2_QUEUED, CLAIMED, SUBMITTED, COMPLETE
  - VECTOR_WRITE_QUEUED, INDEXED
  - SCRAPE_FAILED, ENRICHMENT_STAGE1_FAILED, ENRICHMENT_STAGE2_FAILED, VECTOR_WRITE_FAILED
  - ESCALATION_FLAGGED, PERMANENTLY_FAILED
Validators:     transition guards in transitions.py
  - Peripheral pass (decision=1 and pre_filter_tier=="peripheral") → RELEVANCE_PARKED (manifest-only)
  - Promote: RELEVANCE_PARKED → RELEVANCE_PASSED
Consumers:      all state-worker routers/transitions; worker poll clients
Last changed:   2026-09-11
```

```
Contract:       ManifestEntry / Entry / BatchRecord
Module:         services/state-worker/app/models/domain.py
Serialization:  Pydantic model
Version:        unversioned — tracked by git blame
Purpose:        In-process table rows including JSON-list fields and pre_filter_tier
Fields:         mirror SQLite columns; Entry.reading_status ReadingStatusEnum; flagged_for_review bool
Validators:     to_db_row / from_db_row; encode_json_list_fields
Consumers:      transitions, routers
Last changed:   2026-09-10
```

## state-worker HTTP wire

```
Contract:       ManifestBatchRequest / ManifestBatchResponse
Module:         services/state-worker/app/models/http.py
Serialization:  Pydantic model
Version:        unversioned — tracked by git blame
Purpose:        POST /manifest/batch
Fields:
  - request.entries[]: source_id, source, url, title, abstract, published_at, domain
  - response.inserted, skipped
Validators:     idempotent skip on duplicate source_id
Consumers:      scraper StateWorkerClient
Last changed:   2026-06-11
```

```
Contract:       PollResponse
Module:         services/state-worker/app/models/http.py
Serialization:  Pydantic model
Version:        unversioned — tracked by git blame
Purpose:        GET /manifest/poll and GET /entries/poll
Fields:
  - entries: list[dict]; content_raw omitted at VECTOR_WRITE_QUEUED
  - claimed_count: int; transitioned_to: str | None
Validators:     state query must be poll-eligible
Consumers:      pre-filter-worker, content-scraper, enrichment-batcher, vector-writer
Last changed:   2026-06-11
```

```
Contract:       ContentPostRequest / ContentPostResponse
Module:         services/state-worker/app/models/http.py
Serialization:  Pydantic model
Version:        unversioned — tracked by git blame
Purpose:        POST /entries/content — persist fetch_content str
Fields:
  - request.source_id, content_raw
  - response.entry_id, processing_state
Validators:     409 provenance_incomplete / invalid_transition
Consumers:      content-scraper
Last changed:   2026-09-13
```

```
Contract:       PreFilterResultsRequest / PreFilterResultsResponse
Module:         services/state-worker/app/models/http.py
Serialization:  Pydantic model
Version:        unversioned — tracked by git blame
Purpose:        POST /manifest/pre-filter-results
Fields:
  - request.batch_id, profile_version
  - request.entries[]: source_id, decision (0|1), pre_filter_rationale, pre_filter_tier
  - response.updated, passed, rejected, parked (default 0)
Validators:     decision ∈ {0,1}; peripheral pass → PARKED
Consumers:      batch-poller
Last changed:   2026-09-11
```

```
Contract:       EnrichmentStage1ResultsRequest / EnrichmentStage2ResultsRequest
Module:         services/state-worker/app/models/http.py
Serialization:  Pydantic model
Version:        unversioned — tracked by git blame
Purpose:        POST enrichment results (204 empty body)
Fields:
  - Stage1 entries[]: source_id, success, summary, concepts, tags, entry_type, challenge_hooks, oov_tags_stripped, error_message
  - Stage2 entries[]: source_id, success, relevance_score, relevance_reason, value_rationale, error_message
Validators:     success false recorded as failure path; score 0.0–1.0 when success
Consumers:      batch-poller
Last changed:   2026-09-13
```

```
Contract:       IndexedPostRequest / FailedPostRequest / RetryPost* / PermanentFailPost* / ReadingStatusPatch*
Module:         services/state-worker/app/models/http.py
Serialization:  Pydantic model
Version:        unversioned — tracked by git blame
Purpose:        Index ack, failure envelope, ops retry/fail/reading-status
Fields:         source_id plus type-specific fields (see models/http.py)
Validators:     404 not_found; 409 invalid_transition / terminal_state
Consumers:      vector-writer, workers, query-api proxies, UI
Last changed:   2026-09-13
```

```
Contract:       BatchRegisterRequest / BatchPatchRequest / BatchDetailResponse / BatchTimeoutResponse
Module:         services/state-worker/app/models/http.py
Serialization:  Pydantic model
Version:        unversioned — tracked by git blame
Purpose:        POST/PATCH /batches* ; timeout
Fields:
  - register: batch_id, batch_type (pre_filter|enrichment_stage1|enrichment_stage2), domain, profile_version, profile_render_hash, source_ids, entry_count
  - patch: status, passed_count?, failed_count?, completed_at?, external_batch_id?
Validators:     duplicate batch_id → 409; illegal status → 409
Consumers:      pre-filter-worker, enrichment-batcher, batch-poller, query-api
Last changed:   2026-06-13
```

```
Contract:       ParkedListResponse / PromoteParkedRequest / PromoteParkedResponse / EscalationsResponse
Module:         services/state-worker/app/models/http.py
Serialization:  Pydantic model
Version:        unversioned — tracked by git blame
Purpose:        GET /parked, POST /parked/promote, GET /escalations
Fields:
  - ParkedEntryWire: source_id, title, abstract, source, url, pre_filter_rationale, pre_filter_tier, discovered_at, processing_state
  - Escalation entries include nested error_log (failure row + ALERT sibling)
Validators:     promote 409 if not RELEVANCE_PARKED
Consumers:      query-api proxies; UI
Last changed:   2026-09-11
```

```
Contract:       ScraperStateResponse / ScraperStateUpdateRequest
Module:         services/state-worker/app/models/http.py
Serialization:  Pydantic model
Version:        unversioned — tracked by git blame
Purpose:        GET/POST /scraper-state/{source}
Fields:
  - response: source, last_successful_run_at, updated_at
  - update: timestamp ISO 8601
Validators:     POST 204
Consumers:      scraper StateWorkerClient
Last changed:   2026-06-11
```

## scraper / content

```
Contract:       ManifestIngestEntry / ManifestBatchResult
Module:         services/scraper/app/models.py
Serialization:  Pydantic model
Version:        unversioned — tracked by git blame
Purpose:        Scraper-side ingest DTO
Fields:
  - ManifestIngestEntry: source_id, source, url, title, abstract, published_at, domain
  - ManifestBatchResult: inserted, skipped
Validators:     source_id via make_source_id "{source}:{raw_id}"
Consumers:      adapters, StateWorkerClient
Last changed:   2026-06-12
```

```
Contract:       RateLimit
Module:         services/scraper/app/rate_limit.py
Serialization:  dataclass
Version:        unversioned — tracked by git blame
Purpose:        Per-source token bucket
Fields:
  - calls, period_seconds, backoff ("exponential"|"linear"), max_retries, jitter
Validators:     SOURCE_RATE_LIMITS keyed by SourceEnum.value
Consumers:      adapters, failure_envelope
Last changed:   2026-09-10
```

```
Contract:       fetch_content
Module:         services/scraper/app/adapters/base.py (impls in adapters/*.py)
Serialization:  plain str (not JSON)
Version:        unversioned — tracked by git blame
Purpose:        Full-body fetch after RELEVANCE_PASSED claimed to SCRAPE_QUEUED
Fields:
  - return: UTF-8 text; HTTP body is ContentPostRequest {source_id, content_raw}
Validators:     adapter exceptions mapped to FailedPostRequest
Consumers:      content-scraper loop
Last changed:   2026-09-13
```

```
Contract:       ArXiv Atom feed response
Module:         (external) export.arxiv.org
Serialization:  Atom XML
Version:        unversioned — external API
Purpose:        Manifest discovery input for ArxivAdapter
Fields:
  - atom:entry id, title, summary, published, link
Validators:     entries without id/title silently skipped
Consumers:      parse_atom_feed
Last changed:   2026-06-12
```

## profiles, rubrics, prompt-cache

```
Contract:       ProfileDocument / Profile pin map
Module:         bishop_shared/profile_renderer.py
Serialization:  Pydantic from YAML (extra=ignore)
Version:        unversioned — tracked by git blame
Purpose:        NL profile for gate-1 and Call 2
Fields:
  - version, domain, canonical_hash, context, principles, anchors[], exclusions
  - peripheral_classes, peripheral_disposition ("pass"|"park"), calibration_examples[], output
  - _PROFILE_FILENAME: prefilter/professional → professional_v1.2.0_soft_launch.yaml (AD HOC); enrichment/professional → professional_v1.0.0.yaml
Validators:     compute_profile_hash must match canonical_hash or submit aborts
Consumers:      pre-filter-worker, enrichment-batcher stage2
Last changed:   2026-09-11
```

```
Contract:       professional_v1.2.0_soft_launch.yaml
Module:         config/profiles/professional_v1.2.0_soft_launch.yaml
Serialization:  YAML
Version:        1.2.0-soft-launch
Purpose:        Live pre-filter pin — precision overlay; peripheral parked
Fields:
  - canonical_hash: 64ec84d7e8f41b0b6ea398ec9c9dd2007e1b149cd42c4e6ced2873d612150091
  - peripheral_disposition: park
Validators:     SHA-256 of JSON-canonical dict excluding canonical_hash
Consumers:      pre-filter-worker
Last changed:   2026-09-11
```

```
Contract:       professional_v1.2.0.yaml
Module:         config/profiles/professional_v1.2.0.yaml
Serialization:  YAML
Version:        1.2.0
Purpose:        Intended calibrated pre-filter pin (not currently selected)
Fields:
  - canonical_hash: ac6355c92320a6a890d87f22b2da29b05997e783c3fbd6389e32cfcf9f3a1484
Validators:     hash as above
Consumers:      none at runtime until pin map reverts
Last changed:   2026-09-10
```

```
Contract:       professional_v1.0.0.yaml
Module:         config/profiles/professional_v1.0.0.yaml
Serialization:  YAML
Version:        1.0.0
Purpose:        Live enrichment Call 2 profile (include_output=False)
Fields:
  - canonical_hash: 80f5f9abdc3b80c8e43c0fb6f40ac057c97130aa67ecb7852b48d49a26bb687d
Validators:     hash as above
Consumers:      enrichment-batcher stage2
Last changed:   2026-06-13
```

```
Contract:       cache_control breakpoint / cache keys A B C
Module:         bishop_shared/prompt_cache.py; pre-filter loop; bishop_shared/enrichment_prompts.py
Serialization:  Anthropic system content-block list
Version:        unversioned — tracked by git blame
Purpose:        Cached prefixes for the three Anthropic gates
Fields:
  - HAIKU_CACHE_MIN_TOKENS 4096; CACHE_TTL "1h"; last block only has cache_control ephemeral
  - Key A: profile render (soft_launch, include_output=True) + prefilter_rubric body
  - Key B: Call 1 schema/taxonomy + call1_rubric body
  - Key C: profile render (v1.0.0, include_output=False) + call2_rubric + Call 2 schema
Validators:     tests/test_prompt_cache.py; token-floor ≥ 4506 cl100k_base (test-only)
Consumers:      three Anthropic submitters
Last changed:   2026-09-13
```

```
Contract:       RubricDocument / rubric assets
Module:         bishop_shared/rubric_assets.py; config/prompts/*_rubric_v1.md
Serialization:  Markdown with front matter; hashed body only (LF-normalized)
Version:        1.0.0 per file
Purpose:        Annex text for cache keys A/B/C; image-baked
Fields:
  - front matter: rubric_id, version, canonical_hash
  - prefilter_rubric_v1.md hash 821c1f8d94c9225c3e3d1ed79bd132cc34417a57dfa3bdf1dad7727dba1f39b9
  - call1_rubric_v1.md hash f3cf74ac069d066c378f1a0937ce3c6da230455ce29660dc8e630803859819cc
  - call2_rubric_v1.md hash d1e7b871e1793b277a08dbe929390a45960bf665c7a44e60e1442229325d58a5
Validators:     verify_rubric_hash returns None on mismatch → abort submit
Consumers:      three gates
Last changed:   2026-09-13
```

```
Contract:       Anthropic batch custom_id
Module:         bishop_shared/batch_custom_id.py
Serialization:  API string, ^[a-zA-Z0-9_-]{1,64}$
Version:        unversioned — tracked by git blame
Purpose:        Join batch results to batches.source_ids
Fields:
  - short source_id: URL-safe base64 without padding
  - long (>48 UTF-8 bytes): "h" + base64url(sha256) — not reversible; poller re-encodes
Validators:     pattern + 64-char cap
Consumers:      all three submitters; batch-poller
Last changed:   2026-09-13
```

```
Contract:       Idle hold / MIN_BATCH_SIZE / MAX_HOLD_MINUTES
Module:         services/pre-filter-worker/app/config.py; services/enrichment-batcher/app/config.py
Serialization:  env-backed ints (in-process; not a DB shape)
Version:        unversioned — tracked by git blame
Purpose:        Do not submit undersized batches until a deadline
Fields:
  - PREFILTER_MIN_BATCH_SIZE 25; PREFILTER_MAX_HOLD_MINUTES 30; PREFILTER_BATCH_SIZE 50
  - ENRICHMENT_STAGE1/2_MIN_BATCH_SIZE 10; MAX_HOLD_MINUTES 30; BATCH_SIZE 50
  - submit if held_count ≥ MIN OR hold elapsed ≥ MAX; restart drops pending
Validators:     BISHOP_* env overrides
Consumers:      prefilter/stage loops
Last changed:   2026-09-13
```

```
Contract:       Anthropic usage → cache_usage log
Module:         services/batch-poller/app/loop.py
Serialization:  API usage object → log extra dict (not SQLite)
Version:        unversioned — tracked by git blame
Purpose:        Observe cache hits after batch completion
Fields:
  - cache_creation_input_tokens, cache_read_input_tokens, input_tokens, output_tokens, cache_hit_ratio
Validators:     warning if both cache counters are 0
Consumers:      operators / G1
Last changed:   2026-09-13
```

```
Contract:       Pre-filter / Call 1 / Call 2 model JSON
Module:         batch-poller parse_pre_filter_response; bishop_shared/enrichment_parsers.py
Serialization:  JSON object in model text
Version:        unversioned — tracked by git blame
Purpose:        Gate-1 decision; extraction; relevance score
Fields:
  - pre-filter: decision 0|1, rationale, optional tier core|peripheral
  - Call 1: summary, concepts, tags, entry_type, challenge_hooks
  - Call 2: relevance_score 0–1, relevance_reason, value_rationale
Validators:     malformed JSON → parse_failed / decision 0
Consumers:      state-worker result POSTs
Last changed:   2026-09-13
```

```
Contract:       ANTHROPIC_MODEL_PREFILTER / ANTHROPIC_MODEL_ENRICHMENT
Module:         bishop_shared/anthropic_config.py
Serialization:  constant string
Version:        unversioned — tracked by git blame
Purpose:        Pinned Haiku snapshot
Fields:
  - both: claude-haiku-4-5-20251001
Validators:     verify_model_string; HTTP 400 → fatal
Consumers:      all three submitters, G3
Last changed:   2026-06-13
```

## index + query

```
Contract:       LanceRow / LanceDB entries table
Module:         services/vector-writer/app/stores/lancedb_store.py
Serialization:  PyArrow schema in LanceDB table "entries"
Version:        unversioned — tracked by git blame
Purpose:        Dense vectors for cosine search
Fields:
  - source_id, vector list<float32>[384], title, summary, domain, tags, challenge_hooks, relevance_score
Validators:     vector length == EMBEDDING_DIM 384; skip duplicate source_id
Consumers:      query-api lancedb_reader
Last changed:   2026-09-13
```

```
Contract:       DuckDB entries_mirror
Module:         services/vector-writer/app/stores/duckdb_mirror.py
Serialization:  DuckDB table at /app/data/duckdb/bishop.duckdb
Version:        unversioned — tracked by git blame
Purpose:        Metadata filter + recent + search-hit hydration
Fields:
  - source_id PK, source, url, title, published_at, ingested_at, domain, entry_type
  - relevance_score, reading_status, summary; tags/concepts/challenge_hooks JSON
Validators:     upsert; lock retry
Consumers:      query-api DuckDbReader
Last changed:   2026-09-13
```

```
Contract:       BM25 index.pkl payload
Module:         services/vector-writer/app/stores/bm25_store.py
Serialization:  pickle dict {corpus, source_ids}
Version:        unversioned — tracked by git blame
Purpose:        Per-domain dual BM25 (main + challenge_hooks)
Fields:
  - paths /app/data/bm25/{domain}/main/index.pkl and .../challenge_hooks/index.pkl
  - lock file .bm25_write.lock
Validators:     reader requires keys exactly {corpus, source_ids}
Consumers:      query-api bm25_reader
Last changed:   2026-09-13
```

```
Contract:       IndexPolicy
Module:         bishop_shared/index_policy.py; config/index_policy.yaml
Serialization:  Pydantic from YAML (image-baked)
Version:        0.1.0 (file)
Purpose:        Gate 2 keep/skim/drop on enrichment relevance_score
Fields:
  - keep_min 0.40, skim_min 0.25, enforce false (log only, still index)
Validators:     0–1 bounds; skim_min ≤ keep_min
Consumers:      vector-writer index_entry
Last changed:   2026-09-13
```

```
Contract:       SearchRequest / SearchResponse / RecentResponse / EntryResponse
Module:         services/query-api/app/models.py
Serialization:  Pydantic; GET query params
Version:        unversioned — tracked by git blame
Purpose:        Read-path HTTP
Fields:
  - search: q min_length 1; filters domain/source/tags/min_relevance/days/type/reading_status; hits cap 20; RRF_K=60
  - recent: source?, days default 7; DuckDB lock → empty list not 5xx
  - entry: mirrors Entry including content_raw; 404 not_found
Validators:     400 invalid_query
Consumers:      UI /search, /explorer, /entries/{id}
Last changed:   2026-09-13
```

```
Contract:       query-api write proxies
Module:         services/query-api/app/routers/*
Serialization:  JSON pass-through to state-worker
Version:        unversioned — tracked by git blame
Purpose:        UI never talks to state-worker
Fields:
  - POST retry / permanent-fail; PATCH reading-status; GET/POST parked; GET escalations; GET /batches*
Validators:     502 upstream_error
Consumers:      services/ui/app/main.py
Last changed:   2026-09-13
```

## ops overlays

```
Contract:       Snapshot file
Module:         bishop_shared/constants.py; scripts/sqlite_snapshot.py
Serialization:  standalone SQLite file (journal_mode=DELETE after backup)
Version:        unversioned — tracked by git blame
Purpose:        Integrity-gated online backup; live name never rotates
Fields:
  - dir /app/data/sqlite/snapshots; name bishop-{YYYYMMDD-HHMMSS}.db; TTL 24h; interval 30 min
Validators:     source and dest integrity_check; fail deletes temp not live
Consumers:      scripts/sqlite_restore.py
Last changed:   2026-09-13
```

```
Contract:       Named volume overlay bishop-sqlite
Module:         docker-compose.override.named-volume.yml
Serialization:  Docker named volume
Version:        unversioned — tracked by git blame
Purpose:        Opt-in sqlite backing that is not a Windows bind mount
Fields:
  - volume bishop-sqlite still at /app/data/sqlite; not auto-loaded
Validators:     tests/test_sqlite_named_volume.py
Consumers:      opt-in compose; snapshot --volume
Last changed:   2026-09-13
```

```
Contract:       Live compose sqlite overlay (this host)
Module:         docker-compose.override.yml
Serialization:  Compose bind remount
Version:        unversioned — tracked by git blame
Purpose:        Live file under sqlite_live after leaked WAL handles
Fields:
  - state-worker + query-api: ${BISHOP_DATA_ROOT}/sqlite_live:/app/data/sqlite
Validators:     snapshot resolve_db_path prefers sqlite_live/bishop.db if present
Consumers:      current `docker compose up` on this host
Last changed:   2026-09-11
```

**Still deferred:** `personal` domain profile YAML. Cache usage is logs-only (not a SQLite column). `reading_status` has been in m1 since initial schema.
