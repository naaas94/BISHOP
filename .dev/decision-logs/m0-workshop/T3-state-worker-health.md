# T3 — state-worker health endpoint

**Plan:** m0-workshop · **Date:** 2026-06-09

## Chosen approach

- **Stack:** FastAPI + uvicorn on `python:3.12-slim`, matching T1 `pyproject.toml` Python baseline.
- **Route surface:** Single `GET /health` returning `HealthResponse` (`status: Literal["ok"]`); FastAPI auto-docs disabled so no `/openapi.json` or `/docs` routes appear at M0.
- **Listen binding:** `run()` starts uvicorn on `0.0.0.0` with port from `bishop_shared.constants.STATE_WORKER_INTERNAL_PORT`; Docker `CMD` is `python -m app.main` so the constant is the single source of truth for the container listen port.
- **Healthcheck probe:** `curl` installed in the Dockerfile via `apt-get` for T4 compose `healthcheck` (`curl -f http://localhost:8000/health`).
- **Tests:** `fastapi.testclient.TestClient` against the app object; `sys.path` adjusted in the test module to import from the hyphenated `services/state-worker/` directory without a conftest change.

## Alternatives rejected

- **Hardcoded `--port 8000` in Dockerfile CMD via uvicorn CLI:** Rejected — duplicates the port constant and violates the kill criterion that the app must bind `STATE_WORKER_INTERNAL_PORT`.
- **Python-based compose healthcheck instead of curl:** Rejected for T3 — plan §2 Wire names `curl` as the compose probe; installing curl in the slim image is low cost and unblocks T4 without a custom healthcheck script.
- **Adding `app/__init__.py` or root `conftest.py` for imports:** Rejected — not in T3 files-to-touch; namespace-package import via service-root `sys.path` in the test file is sufficient.

## Assumptions made

- `STATE_WORKER_INTERNAL_PORT` remains `8000` through M0; T4 compose healthcheck URL uses the same port inside the container network namespace.
- Developers run pytest with `services/state-worker/requirements.txt` installed (fastapi, uvicorn, pydantic); root `pyproject.toml` dev extras were not extended in T3 to avoid scope creep into T2/T3 dependency-skew territory.
- No §9.1 REST routes beyond `/health` are required until M1; disabling FastAPI OpenAPI endpoints is acceptable for M0.

## Items deferred

- **Compose `healthcheck` `start_period: 10s`:** T4 (mitigates uvicorn startup race).
- **Docker image build verification in pytest:** Deferred — contract tests use TestClient only per plan §2 Tests policy; G1 compose verification is T5.
- **Root `pyproject.toml` dev dependency pin for fastapi/uvicorn:** Deferred — parallel T2/T3 `requirements.txt` pattern; unify in a follow-on if CI needs a single install path.
