Section:      known-coupling-surfaces
Version:      1.7.0
Last updated: 2026-09-16

```
Surface:      BISHOP_SERVICES tuple ↔ docker-compose.yml service keys ↔ services/<name>/ directory names
Shared by:    bishop_shared.constants ↔ docker-compose.yml ↔ services/* ↔ tests/test_service_stubs.py
Failure mode: Renaming a service in one location breaks compose DNS, build context paths, or stub tests
Confirmed:    yes — source: bishop_shared/constants.py, docker-compose.yml, tests
```

```
Surface:      BISHOP_VOLUME_MOUNTS host_suffix ↔ container_path pairs
Shared by:    bishop_shared.constants ↔ docker-compose.yml ↔ scripts/init-volumes.{sh,ps1} ↔ tests/test_compose.py
Failure mode: New volume suffix without init script or compose matrix update leaves G1 writability failing
Confirmed:    yes — source: T1 decision log, test_compose.py
```

```
Surface:      Per-service volume mount subset (T1 matrix)
Shared by:    .dev/decision-logs/m0-workshop/T1-repo-layout.md ↔ tests/test_compose.py::SERVICE_VOLUME_SUFFIXES ↔ docker-compose.yml
Failure mode: Matrix encoded only in tests/decision log, not in bishop_shared — drift if compose edited without test update
Confirmed:    yes — source: T1 decision log, tests/test_compose.py
```

```
Surface:      STATE_WORKER_INTERNAL_PORT (8000)
Shared by:    bishop_shared.constants ↔ state-worker uvicorn bind ↔ compose healthcheck ↔ STATE_WORKER_URL path segment ↔ query-api internal listen
Failure mode: Health gate passes internally but dependent URL points at wrong port
Confirmed:    yes — source: constants.py, docker-compose.yml, tests
```

```
Surface:      Host port mapping query-api ${QUERY_API_HOST_PORT}:8000 and ui ${UI_HOST_PORT}:80
Shared by:    bishop_shared.constants ↔ docker-compose.yml ↔ verify-g1.sh ↔ ui container listen :80
Failure mode: Host unreachable or wrong port if constants, compose, or ui listen port diverge
Confirmed:    yes — source: T1/T4 decision logs, tests
```

```
Surface:      Docker image tags bishop/<service>:<milestone>
Shared by:    docker-compose.yml image lines ↔ tests/test_compose.py::test_image_tags_use_milestone_convention
Failure mode: Tag and test dict must move together
Confirmed:    yes — current tags: state-worker m1, scraper m8, pre-filter-worker m3, batch-poller m5, content-scraper m4, enrichment-batcher m5, vector-writer m6, query-api m7, ui m8. T12 (2026-09-10) closed the T8-bis deferred scraper/ui m8 bump.
```

```
Surface:      Compose healthcheck URL /health/db
Shared by:    docker-compose.yml ↔ tests/test_compose.py::test_state_worker_has_healthcheck_and_no_host_ports ↔ services/state-worker/app/main.py
Failure mode: Dependents start against a process that cannot open SQLite if healthcheck is only GET /health
Confirmed:    yes — source: docker-compose.yml, tests/test_compose.py
```

```
Surface:      ADAPTER_REGISTRY — seven-source list, single merge point
Shared by:    services/scraper/app/adapters/registry.py ↔ scraper loop ↔ content-scraper adapter_resolver (vendored scraper_app.adapters.registry)
Failure mode: Source omitted from registry never scrapes and never fetches content; content-scraper image can drift if not rebuilt with scraper
Confirmed:    yes — source: M8 T8-bis, services/content-scraper/Dockerfile
```

```
Surface:      BISHOP_BACKFILL_ENABLED / BISHOP_BACKFILL_CHUNK_DAYS / BISHOP_BACKFILL_INTER_CHUNK_DELAY_SEC
Shared by:    services/scraper/app/config.py ↔ loop.py ↔ docker-compose.yml scraper environment ↔ bishop_shared/scraper_config.py BACKFILL_CONFIG
Failure mode: Flipping BISHOP_BACKFILL_ENABLED=1 without matching image silently falls back to unchunked fetch
Confirmed:    yes — source: M8 T8-bis, tests/test_scraper_backfill_chunking.py
```

```
Surface:      BISHOP_BACKFILL_WINDOW_OVERRIDE_DAYS ↔ BACKFILL_CONFIG.window_days
Shared by:    docker-compose.yml (compose default 60) ↔ services/scraper/app/config.py ↔ scraper cold-start
Failure mode: Override silently caps all sources to N days regardless of per-source BACKFILL_CONFIG
Confirmed:    yes — source: soft-launch overlay (compose default 60 as of 2026-09-15 after option 1), tests/test_compose.py::test_scraper_backfill_window_override_compose_default, tests/test_scraper_config.py
```

```
Surface:      Docker network name bishop-internal
Shared by:    docker-compose.yml networks section ↔ tests/test_compose.py::test_bishop_internal_network
Failure mode: Service discovery failure if network name changes inconsistently
Confirmed:    yes — source: docker-compose.yml, T4 decision log
```

```
Surface:      BISHOP_DATA_ROOT env interpolation
Shared by:    .env.example ↔ docker-compose.yml ↔ init-volumes scripts ↔ verify-g1.sh
Failure mode: Volumes bind to wrong host path; G1 writability probes wrong directory (especially on Windows)
Confirmed:    yes — source: .env.example, T1 decision log
```

```
Surface:      STATE_WORKER_URL=http://state-worker:8000
Shared by:    docker-compose.yml environment on eight dependents (ui uses QUERY_API_URL instead) ↔ worker config.py modules ↔ tests/test_compose.py
Failure mode: Workers cannot reach state-worker if env removed or URL path wrong
Confirmed:    yes — source: docker-compose.yml
```

```
Surface:      SQLITE_DB_PATH = /app/data/sqlite/bishop.db
Shared by:    bishop_shared.constants ↔ state-worker app/db.py (writer) ↔ query-api sqlite_reader mode=ro ↔ snapshot/restore scripts
Failure mode: Writer opens wrong file; readers diverge; second writer corrupts WAL
Confirmed:    yes — source: T1-schema-foundation, tests/test_sqlite_wal_concurrency.py. This-host overlay remounts the same container path onto sqlite_live via docker-compose.override.yml.
```

```
Surface:      SQLITE snapshot naming (bishop-{timestamp}.db)
Shared by:    bishop_shared.constants SQLITE_SNAPSHOT_* ↔ scripts/sqlite_snapshot.py ↔ scripts/sqlite_restore.py
Failure mode: Restore cannot find snapshots; TTL glob misses files
Confirmed:    yes — source: tests/test_sqlite_snapshot.py
```

```
Surface:      §20 SourceEnum / DomainEnum literals — dual definition
Shared by:    bishop_shared/enums.py ↔ services/state-worker/app/enums.py ↔ tests/test_shared_enums.py
Failure mode: Wire incompatibility between scraper POST bodies and state-worker validation
Confirmed:    yes — source: tests/test_shared_enums.py
```

```
Surface:      source_id canonical format "{source}:{raw_id}"
Shared by:    SourceAdapter.make_source_id ↔ adapters ↔ state-worker manifest PK ↔ bishop_shared.batch_custom_id encoding
Failure mode: Duplicate or orphan rows if format changes in adapter but not ingest path
Confirmed:    yes — source: adapters/base.py
```

```
Surface:      Anthropic batch custom_id encoding
Shared by:    bishop_shared/batch_custom_id.py ↔ three Anthropic submitters ↔ batch-poller result join (re-encodes source_ids; no longer raw source_id)
Failure mode: Results cannot be matched if encoding changes on one side only
Confirmed:    yes — source: tests around batch_custom_id; prompt-caching T1-bis
```

```
Surface:      ManifestIngestEntry.domain wire value
Shared by:    adapters (professional hardcoded) ↔ POST /manifest/batch ↔ manifest.domain
Failure mode: Downstream pre-filter routing breaks if domain assignment changes per source without contract update
Confirmed:    yes — source: M2 audit C1
```

```
Surface:      G2 pytest module list in verify-g2.sh, verify-m2.sh, and verify-m3.sh
Shared by:    scripts/verify-g2.sh ↔ verify-m2.sh ↔ verify-m3.sh ↔ tests/test_verify_g2.py
Failure mode: New contract tests not in gate script give false confidence (F-014: alerts test still outside G2 script)
Confirmed:    yes — source: scripts/verify-g2.sh
```

```
Surface:      ANTHROPIC_MODEL_PREFILTER and ANTHROPIC_MODEL_ENRICHMENT
Shared by:    bishop_shared/anthropic_config.py ↔ pre-filter-worker ↔ enrichment-batcher ↔ batch-poller ↔ verify-g3.sh
Failure mode: Single-sided bump causes HTTP 400 on one gate only
Confirmed:    yes — source: anthropic_config.py (both currently claude-haiku-4-5-20251001)
```

```
Surface:      Gate-split profile pins ↔ canonical_hash
Shared by:    bishop_shared/profile_renderer.py _PROFILE_FILENAME ↔ pre-filter-worker ↔ enrichment-batcher stage2 ↔ BatchRegisterRequest.profile_version
Failure mode: Submit blocked on hash mismatch; advancing one gate silently changing the other was the reason for the split
Confirmed:    yes — live: prefilter professional_v1.2.0_soft_launch.yaml (ad hoc overlay); enrichment professional_v1.0.0.yaml; intended prefilter professional_v1.2.0.yaml is on disk but not selected
```

```
Surface:      Anthropic prompt-cache keys A/B/C ↔ rubric paths ↔ token floor
Shared by:    bishop_shared/prompt_cache.py ↔ rubric_assets.py ↔ enrichment_prompts.py ↔ pre-filter/enrichment loops ↔ batch-poller cache_usage logs ↔ config/prompts/*_rubric_v1.md
Failure mode: Rubric/profile edit without hash recompute blocks submit; prefix below 4096 (test margin 4506) kills cache economics
Confirmed:    yes — source: tests/test_prompt_cache.py, tests/test_prompt_cache_token_floor.py, tests/test_rubric_assets.py
```

```
Surface:      Idle-flush MIN_BATCH_SIZE / MAX_HOLD_MINUTES
Shared by:    pre-filter-worker/app/config.py ↔ enrichment-batcher/app/config.py ↔ in-process pending lists (not a DB shape) ↔ tests/test_m5_integration.py
Failure mode: Restart drops held items; defaults 30 minutes (T11 retune from 120). M5 e2e still seeds 5/1 entries against stage-1 min 10 → no in-flight batch (OPEN-021)
Confirmed:    yes — source: prompt-caching T9-bis / T11; 2026-09-14 isolated M5 fails
```

```
Surface:      Batch type strings pre_filter | enrichment_stage1 | enrichment_stage2
Shared by:    BatchTypeEnum ↔ batch-poller TRACKED_BATCH_TYPES ↔ enrichment-batcher registration
Failure mode: Wrong type routed to wrong poller handler
Confirmed:    yes — source: tests/test_batch_poller_enrichment.py
```

```
Surface:      Soft-launch RELEVANCE_PARKED overlay
Shared by:    ProcessingState ↔ transitions.py peripheral parking ↔ GET/POST /parked ↔ query-api/ui proxies
Failure mode: Revert overlay without restoring pin/state leaves manifests stuck parked or wrong tier routing
Confirmed:    yes — source: .dev/decision-logs/ops/soft-launch-precision-overlay.md
```

```
Surface:      Index store path constants shared writer/reader
Shared by:    bishop_shared/indexing_config.py ↔ vector-writer stores ↔ query-api stores
Failure mode: Path mismatch → empty search channels or write/read different files
Confirmed:    yes — source: tests/test_indexing_config.py, tests/test_m6_integration.py, tests/test_m7_integration.py
```

```
Surface:      SQLite integrity gate at state-worker startup
Shared by:    services/state-worker/app/db.py enforce_integrity ↔ /health/db ↔ scripts/sqlite_snapshot.py integrity_ok
Failure mode: Corrupt DB blocks entire stack (by design)
Confirmed:    yes — source: tests/test_state_worker_integrity_gate.py
```

```
Surface:      Host profiles volume mount path
Shared by:    docker-compose.yml ${BISHOP_DATA_ROOT}/profiles ↔ PROFILES_CONTAINER_DIR ↔ seed-profiles scripts
Failure mode: pre-filter-worker cannot load profile if mount path or seed script diverges from renderer constant
Confirmed:    yes — source: docker-compose.yml, profile_renderer.py
```

```
Surface:      Rubric prompts are image-baked, not a compose volume
Shared by:    Dockerfiles COPY config/prompts → /app/config/prompts ↔ bishop_shared.rubric_assets.PROMPTS_CONTAINER_DIR
Failure mode: Editing host markdown without rebuild leaves containers on stale rubrics
Confirmed:    yes — source: prompt-caching T1-bis, Dockerfiles
```

```
Surface:      state-worker start_period 30s (M1)
Shared by:    docker-compose.yml healthcheck ↔ tests/test_compose.py
Failure mode: Dependents start before migrations complete if start_period shortened without test update
Confirmed:    yes — source: M1 T5/T6, test_compose.py
```

```
Surface:      Optional Docker named volume bishop-sqlite (proposal — cutover NOT executed)
Shared by:    docker-compose.override.named-volume.yml ↔ scripts/sqlite_snapshot.py --volume ↔ tests/test_sqlite_named_volume.py
Failure mode: Host bind mount vs named volume tooling divergence
Confirmed:    yes as proposal only — standing docker-compose.yml still bind-mounts ${BISHOP_DATA_ROOT}/sqlite
```

```
Surface:      tests/test_service_stubs.py T2_WORKER_STUB_SERVICES vs Docker CMD
Shared by:    tests/test_service_stubs.py ↔ services/enrichment-batcher/stub_main.py ↔ services/enrichment-batcher/Dockerfile
Failure mode: Test still treats enrichment-batcher as an M0 stub loop; Docker runs python -m app.main. Passing stub tests do not mean the leftover stub is the runtime entrypoint
Confirmed:    yes — source: tests/test_service_stubs.py L13–15 vs Dockerfile CMD
```

```
Surface:      Shared top-level `app` package across nine services
Shared by:    services/*/app ↔ pytest sys.path inserts ↔ sys.modules['app']
Failure mode: Monolithic `pytest tests/` binds the wrong service; query-api (has app/__init__.py) wins over state-worker/vector-writer (namespace packages, no __init__.py). Leaky tests (query-api entry + stats) leave query-api on path
Confirmed:    yes — OPEN-002; 2026-09-14 isolation: entry+contract dies, search/UI+contract pass
```

```
Surface:      docker-compose.override.yml auto-load vs named-volume overlay filename
Shared by:    docker-compose.override.yml (tracked sqlite_live remount) ↔ docker-compose.override.named-volume.yml (opt-in, not auto-loaded) ↔ tests/test_sqlite_named_volume.py::test_default_compose_discovery_ignores_named_volume_override
Failure mode: Any committed docker-compose.override.yml makes `docker compose config` ≠ `-f docker-compose.yml` (OPEN-022). The named-volume filename is safe from auto-load
Confirmed:    yes — 2026-09-14 isolated fail; incident 2026-09-12 FU-002
```

```
Surface:      Untrusted ingest text → Anthropic user turn → embeddings
Shared by:    scraper adapters (title/abstract/content_raw) ↔ pre-filter-worker user_message ↔ enrichment Call 1 user blob ↔ Call 1 summary → Call 2 user blob ↔ vector-writer encode(title, summary, challenge_hooks)
Failure mode: A public title/README can steer Gate 1 pass/park, Call 2 score, and retrieval neighbors without any tool-use or RCE. Untrusted text is not in the cached system prefix.
Confirmed:    yes — 2026-09-15 seed map; OPEN-023; .dev/decision-logs/ops/ingest-content-risk-seed.md
```

```
Surface:      Stored manifest/entries.url rendered as UI href
Shared by:    adapter-supplied url (Atom link, GitHub html_url, LessWrong pageUrl, …) ↔ SQLite url column ↔ services/ui templates entry_detail.html and parked.html href="{{ …url }}"
Failure mode: No scheme allowlist. javascript: or data: would execute on click if an upstream API ever returned it. Adapters do not fetch this url for content.
Confirmed:    yes — 2026-09-15 seed map I-6
```

```
Surface:      content_raw unbounded from wire to SQLite
Shared by:    ContentPostRequest.content_raw (no max_length) ↔ entries.content_raw sa.Text() ↔ Call 1 truncate only at ENRICHMENT_TRUNCATION_MAX_TOKENS
Failure mode: A huge body bloated SQLite/worker memory before Call 1 truncation. Truncation does not cap ingest.
Confirmed:    yes — 2026-09-15 seed map I-5
```
