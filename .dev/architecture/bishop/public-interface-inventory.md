Section:      public-interface-inventory
Version:      1.0.0
Last updated: 2026-06-10

| Symbol | Module | Kind | Signature summary | Consumed by | Stability |
|--------|--------|------|-------------------|-------------|-----------|
| `VolumeMount` | `bishop_shared.constants` | class | Frozen dataclass: `host_suffix`, `container_path` | `tests/test_constants.py` | stable |
| `BISHOP_SERVICES` | `bishop_shared.constants` | constant | Tuple of nine compose service keys in spec order | `docker-compose.yml`, `tests/*`, init/verify scripts | stable |
| `BISHOP_VOLUME_MOUNTS` | `bishop_shared.constants` | constant | List of six host→container volume pairs per spec §8.5 | compose, init scripts, `tests/test_compose.py`, `verify-g1.sh` | stable |
| `BISHOP_DATA_ROOT_DEFAULT` | `bishop_shared.constants` | constant | Default host data root string `~/bishop_data` | `.env.example`, `tests/test_constants.py` | stable |
| `STATE_WORKER_INTERNAL_PORT` | `bishop_shared.constants` | constant | Internal HTTP port `8000` for state-worker and query-api container listen | compose healthcheck, state-worker app, query-api stub, tests | stable |
| `QUERY_API_HOST_PORT` | `bishop_shared.constants` | constant | Host-mapped port `8080` for query-api | compose, `verify-g1.sh`, ui stub derivation, tests | stable |
| `UI_HOST_PORT` | `bishop_shared.constants` | constant | Host-mapped port `8081` for ui | compose, `verify-g1.sh`, tests | stable |
| `health` | `services/state-worker/app/main.py` | function route | `GET /health` → `200` with `HealthResponse` | compose healthcheck, `verify-g1.sh`, `tests/test_state_worker_health.py` | stable |
| `run` | `services/state-worker/app/main.py` | function | Starts uvicorn on `0.0.0.0:STATE_WORKER_INTERNAL_PORT` | Docker CMD `python -m app.main` | stable |
| `HealthResponse` | `services/state-worker/app/models.py` | class | Pydantic model: `status: Literal["ok"]` | `app/main.py`, health tests | stable |
| `main` | `services/<stub>/stub_main.py` | function | Service entry point — long-running loop or HTTP server | Docker CMD per service Dockerfile | experimental |
| `RootHandler` | `services/query-api/stub_main.py`, `services/ui/stub_main.py` | class | HTTP handler: `GET /` → `200 ok`, else `404` | stub HTTP servers, `tests/test_service_stubs.py` | experimental |

**Re-exports:** `bishop_shared/__init__.py` re-exports all constants and `VolumeMount` listed above.

**Not yet public (M0):** REST endpoints beyond `/health`, SQLite schema, poll-and-claim APIs, and inter-service RPC are deferred to M1+ per charter.
