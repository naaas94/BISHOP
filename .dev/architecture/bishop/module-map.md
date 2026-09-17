Section:      module-map
Version:      1.5.0
Last updated: 2026-09-13

| Module path | Role | Key files | Stability |
|-------------|------|-----------|-----------|
| `bishop_shared` | Shared monorepo constants, enums, profiles, cache/rubric, enrichment, indexing | `__init__.py`, `constants.py`, `enums.py`, `profile_renderer.py`, `anthropic_config.py`, `prompt_cache.py`, `rubric_assets.py`, `scraper_config.py`, `indexing_config.py` | stable |
| `bishop_shared.constants` | Frozen contract: service names, volume mounts, ports, SQLite path, snapshot naming | `constants.py` | stable |
| `bishop_shared.enums` | Cross-service `SourceEnum` and `DomainEnum` literals (§20.1, §20.3) | `enums.py` | stable |
| `bishop_shared.profile_renderer` | NL profile YAML load, canonical hash, gate-split pin map, system-prompt rendering | `profile_renderer.py` | active |
| `bishop_shared.anthropic_config` | Pinned pre-filter and enrichment model strings; G3 verification gate | `anthropic_config.py` | stable |
| `bishop_shared.prompt_cache` | Sole `cache_control` emitter (`cached_system_blocks`); Haiku cache floor + TTL | `prompt_cache.py` | stable |
| `bishop_shared.rubric_assets` | Rubric markdown load + body-only hash-or-abort (keys A/B/C) | `rubric_assets.py` | active |
| `bishop_shared.enrichment_config` | Call 1 truncation token cap (`ENRICHMENT_TRUNCATION_MAX_TOKENS`) | `enrichment_config.py` | stable |
| `bishop_shared.enrichment_prompts` | Call 1 / Call 2 system-block builders (cache keys B/C) | `enrichment_prompts.py` | active |
| `bishop_shared.enrichment_parsers` | Call 1 / Call 2 JSON parse + tag OOV strip | `enrichment_parsers.py` | active |
| `bishop_shared.anthropic_batch_errors` | Classify Anthropic HTTP 400 into log event names | `anthropic_batch_errors.py` | active |
| `bishop_shared.scraper_config` | `BACKFILL_CONFIG` per-source windows; `SOURCE_SCHEDULE_INTERVAL_SEC` | `scraper_config.py` | active |
| `bishop_shared.source_config` | Optional per-source category include/exclude YAML | `source_config.py` | active |
| `bishop_shared.indexing_config` | Embedding model/dim, LanceDB/DuckDB/BM25 paths, `build_embed_text` | `indexing_config.py` | stable |
| `bishop_shared.index_policy` | Gate-2 keep/skim/drop bands from `config/index_policy.yaml` | `index_policy.py` | active |
| `bishop_shared.batch_custom_id` | Anthropic `custom_id` encode/decode (base64url / hashed) | `batch_custom_id.py` | stable |
| `config/profiles` | Versioned NL profile YAML (host-seeded). Live pins: prefilter `professional_v1.2.0_soft_launch.yaml` (ad hoc overlay); enrichment `professional_v1.0.0.yaml`. On disk unused: `v1.1.0`, `v1.1.1` | `professional_v1.0.0.yaml`, `professional_v1.1.0.yaml`, `professional_v1.1.1.yaml`, `professional_v1.2.0.yaml`, `professional_v1.2.0_soft_launch.yaml` | active |
| `config/prompts` | Image-baked rubric annexes (not a compose volume) | `prefilter_rubric_v1.md`, `call1_rubric_v1.md`, `call2_rubric_v1.md` | active |
| `config/sources` | Per-source category gate YAML (ArXiv primary-category include/exclude) | `arxiv.yaml` | active |
| `config/index_policy.yaml` | Gate-2 index policy asset baked into vector-writer image | `index_policy.yaml` | active |
| `bishop_cli` | Typer CLI over query-api read path (search/entry) | `main.py`, `config.py` | active |
| `calibration` | Frozen working-set export for human profile/prompt review — not the live DB | `MANIFEST.json`, `*.review.json` | frozen |
| `alembic` | Repo-root SQLite migrations (not under `services/state-worker/`) | `alembic.ini`, `versions/m1_001_*.py`, `m3_001_*.py`, `m8_001_pre_filter_tier.py` | stable |
| `services/state-worker` | Central state service — sole SQLite writer, transition engine, REST | `Dockerfile`, `requirements.txt`, `app/` | active |
| `services/state-worker.app` | FastAPI app, lifespan (integrity gate → migrations → pool → sweeps) | `main.py`, `db.py`, `sweeps.py` | active |
| `services/state-worker.app.transitions` | Atomic poll-and-claim, ingest, batch lifecycle, H3 writes, parked promote, failure/retry | `transitions.py` | active |
| `services/state-worker.app.alerts` | §14.3 alert dual-write (CRITICAL log + `error_log` ALERT row) | `alerts.py` | active |
| `services/state-worker.app.routers` | HTTP handlers: manifest, poll, entries, batches, scraper-state, escalations, parked | `manifest.py`, `poll.py`, `entries.py`, `batches.py`, `scraper_state.py`, `escalations.py`, `parked.py` | active |
| `services/state-worker.app.models` | Domain Pydantic models and HTTP wire DTOs | `domain.py`, `http.py`, `__init__.py` | active |
| `services/state-worker.app.enums` | `ProcessingState` (22 members incl. `RELEVANCE_PARKED`) and remaining §20 enums | `enums.py` | active |
| `services/scraper` | Discovery scraper — seven-source manifest fetch and state-worker POST | `Dockerfile`, `requirements.txt`, `app/` | active |
| `services/scraper.app` | Scrape loop; §18.4 chunked backfill behind `BISHOP_BACKFILL_*` | `main.py`, `loop.py`, `config.py` | active |
| `services/scraper.app.adapters` | `SourceAdapter` ABC + `ADAPTER_REGISTRY` (7 sources); all implement `fetch_content` | `base.py`, `registry.py`, `arxiv.py`, `github.py`, `huggingface.py`, `lesswrong.py`, `openreview.py`, `paperswithcode.py`, `semantic_scholar.py` | active |
| `services/scraper.app.failure_envelope` | Async retry wrapper with §6.3 HTTP classification | `failure_envelope.py`, `exceptions.py` | active |
| `services/scraper.app.state_worker_client` | httpx client for manifest batch and scraper-state | `state_worker_client.py` | active |
| `services/scraper.app.rate_limit` | Per-source token-bucket limits | `rate_limit.py` | active |
| `services/pre-filter-worker` | Pre-filter worker — poll DISCOVERED, submit cached Anthropic batches (key A) | `Dockerfile`, `requirements.txt`, `app/` | active |
| `services/pre-filter-worker.app` | Scheduler, G3 gate, profile+rubric hash, idle-flush hold, batch submit | `main.py`, `loop.py`, `config.py`, `anthropic_batch_client.py`, `state_worker_client.py` | active |
| `services/batch-poller` | Batch poller — startup scan, Anthropic poll, timeout, cache_usage logs | `Dockerfile`, `requirements.txt`, `app/` | active |
| `services/batch-poller.app` | Poll loop for `pre_filter`, `enrichment_stage1`, `enrichment_stage2` | `main.py`, `loop.py`, `startup.py`, `clients/anthropic.py`, `clients/state_worker.py` | active |
| `services/content-scraper` | Content worker — poll RELEVANCE_PASSED, vendored adapters, POST `/entries/content` | `app/main.py`, `loop.py`, `adapter_resolver.py`, `state_worker_client.py`, `Dockerfile` | active |
| `services/enrichment-batcher` | Enrichment submitter — Call 1 (key B) and Call 2 (key C) with idle-flush | `app/main.py`, `stage1_loop.py`, `stage2_loop.py`, `anthropic_batch_client.py`, `Dockerfile` | active |
| `services/vector-writer` | Index writer — embed + LanceDB + DuckDB mirror + dual BM25 | `app/main.py`, `loop.py`, `index_entry.py`, `stores/`, `Dockerfile` | active |
| `services/query-api` | Read-path FastAPI — RRF search, recent, entry, write proxies to state-worker | `app/main.py`, `routers/`, `stores/`, `sqlite_reader.py`, `Dockerfile` | active |
| `services/ui` | Operator UI (FastAPI + Jinja/HTMX); talks only to query-api | `app/main.py`, `Dockerfile` | active |
| `tests` | Contract tests for constants, compose, G2–G7/M3–M8, workers, prompt-cache, sqlite ops | `test_*.py` | active |
| `scripts` | Volume bootstrap, profile/rubric hashing, milestone gates, G5/G6, sqlite snapshot/restore/salvage | `init-volumes.*`, `seed-profiles.*`, `verify-g1.sh`…`verify-m8.sh`, `sqlite_snapshot.py`, `sqlite_restore.py`, `sqlite_salvage.py`, `register-snapshot-task.ps1`, `profile_hash.py`, `rubric_hash.py`, `replay_prefilter.py` | active |
| `docker-compose.yml` | Nine-service stack: `state-worker:m1`, `scraper:m8`, `pre-filter-worker:m3`, `content-scraper:m4`, `enrichment-batcher:m5`, `batch-poller:m5`, `vector-writer:m6`, `query-api:m7`, `ui:m8` | `docker-compose.yml` | active |
| `docker-compose.override.yml` | This-host overlay: remount sqlite to `${BISHOP_DATA_ROOT}/sqlite_live` | `docker-compose.override.yml` | experimental |
| `docker-compose.override.named-volume.yml` | Opt-in named volume `bishop-sqlite` (not auto-loaded) | `docker-compose.override.named-volume.yml` | experimental |
| `.env.example` | Documented host data root (Windows: explicit path; tilde not expanded) | `.env.example` | stable |
| `eval/prefilter_v0` | Original frozen gold set cited by AGENTS.md — not the live DB | `contract.json`, `items.json`, `labels.json` | frozen |
| `eval/prefilter_v1` | Current pre-filter gold (129 adjudicated items) for `replay_prefilter.py` / G6 | `contract.json`, `items.json`, `labels.json` | frozen |
| `.dev/quality` | G6 enrichment manual-sampling artifact | `g6-enrichment-template.md` | active |

**Milestone notes:** M4–M7 landed content-scraper, enrichment-batcher, vector-writer, query-api, and ui as real FastAPI/scheduler services (`python -m app.main`). Orphaned `stub_main.py` files remain on disk for seven services (not scraper/state-worker) and are not Docker entrypoints. **Flag:** `tests/test_service_stubs.py` still lists `enrichment-batcher` in `T2_WORKER_STUB_SERVICES` and asserts the leftover stub loops forever — Docker CMD is `app.main`. Architecture does not patch that test. M8 merged seven adapters into `ADAPTER_REGISTRY` and chunked backfill. T12 (2026-09-10) bumped compose+test image tags to `scraper:m8` / `ui:m8`. Prompt-caching (2026-09-12) added `bishop_shared.prompt_cache` / `rubric_assets`, cache keys A/B/C, idle-flush `MAX_HOLD_MINUTES` default 30, and batch-poller cache_usage logs. Soft-launch overlay (2026-09-11, ad hoc) parks peripheral pre-filter passes (`RELEVANCE_PARKED`) and pins prefilter to `professional_v1.2.0_soft_launch.yaml` — not intended steady state; see `.dev/decision-logs/ops/soft-launch-precision-overlay.md`.

**Alembic:** runtime migrations are repo-root `alembic/versions/` (`m1_001` → `m3_001` → `m8_001_pre_filter_tier`). There is no `services/state-worker/alembic/`.

**This refresh (2026-09-13):** completed the 2026-09-10 INDEX landing-gate re-audit of M4–M8 surfaces and folded prompt-caching + soft-launch + sqlite ops overlay. `failure-taxonomy.md` is unchanged (cause classes still pending user confirmation).
