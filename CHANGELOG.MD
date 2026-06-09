# Changelog

## m0-workshop — 2026-06-09

- T1 (repo layout, shared constants, volume init): Added `bishop_shared/constants.py` with frozen §9 service names, §8.5 volume mounts, and M0 port constants; `.env.example`, cross-platform `scripts/init-volumes` scripts, pytest coverage, and architectural decision log for layout and volume matrix. Establishes the typed contract surface T2–T5 consume without embedding paths in compose yet.
- T2 (eight non–state-worker service stubs): Added Dockerfiles and `stub_main.py` entry points for scraper, pre-filter-worker, content-scraper, enrichment-batcher, batch-poller, vector-writer, query-api, and ui; workers use sleep loops, HTTP stubs serve `GET /` → `ok`, ports imported from `bishop_shared.constants`. + added `tests/test_service_stubs.py`. Docker image build smoke not covered in pytest (deferred to T4/T5 G1 per plan test policy).
- T3 (state-worker health endpoint): Added FastAPI `GET /health` on `STATE_WORKER_INTERNAL_PORT`, `HealthResponse` model, Dockerfile with curl for compose healthcheck, and TestClient unit tests. Only `/health` is exposed at M0; see `.dev/decision-logs/m0-workshop/T3-state-worker-health.md`.
