Section:      module-map
Version:      1.2.0
Last updated: 2026-06-13

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
| `services/scraper.app` | Scrape loop scheduler and orchestration | `main.py`, `loop.py`, `config.py` | active |
| `services/scraper.app.adapters` | `SourceAdapter` ABC, registry, ArXiv Atom implementation | `base.py`, `registry.py`, `arxiv.py` | active |
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
| `tests` | Contract tests for constants, compose, G2/G3/M3 gates, state-worker, scraper, pre-filter, batch-poller | `test_*.py` | active |
| `scripts` | Host volume bootstrap, profile seeding, milestone verification gates | `init-volumes.*`, `seed-profiles.*`, `verify-g1.sh`, `verify-g2.sh`, `verify-g3.sh`, `verify-m2.sh`, `verify-m3.sh` | active |
| `docker-compose.yml` (repo root) | Nine-service stack; `state-worker:m1`, `scraper:m2`, `pre-filter-worker:m3`, `batch-poller:m3`, others `m0` | `docker-compose.yml` | active |
| `.env.example` | Documented host data root default for compose interpolation | `.env.example` | stable |

**Milestone notes:** Five pipeline services remain M0 stubs. `state-worker` is the contract anchor for the full §6.1 state machine. `scraper` runs `python -m app.main` with asyncio scheduler. `pre-filter-worker` and `batch-poller` run `python -m app.main` (M0 `stub_main.py` retained but unused by Dockerfiles). Post-M2 charter scope: ArXiv-only `ADAPTER_REGISTRY`. M3 scope: `professional` domain only; `personal` profile deferred.
