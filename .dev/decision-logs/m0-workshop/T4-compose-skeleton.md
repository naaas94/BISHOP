# T4 — Docker Compose skeleton

**Plan:** m0-workshop · **Date:** 2026-06-09

## Chosen approach

- **Single `docker-compose.yml`:** All nine §9 services on network `bishop-internal` with image tags `bishop/<service-name>:m0`.
- **Build context:** Repo root (`.`) with `dockerfile: services/<name>/Dockerfile` per service — matches T2/T3 `COPY services/...` and `COPY bishop_shared` paths without Dockerfile edits.
- **Health gate:** `state-worker` healthcheck `curl -f http://localhost:8000/health` with `start_period: 10s`; eight dependents use `depends_on: state-worker: condition: service_healthy` and `STATE_WORKER_URL=http://state-worker:8000`.
- **Host ports (A1):** Only `query-api` (`${QUERY_API_HOST_PORT}:8000`) and `ui` (`${UI_HOST_PORT}:80`); `state-worker` has no `ports:` mapping.
- **Volumes:** Per-service matrix from T1 decision log; host paths `${BISHOP_DATA_ROOT}/<suffix>` aligned with `BISHOP_VOLUME_MOUNTS`.

## Alternatives rejected

- **`build.context: services/<name>` (plan §2 reminder):** Rejected — T2/T3 Dockerfiles copy `bishop_shared/` and `services/<name>/...` relative to repo root; per-service context would require Dockerfile rewrites outside T4 files-to-touch.
- **Default host-port interpolation in compose (`${QUERY_API_HOST_PORT:-8080}`):** Rejected — plan §2 Wire binds literal `${QUERY_API_HOST_PORT}` / `${UI_HOST_PORT}`; values come from `.env` (see T1 constants and `.env.example` for `BISHOP_DATA_ROOT`; host ports match `bishop_shared.constants` defaults when unset in shell).
- **Mapping `state-worker` to host for G1 curl:** Rejected — resolves charter/spec conflict (A1); internal-only health via compose healthcheck and T5 in-container exec.

## Assumptions made

- T2/T3 Dockerfiles remain buildable from repo root; no service renames before T5.
- Developers provide `.env` with `BISHOP_DATA_ROOT` (explicit path on Windows) and optional port overrides before `docker compose up`.
- `curl` in state-worker image (T3) satisfies compose healthcheck; `start_period: 10s` covers uvicorn startup.

## Items deferred

- **G1 hostname resolution and host curl checks:** T5 (`scripts/verify-g1.sh`).
- **`.env.example` entries for `QUERY_API_HOST_PORT` / `UI_HOST_PORT`:** Deferred — constants defaults (8080/8081) match T1; compose interpolation expects env at runtime; T5 may document full `.env` template.
- **Compose validation via `docker compose config` in pytest:** Deferred — static `tests/test_compose.py` covers contract structure; live stack proof is T4 manual gate + T5 G1.
