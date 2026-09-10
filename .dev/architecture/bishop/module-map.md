Section:      module-map
Version:      1.3.0
Last updated: 2026-09-10

| Module path | Role | Key files | Stability |
|-------------|------|-----------|-----------|
| `bishop_shared` | Shared monorepo constants, cross-service §20 enums, profile rendering, Anthropic config | `__init__.py`, `constants.py`, `enums.py`, `profile_renderer.py`, `anthropic_config.py` | stable |
| `bishop_shared.constants` | Frozen contract: service names, volume mounts, ports, SQLite path | `constants.py` | stable |
| `bishop_shared.enums` | Cross-service `SourceEnum` and `DomainEnum` literals (§20.1, §20.3) | `enums.py` | stable |
| `bishop_shared.profile_renderer` | NL profile YAML load, canonical hash (§11.3), system-prompt rendering | `profile_renderer.py` | active |
| `bishop_shared.anthropic_config` | Frozen pre-filter model string and G3 verification gate | `anthropic_config.py` | stable |
| `config/profiles` | Versioned NL profile YAML assets (host-seeded to profiles volume) | `professional_v1.0.0.yaml` | active |
| `services/state-worker` | Central state service — SQLite persistence, transition engine, §9.1 REST | `Dockerfile`, `requirements.txt`, `alembic/`, `app/` | active |
| `services/state-worker.app` | FastAPI app, lifespan (migrations → pool → sweeps) | `main.py`, `db.py`, `sweeps.py` | active |
| `services/state-worker.app.transitions` | Atomic poll-and-claim, manifest ingest, batch lifecycle, H3 writes, failure/retry paths | `transitions.py` | active |
| `services/state-worker.app.alerts` | §14.3 alert dual-write (CRITICAL log + `error_log` ALERT row) | `alerts.py` | active |
| `services/state-worker.app.routers` | HTTP route handlers for manifest, poll, entries, batches, scraper-state, escalations | `manifest.py`, `poll.py`, `entries.py`, `batches.py`, `scraper_state.py`, `escalations.py` | active |
| `services/state-worker.app.models` | Domain Pydantic models (§7 tables) and HTTP wire DTOs | `domain.py`, `http.py`, `__init__.py` | active |
| `services/state-worker.app.enums` | `ProcessingState` and remaining §20 enums (authoritative in-process copy) | `enums.py` | active |
| `services/scraper` | Discovery scraper — scheduled manifest fetch and state-worker POST | `Dockerfile`, `requirements.txt`, `app/` | active |
| `services/scraper.app` | Scrape loop scheduler; M8 adds §18.4 chunked backfill on cold start behind `BISHOP_BACKFILL_ENABLED` | `main.py`, `loop.py`, `config.py` | active |
| `services/scraper.app.adapters` | `SourceAdapter` ABC + seven-source registry (M8): ArXiv, GitHub, HuggingFace, LessWrong, OpenReview, PapersWithCode, Semantic Scholar | `base.py`, `registry.py`, `arxiv.py`, `github.py`, `huggingface.py`, `lesswrong.py`, `openreview.py`, `paperswithcode.py`, `semantic_scholar.py` | active |
| `services/scraper.app.failure_envelope` | Async retry wrapper with §6.3 HTTP classification | `failure_envelope.py`, `exceptions.py` | active |
| `services/scraper.app.state_worker_client` | httpx client for manifest batch and scraper-state routes | `state_worker_client.py` | active |
| `services/scraper.app.rate_limit` | Per-source rate limits (§15.1) and token-bucket limiter | `rate_limit.py` | active |
| `services/pre-filter-worker` | Pre-filter pipeline worker — poll DISCOVERED manifests, submit Anthropic batches | `Dockerfile`, `requirements.txt`, `app/` | active |
| `services/pre-filter-worker.app` | Async scheduler, G3 gate, profile render, Anthropic batch submit | `main.py`, `loop.py`, `config.py`, `anthropic_batch_client.py`, `state_worker_client.py` | active |
| `services/batch-poller` | Batch status poller — startup scan, Anthropic poll, timeout enforcement | `Dockerfile`, `requirements.txt`, `app/` | active |
| `services/batch-poller.app` | Poll loop, startup scan, Anthropic result fetch, state-worker lifecycle PATCH | `main.py`, `loop.py`, `startup.py`, `clients/anthropic.py`, `clients/state_worker.py` | active |
| `services/content-scraper` | Content scraper worker; M0 stub (`fetch_content` deferred to M4) | `stub_main.py`, `Dockerfile` | experimental |
| `services/enrichment-batcher` | Enrichment batch submitter; M0 stub | `stub_main.py`, `Dockerfile` | experimental |
| `services/vector-writer` | Vector/BM25 index writer; M0 stub | `stub_main.py`, `Dockerfile` | experimental |
| `services/query-api` | Read-path HTTP API; M0 HTTP stub on internal port 8000 | `stub_main.py`, `Dockerfile` | experimental |
| `services/ui` | Web UI; M0 HTTP stub listening on container port 80 | `stub_main.py`, `Dockerfile` | experimental |
| `tests` | Contract tests for constants, compose, G2/G3/M3/M7/M8 gates, state-worker, query-api, ui, scraper, pre-filter, batch-poller | `test_*.py` | active |
| `scripts` | Host volume bootstrap, profile seeding, milestone verification gates, G5/G6 quality wrappers | `init-volumes.*`, `seed-profiles.*`, `verify-g1.sh`…`verify-m8.sh`, `run-g5-quality-gate.sh`, `run-g6-prefilter-replay.sh`, `run-g6-enrichment-sampling.sh`, `replay_prefilter.py`, `build_eval_v1.py`, `apply_adjudication.py` | active |
| `docker-compose.yml` (repo root) | Nine-service stack; `state-worker:m1`, `scraper:m2`, `pre-filter-worker:m3`, `batch-poller:m5`, `content-scraper:m4`, `enrichment-batcher:m5`, `vector-writer:m6`, `query-api:m7`, `ui:m7`. M8 Naming contract calls for `scraper:m8`/`ui:m8`; deferred — see known-coupling-surfaces.md image-tag row | `docker-compose.yml` | active |
| `.env.example` | Documented host data root default for compose interpolation | `.env.example` | stable |
| `eval/prefilter_v1` | Frozen pre-filter gold set (129 adjudicated items) consumed by `scripts/replay_prefilter.py` and `tests/test_g6_prefilter_gold.py` — not the live DB | `contract.json`, `items.json`, `labels.json` | frozen |
| `.dev/quality` | G6 enrichment manual-sampling artifact (10-entry template, operator-filled) | `g6-enrichment-template.md` | active |

**Milestone notes:** M8 (Hardening and Scale, this refresh) lands the remaining six non-ArXiv source adapters behind a single `ADAPTER_REGISTRY` (T8-bis is the sole merger per plan contract), chunked backfill (§18.4) gated by `BISHOP_BACKFILL_ENABLED`/`BISHOP_BACKFILL_CHUNK_DAYS`/`BISHOP_BACKFILL_INTER_CHUNK_DELAY_SEC`, and `scripts/verify-m8.sh`. `content-scraper`, `enrichment-batcher`, `vector-writer` are no longer M0 stubs as of M4–M6 (see their own milestone image tags); `query-api` (M7) and `ui` (M7/M8) are live FastAPI/Flask-style services, not stubs — this module-map's stub language from the M0–M3 era is stale for those five services and is corrected here. `state-worker` remains the contract anchor for the full §6.1 state machine. G4 (live INDEXED corpus), G5 (embedding fixture gate), and G6 (pre-filter gold + enrichment sampling, assessed 7/10 with three documented `challenge_hooks` rejects) are the M8 entry gates for enabling backfill (G7); see `.dev/decision-logs/m8-hardening-scale/T8-backfill-enable.md`.

**Deferred in this refresh:** `public-interface-inventory.md`, `data-contract-registry.md`, `integration-seams.md`, `external-input-sources.md`, `architectural-patterns.md`, `open-questions.md`, and `architectural-decisions-divergence.md` were not re-audited for M4–M8 (content-scraper, enrichment-batcher, vector-writer, query-api, ui, and the M8 adapter/backfill/quality-gate surface described above). `module-map.md`, `known-coupling-surfaces.md`, `dependency-graph.md`, and `INDEX.md` were refreshed. Landing gate: next `project-architecture` skill pass or M9 kickoff, whichever comes first — do not treat the un-refreshed files as current for M4+ surfaces.
