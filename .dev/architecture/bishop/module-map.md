Section:      module-map
Version:      1.0.0
Last updated: 2026-06-10

| Module path | Role | Key files | Stability |
|-------------|------|-----------|-----------|
| `bishop_shared` | Shared monorepo constants re-exported for consumers | `__init__.py` | stable |
| `bishop_shared.constants` | Frozen M0 contract: service names, volume mounts, ports | `constants.py` | stable |
| `services/state-worker` | Central state service container; M0 exposes `GET /health` only | `Dockerfile`, `requirements.txt`, `app/` | active |
| `services/state-worker.app` | FastAPI application package for state-worker | `main.py`, `models.py` | active |
| `services/scraper` | Ingest scraper service; M0 long-running stub | `stub_main.py`, `Dockerfile` | experimental |
| `services/pre-filter-worker` | Pre-filter pipeline worker; M0 stub | `stub_main.py`, `Dockerfile` | experimental |
| `services/content-scraper` | Content scraper worker; M0 stub | `stub_main.py`, `Dockerfile` | experimental |
| `services/enrichment-batcher` | Enrichment batch submitter; M0 stub | `stub_main.py`, `Dockerfile` | experimental |
| `services/batch-poller` | Batch status poller; M0 stub | `stub_main.py`, `Dockerfile` | experimental |
| `services/vector-writer` | Vector/BM25 index writer; M0 stub | `stub_main.py`, `Dockerfile` | experimental |
| `services/query-api` | Read-path HTTP API; M0 HTTP stub on internal port 8000 | `stub_main.py`, `Dockerfile` | experimental |
| `services/ui` | Web UI; M0 HTTP stub listening on container port 80 | `stub_main.py`, `Dockerfile` | experimental |
| `tests` | Static contract tests for constants, compose, stubs, and G1 script | `test_*.py` | active |
| `scripts` | Host volume bootstrap and G1 verification gate | `init-volumes.sh`, `init-volumes.ps1`, `verify-g1.sh` | active |
| `docker-compose.yml` (repo root) | Nine-service stack wiring, network, volumes, health gate | `docker-compose.yml` | active |
| `.env.example` | Documented host data root default for compose interpolation | `.env.example` | stable |

**Notes (M0):** Eight pipeline services are stubs with no business logic. Only `state-worker` runs a real HTTP server beyond minimal root handlers on `query-api` and `ui`. Post-M1, `services/state-worker` becomes the contract anchor for the full state machine per charter §M1.
