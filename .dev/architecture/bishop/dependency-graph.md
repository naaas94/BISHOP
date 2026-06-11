Section:      dependency-graph
Version:      1.0.0
Last updated: 2026-06-10

## Internal dependencies

| Dependent | Depends on | Nature of coupling | Risk if changed independently |
|-----------|-----------|--------------------|------------------------------|
| `docker-compose.yml` | `bishop_shared.constants` (conceptual) | Service keys, volume suffixes, and port numbers must stay aligned with frozen constants and pytest matrices | Compose tests fail; G1 gate fails; DNS/health chain breaks |
| `tests/test_compose.py` | `bishop_shared.constants`, T1 decision log matrix | Duplicates `SERVICE_VOLUME_SUFFIXES` per-service mount map not encoded in constants module | Volume under/over-mount if matrix updated in one place only |
| `services/state-worker` | `bishop_shared.constants` | Imports `STATE_WORKER_INTERNAL_PORT` for uvicorn bind | Port drift vs compose healthcheck |
| `services/query-api`, `services/ui` | `bishop_shared.constants` | Container listen ports derived from shared constants | Host port mapping mismatch with compose |
| All eight dependents (runtime) | `state-worker` health | Compose `depends_on: condition: service_healthy` blocks startup until `/health` passes | Dependent containers never start or restart-loop if health contract breaks |
| `scripts/verify-g1.sh` | `bishop_shared.constants` (conceptual), init scripts | Hardcodes nine services, six volume subdirs, and default ports mirroring constants | G1 false pass/fail if constants change without script update |
| `scripts/init-volumes.sh`, `init-volumes.ps1` | `BISHOP_VOLUME_MOUNTS` host_suffix values (conceptual) | Both create the same six subdirectory names | Missing host dirs if suffix list diverges |
| Service Dockerfiles | repo root build context | All use `context: .` and COPY paths like `bishop_shared/` or `services/<name>/` | Build failure if context narrowed to per-service directory |
| `tests/test_state_worker_health.py` | `services/state-worker/app` on sys.path | Manually inserts state-worker and repo root for `from app.main` | Import failures if package layout changes |

## External dependencies

| Dependency | Version pinned | Role in project | Sensitivity |
|------------|---------------|-----------------|-------------|
| Python | `>=3.12` (pyproject.toml); `3.12-slim` in Dockerfiles | Runtime for all containers and local pytest | medium |
| FastAPI | `>=0.110` (state-worker requirements.txt) | state-worker HTTP framework | medium |
| uvicorn | `>=0.27[standard]` | ASGI server for state-worker | medium |
| Pydantic | `>=2.0` | HealthResponse validation | medium |
| pytest | `>=8.0` (dev optional dep) | Contract test runner | low |
| Docker / Docker Compose | unpinned (host tooling) | M0 delivery and G1 gate | high |
| curl | in state-worker image + host for verify-g1 | Health probing | low |
| stdlib `http.server` | Python stdlib | query-api and ui M0 stubs | low |

**Not yet introduced (planned M1+):** aiosqlite, Alembic, LanceDB, DuckDB, BM25 libraries, LLM client SDKs — per bishop_spec_0_6.md and charter milestone registry.
