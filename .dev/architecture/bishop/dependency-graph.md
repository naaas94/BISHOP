Section:      dependency-graph
Version:      1.1.0
Last updated: 2026-06-12

## Internal dependencies

| Dependent | Depends on | Nature of coupling | Risk if changed independently |
|-----------|-----------|--------------------|------------------------------|
| `docker-compose.yml` | `bishop_shared.constants` (conceptual) | Service keys, volume suffixes, ports must align with frozen constants and pytest matrices | Compose tests fail; G1/G2 gates fail; DNS/health chain breaks |
| `tests/test_compose.py` | `bishop_shared.constants`, T1 decision log matrix | `SERVICE_VOLUME_SUFFIXES` per-service mount map not encoded in constants module | Volume under/over-mount if matrix updated in one place only |
| `services/state-worker` | `bishop_shared.constants` | `STATE_WORKER_INTERNAL_PORT`, `SQLITE_DB_PATH` for bind and DB open | Port drift vs healthcheck; wrong DB file path |
| `services/scraper` | `bishop_shared.enums` | Imports shared `SourceEnum`/`DomainEnum` for wire compatibility | Enum literal drift vs state-worker if bishop_shared not updated |
| `tests/test_shared_enums.py` | `bishop_shared.enums` + `state-worker/app/enums.py` literals | Hardcoded literal sets must match both enum modules | Drift guard fails; silent wire incompatibility if test removed |
| `services/scraper` | `services/state-worker` (runtime HTTP) | `StateWorkerClient` calls manifest batch and scraper-state routes over `STATE_WORKER_URL` | Scraper cycle fails; manifests not ingested |
| `services/scraper/app/loop.py` | `services/scraper/app/adapters/registry.py` | Iterates `ADAPTER_REGISTRY` — charter limits to Arxiv only at M2 | New sources require registry + rate limit + tests |
| `services/state-worker/app/routers/*` | `services/state-worker/app/transitions.py` | Routers delegate all state mutations to transition engine | Business logic drift if routers bypass transitions |
| `services/state-worker/app/transitions.py` | `services/state-worker/app/alerts.py` | M1 alert triggers call `emit_alert` on specific failure paths | Missing alerts or duplicate error_log rows |
| `services/state-worker/app/main.py` | `app/db.py`, `app/sweeps.py` | Lifespan ordering: migrations → pool → sweep task | Race or missing sweeps if startup order changes |
| All eight dependents (runtime) | `state-worker` health | Compose `depends_on: condition: service_healthy` | Dependent containers never start |
| `scripts/verify-g2.sh`, `verify-m2.sh` | G2 pytest slice + scraper tests | Hardcoded test module lists | Gate false pass/fail if test layout changes |
| Service Dockerfiles | repo root build context | `context: .` with COPY `bishop_shared/`, `services/<name>/` | Build failure if context narrowed |
| `tests/test_state_worker_*.py` | `services/state-worker/app` on sys.path | Manual path insertion for `from app.main` | Import failures if package layout changes |

## External dependencies

| Dependency | Version pinned | Role in project | Sensitivity |
|------------|---------------|-----------------|-------------|
| Python | `>=3.12` (pyproject.toml); `3.12-slim` in Dockerfiles | Runtime for all containers and local pytest | medium |
| FastAPI | `>=0.110` (state-worker requirements.txt) | state-worker HTTP framework | medium |
| uvicorn | `>=0.27[standard]` | ASGI server for state-worker | medium |
| Pydantic | `>=2.0` | Domain and wire model validation | medium |
| Alembic | `>=1.13` | SQLite schema migrations | medium |
| SQLAlchemy | `>=2.0` | Alembic dependency | low |
| aiosqlite | `>=0.20` | Async SQLite access with WAL | medium |
| httpx | `>=0.27` (scraper requirements; dev dep) | Scraper HTTP client; ArXiv API calls | medium |
| respx | `>=0.21` (dev optional dep) | Mock httpx in scraper tests | low |
| pytest / pytest-asyncio | `>=8.0` / `>=0.23` (dev) | Contract test runner | low |
| Docker / Docker Compose | unpinned (host tooling) | Delivery and G1 gate | high |
| curl | in state-worker image + host for verify-g1 | Health probing | low |
| stdlib `http.server` | Python stdlib | query-api and ui M0 stubs | low |
| stdlib `xml.etree.ElementTree` | Python stdlib | ArXiv Atom XML parsing | low |
| export.arxiv.org | external service (unpinned) | ArXiv Atom export API | high |

**Not yet introduced (planned M3+):** LanceDB, DuckDB, BM25 libraries, LLM client SDKs, NL profile parsers — per bishop_spec_0_6.md and charter milestone registry.
