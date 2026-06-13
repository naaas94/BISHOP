# T2 — Content-scraper vendor layout and worker loop

**Plan:** m4-content · **Date:** 2026-06-13

## Chosen approach

- **Docker layout:** Worker package at `/app/app/` (`python -m app.main`); vendored scraper adapter layer at `/app/scraper_app/` copied from `services/scraper/app` with `sed` rewriting `app.` imports to `scraper_app.`; `PYTHONPATH=/app`.
- **Loop:** `content_scrape_cycle` polls `GET /manifest/poll?state=RELEVANCE_PASSED`, resolves adapter via `ADAPTER_REGISTRY`, wraps `fetch_content` in vendored `failure_envelope`, posts `POST /entries/content` on success or `POST /entries/failed` with `state_at_failure=SCRAPE_QUEUED` on adapter failure.
- **Failure mapping:** Dedicated `failure_mapping.py` implements §6.3 table (`RetryExhaustedError` retriable; `PermanentFailureError` / `EscalatableError` / generic not retriable).
- **Non-ArXiv sources:** `resolve_adapter` logs `adapter_not_found` and skips entry (M4 ArXiv-only charter).
- **Tests:** Pytest vendors `scraper_app` into a temp dir with the same sed rewrite as Docker for import smoke and loop tests.

## Alternatives rejected

- **Import scraper as second `app` package in same image:** Rejected — PYTHONPATH collision with content-scraper worker `app` (context-map Flag 2).
- **Duplicate ArxivAdapter in content-scraper:** Rejected — drift risk vs T1 `services/scraper` source of truth (coupling C1).
- **Log-only adapter failures like discovery scraper loop:** Rejected — M4 exit gate requires `POST /entries/failed` for retriable `SCRAPE_FAILED` routing.

## Assumptions made

- Docker `sed` rewrite covers all intra-scraper `app.` imports (no dynamic imports of `app.*`).
- Vendored `scraper_app` at T2 commit matches T1 `fetch_content` behavior when COPY list includes full `services/scraper/app` tree.
- Poll batch contains only ArXiv rows in M4; unknown registry entries are rare and safe to skip.

## Items deferred

- **State-worker content POST 409 (`invalid_transition`, `provenance_incomplete`) loop branch:** Covered by state-worker router tests (T3); loop logs ERROR and continues — adversarial gap deferred to T4 integration.
- **Live Docker vendor smoke in CI:** Default pytest uses temp-dir vendoring; full image build deferred to T4 `verify-m4.sh`.
