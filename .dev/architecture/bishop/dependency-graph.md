Section:      dependency-graph
Version:      1.5.0
Last updated: 2026-09-13

## Internal dependencies

| Dependent | Depends on | Nature of coupling | Risk if changed independently |
|-----------|-----------|--------------------|------------------------------|
| `docker-compose.yml` | `bishop_shared.constants` (conceptual) | Service keys, volume suffixes, ports must align with frozen constants and pytest matrices | Compose tests fail; G1/G2/M3 gates fail; DNS/health chain breaks |
| `tests/test_compose.py` | `bishop_shared.constants`, T1 decision log matrix | `SERVICE_VOLUME_SUFFIXES` per-service mount map not encoded in constants module | Volume under/over-mount if matrix updated in one place only |
| `services/state-worker` | `bishop_shared.constants` | `STATE_WORKER_INTERNAL_PORT`, `SQLITE_DB_PATH`, snapshot constants, `SQLITE_BUSY_TIMEOUT_MS` | Port drift vs healthcheck; wrong DB file path |
| `services/scraper` | `bishop_shared.enums`, `bishop_shared.scraper_config` | Shared source/domain enums; BACKFILL_CONFIG window_days | Enum drift vs state-worker; backfill window silently wrong |
| `services/pre-filter-worker` | `bishop_shared.profile_renderer`, `anthropic_config`, `prompt_cache`, `rubric_assets`, `batch_custom_id` | Profile+rubric hash, cached system blocks (key A), frozen model string | Wrong prompts, hash abort, or model rejection |
| `services/batch-poller` | `bishop_shared.anthropic_config`, `enrichment_parsers`, `batch_custom_id` | Model constant; Call 1/2 parse; custom_id re-encode | Parse drift; join failure; model mismatch vs submit side |
| `tests/test_shared_enums.py` | `bishop_shared.enums` + `state-worker/app/enums.py` literals | Hardcoded literal sets must match both enum modules | Drift guard fails; silent wire incompatibility if test removed |
| `services/scraper` | `services/state-worker` (runtime HTTP) | Manifest batch and scraper-state over `STATE_WORKER_URL` | Scraper cycle fails; manifests not ingested |
| `services/pre-filter-worker` | `services/state-worker` (runtime HTTP) | Poll DISCOVERED; register batches | Pre-filter loop stalls |
| `services/batch-poller` | `services/state-worker` (runtime HTTP) | List/patch/timeout batches; post pre-filter and enrichment results | In-flight batches never complete |
| `services/content-scraper` | vendored `services/scraper/app` as `scraper_app` | Dockerfile COPY + import rewrite; `resolve_adapter` iterates `ADAPTER_REGISTRY` | Adapter drift if scraper changes not rebuilt into content-scraper |
| `services/content-scraper` | `services/state-worker` (runtime HTTP) | Poll RELEVANCE_PASSED; POST content/failed | M4 pipeline stall |
| `services/enrichment-batcher` | `bishop_shared` enrichment/profile/cache/truncation | Two-stage Anthropic submit (keys B/C) | Hash/cache-floor failures block enrichment |
| `services/enrichment-batcher` | `services/state-worker` (runtime HTTP) | Poll SCRAPED / STAGE2_QUEUED; POST /batches | Entries stuck mid-enrichment |
| `services/vector-writer` | `bishop_shared.indexing_config`, `index_policy` | Embed text, store paths, gate-2 bands | Empty or wrong index files |
| `services/vector-writer` | `services/state-worker` (runtime HTTP) | Poll VECTOR_WRITE_QUEUED; POST indexed/failed | Indexing stall |
| `services/query-api` | index stores + SQLite `mode=ro` + state-worker write proxies | Read path + controlled mutations | DuckDB lock skip; WAL read concurrency; 502 on upstream |
| `services/ui` | `services/query-api` HTTP only | No direct state-worker or SQLite | QUERY_API_URL misconfig breaks all pages |
| `services/pre-filter-worker` | `config/profiles` (host volume) | Profiles mounted at `/app/config/profiles` | Missing profile file blocks batch submit |
| `services/pre-filter-worker` / enrichment-batcher / batch-poller | `config/prompts` (image-baked) | Rubrics at `/app/config/prompts` | Stale rubric until image rebuild |
| `services/scraper/app/loop.py` | `services/scraper/app/adapters/registry.py` | Iterates `ADAPTER_REGISTRY` (7 sources) | New sources require registry + rate limit + tests |
| `services/state-worker/app/routers/*` | `services/state-worker/app/transitions.py` | Routers delegate all state mutations to transition engine | Business logic drift if routers bypass transitions |
| `services/state-worker/app/transitions.py` | `services/state-worker/app/alerts.py` | Alert triggers call `emit_alert` | Missing alerts or duplicate error_log rows |
| `services/state-worker/app/main.py` | `app/db.py`, `app/sweeps.py` | Lifespan: integrity → migrations → pool → sweep task | Race or missing sweeps; corrupt DB refuses boot |
| All eight dependents (runtime) | `state-worker` `/health/db` | Compose `depends_on: condition: service_healthy` | Dependent containers never start |
| `bishop_cli` | `services/query-api` (runtime HTTP) | Host Typer client to QUERY_API_HOST_PORT | CLI fails if query-api down or QUERY_API_BASE_URL wrong |
| `services/scraper/app/adapters/arxiv.py` | `config/sources/arxiv.yaml` via `bishop_shared.source_config` | Primary-category include/exclude before gate 1 | Over-broad exclude silently drops human-pass items |
| `scripts/sqlite_snapshot.py` | `bishop_shared.constants` SQLITE_SNAPSHOT_* | Host ops tooling vs live DB path | Snapshot path drift; this-host sqlite_live overlay |
| `scripts/verify-g2.sh`, `verify-m2.sh` … `verify-m8.sh` | G2 pytest slice + milestone test modules | Hardcoded test module lists | Gate false pass/fail if test layout changes |
| `scripts/verify-m3.sh` | `scripts/verify-g3.sh` | M3 gate chains G2 → G3 → M3 pytest suite | G3 failure blocks M3 verification |
| Service Dockerfiles | repo root build context | `context: .` with COPY `bishop_shared/`, `services/<name>/`, `config/` as needed | Build failure if context narrowed |
| `tests/test_state_worker_*.py` | `services/state-worker/app` on sys.path | Manual path insertion for `from app.main` | Import failures if package layout changes |

## External dependencies

| Dependency | Version pinned | Role in project | Sensitivity |
|------------|---------------|-----------------|-------------|
| Python | `>=3.12` (pyproject.toml); `3.12-slim` in Dockerfiles | Runtime for all containers and local pytest | medium |
| FastAPI | `>=0.110` (state-worker, query-api, ui) | HTTP framework | medium |
| uvicorn | `>=0.27[standard]` | ASGI server | medium |
| Pydantic | `>=2.0` | Domain and wire model validation | medium |
| Alembic | `>=1.13` | SQLite schema migrations | medium |
| SQLAlchemy | `>=2.0` | Alembic dependency | low |
| aiosqlite | `>=0.20` | Async SQLite writer pool (state-worker only) | medium |
| httpx | `>=0.27` | HTTP clients for state-worker and source APIs | medium |
| anthropic | `>=0.40` | Anthropic Messages Batches API (submit + poll) | high |
| PyYAML | `>=6.0` | NL profile YAML parsing | medium |
| jinja2 | `>=3.1` | ui templates | low |
| python-multipart | `>=0.0.9` | ui forms | low |
| typer | `>=0.12` (pyproject.toml) | Host `bishop_cli` | low |
| lancedb | `>=0.17.0` | Dense vector store | high |
| duckdb | `>=1.0` | Metadata mirror | medium |
| rank-bm25 | `>=0.2.2` | BM25 Okapi index | medium |
| sentence-transformers | `>=2.7.0` | Embeddings (writer + query encoder) | high |
| pyarrow | `>=15.0` | LanceDB dependency | medium |
| filelock | `>=3.13` | BM25 write serialization | medium |
| tiktoken | dev/test | Token-floor proxy tests | low |
| respx | `>=0.21` (dev) | Mock httpx in scraper/worker tests | low |
| pytest / pytest-asyncio | `>=8.0` / `>=0.23` (dev) | Contract test runner | low |
| Docker / Docker Compose | unpinned (host tooling) | Delivery and G1 gate | high |
| curl | in state-worker image + host for verify-g1 | Health probing | low |
| stdlib `xml.etree.ElementTree` | Python stdlib | ArXiv Atom XML parsing | low |
| stdlib `html.parser` | Python stdlib | ArXiv HTML text extraction | low |
| stdlib `sqlite3` | Python stdlib | query-api `mode=ro` reads; snapshot/restore scripts | medium |
| export.arxiv.org | external service (unpinned) | ArXiv Atom export API | high |
| api.anthropic.com | external service (unpinned) | Pre-filter and enrichment batch submit and poll | high |
| huggingface.co | external service (unpinned) | HuggingFace Hub REST | medium |
| paperswithcode.com | external service (unpinned) | Papers With Code REST | medium |
| api.semanticscholar.org | external service (unpinned) | Semantic Scholar Graph API | medium |
| api.github.com | external service (unpinned) | GitHub Search API; `GITHUB_TOKEN` recommended | medium |
| api2.openreview.net | external service (unpinned) | OpenReview notes search | medium |
| www.lesswrong.com/graphql | external service (unpinned) | LessWrong GraphQL-over-GET | medium |

**Orphaned, not runtime:** leftover `services/*/stub_main.py` using stdlib `http.server` — Docker CMD is `python -m app.main`.
