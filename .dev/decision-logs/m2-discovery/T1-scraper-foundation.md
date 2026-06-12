# T1 — scraper foundation

**Plan:** m2-discovery · **Date:** 2026-06-12

## Chosen approach

- **Shared enums:** `bishop_shared/enums.py` exposes `SourceEnum` and `DomainEnum` only, mirroring `services/state-worker/app/enums.py` §20 literals. Scraper imports from `bishop_shared`; state-worker is not refactored in M2 (plan flag 1 resolution).
- **Scraper package layout:** `services/scraper/app/` with `config.py`, `models.py`, and `state_worker_client.py` (async httpx client for `GET/POST /scraper-state/{source}` and `POST /manifest/batch`).
- **Config:** `STATE_WORKER_BASE_URL` from `STATE_WORKER_URL` (default `http://state-worker:8000`); `ARXIV_CATEGORIES` frozen tuple; `ARXIV_BACKFILL_WINDOW_DAYS` default `7` via `BISHOP_ARXIV_BACKFILL_WINDOW_DAYS`; `SCRAPER_SCHEDULE_INTERVAL_SEC` default `21600` via `BISHOP_SCRAPER_SCHEDULE_INTERVAL_SEC`.
- **Dockerfile:** Repo-root build context copies `bishop_shared` and `app/` with `PYTHONPATH=/app`; M0 `stub_main.py` CMD retained until T5 wires `python -m app.main`.
- **Wire DTOs:** Pydantic models align with state-worker `ManifestBatchEntryWire` and `ScraperStateResponse` field names; `domain` serializes as `"professional"` string for ArXiv ingest.

## Alternatives rejected

- **Import state-worker `app.enums` from scraper container:** Rejected — separate `PYTHONPATH` and image boundary; would couple containers and break scraper Dockerfile isolation (plan §5.2 assumption).
- **Duplicate enum literals only in scraper models without `bishop_shared`:** Rejected — plan flag 1 requires shared module and `test_shared_enums_match_state_worker` drift guard.

## Assumptions made

- `httpx.MockTransport` in unit tests is sufficient for T1 client coverage; live state-worker integration remains G2/T5 scope.
- `ManifestIngestEntry.domain` as `DomainEnum` round-trips to the wire string state-worker expects (`DomainEnum(wire.domain)` in transitions).
- T5 will replace stub CMD, add `app.main` scheduler, and update compose image tag to `bishop/scraper:m2`.

## Items deferred

- **Production 60-day `ARXIV_BACKFILL_WINDOW_DAYS`:** §18.2 production default documented here; M2 smoke default remains `7` (plan flag 3).
- **`SourceAdapter`, rate limits, failure envelope, ArXiv adapter, scrape loop:** T2–T5 per plan DAG.
- **State-worker import of `bishop_shared.enums`:** deferred beyond M2 to avoid M1 surface churn.
