# T1 — Repo layout, constants, and volume init

**Plan:** m0-workshop · **Date:** 2026-06-09

## Chosen approach

- **Monorepo layout:** `services/<compose-service-name>/` with hyphenated directory names matching compose service keys exactly (resolves context-map A2).
- **Shared constants:** `bishop_shared/constants.py` freezes §9 service names (9), §8.5 volume mounts (6), and M0 ports.
- **Host data root:** `${BISHOP_DATA_ROOT}` in `.env` / `.env.example`, default `~/bishop_data`. Init scripts create all six host subdirectories regardless of per-service mount subset.
- **Ports (resolves A3):** `state-worker` internal `8000` (no host mapping); `query-api` host `8080` → container `8000`; `ui` host `8081` → container `80`.
- **Docker network name:** `bishop-internal` (declared in T4 compose).
- **Windows data root (resolves A5):** `.env.example` documents that Docker Desktop on Windows does not expand `~`; developers set an explicit path such as `C:/Users/you/bishop_data`.

### Per-service volume matrix (M0)

| Service | Mounts |
|---------|--------|
| `state-worker` | sqlite, logs |
| `batch-poller` | sqlite, logs |
| `vector-writer` | lancedb, duckdb, bm25, logs |
| `query-api` | lancedb, duckdb, bm25, sqlite, logs |
| `pre-filter-worker`, `enrichment-batcher` | profiles, logs |
| `scraper`, `content-scraper` | logs only |
| `ui` | none |

Host path pattern for each mount: `${BISHOP_DATA_ROOT}/<host_suffix>` → `<container_path>` per `BISHOP_VOLUME_MOUNTS`.

## Alternatives rejected

- **Single top-level package per service without `services/` prefix:** Rejected — spec §9 names are service-oriented; `services/<name>/` keeps compose build contexts obvious and matches common monorepo Docker patterns.
- **Hardcoding `~/bishop_data` only in compose without `BISHOP_DATA_ROOT`:** Rejected — fails on Windows where `~` is not expanded by Docker; env interpolation is the cross-platform contract.
- **Creating only volume dirs each service mounts:** Rejected — init scripts create all six §8.5 dirs so G1 writability checks and future mount additions do not require script changes.

## Assumptions made

- Nine §9 service names remain frozen through M0; any rename requires constants + compose + directory renames together.
- `BISHOP_DATA_ROOT` is set in `.env` (copied from `.env.example`) before `docker compose up`; compose volume interpolation reads the same value on Linux and Windows when the path is explicit on Windows.
- Per-service volume subset in this log is authoritative for T2/T4; over-mounting at M0 is acceptable.

## Items deferred

- **Compose `docker-compose.yml` and `bishop-internal` network wiring:** T4.
- **Service Dockerfiles and stub entry points:** T2/T3.
- **`scripts/verify-g1.sh`:** T5.
- **Init-script integration test (shell creates dirs on real FS):** Deferred — contract covered by constants tests + manual G1; no pytest Docker/shell harness in M0 scope.
