# Bishop operator UI — agent reference

Standing note for `services/ui`. Folder index: [README.md](README.md). Cursor rule: `.cursor/rules/bishop-ui.mdc`.
Host URL on this machine: `http://localhost:8081` (`UI_HOST_PORT` in `bishop_shared/constants.py`).

The UI is an operator console for the local stack (pipeline glance, search, parked, escalations). It is not a public product surface and it is not a second query-api.

## Paths

| Role | Path |
|------|------|
| App | `services/ui/app/main.py` |
| Config | `services/ui/app/config.py` — `QUERY_API_URL` |
| Templates | `services/ui/app/templates/` (`base.html` + pages + `partials/`) |
| CSS | `services/ui/static/style.css` |
| Image | `bishop/ui:m8` — `services/ui/Dockerfile` copies `app/` and `static/` into the image |
| Compose | `docker-compose.yml` service `ui` — host `${UI_HOST_PORT}:80` |
| Tests | `tests/test_ui_routes.py` (pages); `tests/test_query_api_stats.py` (dashboard data) |
| Stats backend | `services/query-api/app/stats_reader.py`, `routers/stats.py`, `StatsOverview` / `HarvestStats` / `ScrapeStats` / `TodayStats` in `models.py` |

No bind-mount of templates or CSS. A template/CSS/`main.py` change is invisible until `docker compose build ui && docker compose up -d ui`.

## Doctrine

- **Query-api only.** Every data fetch and mutation goes through `_query_api_get` / `_query_api_request` in `main.py`. Compose also sets `STATE_WORKER_URL`; the UI must not use it. Kill test: `test_ui_main_has_no_direct_store_imports` forbids `sqlite3`, `lancedb`, `duckdb`, `rank_bm25`, `STATE_WORKER_URL`, `state-worker` in `main.py`.
- **No OpenAPI.** `docs_url=None` like query-api.
- **HTML 200 with an error slot.** Upstream 502/4xx still render the page with `error = "query-api returned status {code}"`. Do not turn that into a FastAPI 502 unless you are changing the contract on purpose.
- **`source_id` paths use `:path`.** GitHub/HF ids contain `/`. Quote with `_quote_source_id` (empty `safe=`) when calling query-api.
- **Cache-bust CSS.** `base.html` links `/static/style.css?v={{ static_version }}`. `static_version` is `style.css` mtime at process start (`_static_asset_version`). Browsers otherwise keep a stale sheet across rebuilds (dashboard bars vanish; base theme still looks fine).

## Pages

`GET /` → 302 `/dashboard`. Nav in `base.html`: Dashboard, Today, Scrape, Harvest, Batches, Search, Explorer, Landed, Parked, Escalations.

| UI route | Template | query-api | Notes |
|----------|----------|-----------|--------|
| `GET /dashboard` | `dashboard.html`; `HX-Request` → `partials/dashboard_stats.html` | `GET /stats/overview` | Derived `pass_rate`, `in_flight`, `in_queue`. Cards, funnel, ingest only — scrape/harvest/today live on their pages. Partial root polls every 30s (`hx-trigger="every 30s"`). |
| `GET /today` | `today.html`; `HX-Request` → `partials/today_stats.html` | `GET /stats/today` | UTC-day glance: discovered, scrape health, harvest one-liner, cohort funnel (zero bars hidden). Partial polls every 30s. See [today.md](today.md). |
| `GET /scrape` | `scrape.html`; `HX-Request` → `partials/scrape_stats.html` | `GET /stats/scrape` | Incremental cursors, lag bars, overlay. Today volume is a one-liner to `/today`. GitHub row shows harvest `github_released_today` beside discovered today. Partial polls every 30s. See [scrape.md](scrape.md). |
| `GET /harvest` | `harvest.html`; `HX-Request` → `partials/harvest_stats.html` | `GET /stats/harvest` | Unreleased modeled liability, mill walk + forecast band, daily faucet. Days-to-drain is current unreleased only. Partial polls every 30s. See [harvest-dashboard.md](harvest-dashboard.md). |
| `GET /batches` | `batches.html` | `GET /batches?status=complete` | Sorted by `completed_at` desc in the UI. |
| `GET /batches/{batch_id}` | `batch_detail.html` | `GET /batches/{id}` | |
| `GET /search` | `search.html`; `HX-Request` → `partials/search_results.html` | `GET /search?q=` | Live search; no filters. |
| `GET /explorer` | `explorer.html` | `GET /search` with filters | `source`, `type`, `reading_status`, `min_relevance`, `days`, `tags`. Empty `q` → no request. |
| `GET /landed` | `landed.html` | `GET /recent` | Indexed window, default 7 days. Optional `source`. No required query. See [landed.md](landed.md). |
| `GET /entries/{source_id}` | `entry_detail.html` | `GET /entries/{id}` | |
| `POST /entries/{id}/reading-status` | `entry_detail.html` | `PATCH /entries/{id}/reading-status` | Form; options `unread` / `reading` / `read` / `archived`. |
| `GET /parked` | `parked.html` | `GET /parked` | |
| `POST /parked/{id}/promote` | `parked.html` | `POST /parked/promote` | |
| `GET /escalations` | `escalations.html` | `GET /escalations` | |
| `POST /escalations/{id}/retry` | `escalations.html` | `POST /entries/{id}/retry` | |
| `POST /escalations/{id}/permanent-fail` | `escalations.html` | `POST /entries/{id}/permanent-fail` | |
| `GET /health` | JSON | none | Liveness. |

`GET /recent` is wrapped by `/landed`. Search vs Explorer: `/search` is q-only; `/explorer` is filtered `/search`.

Mutations that write SQLite still go query-api → state-worker. The UI never opens `bishop.db`.

## Dashboard

Stats are aggregates in query-api (`read_stats_overview`, SQLite `mode=ro`). The UI does not count rows.

Headline cards: indexed entries, total entries, manifest items, **total batches** (`batches_total`), pre-filter pass rate (lifetime yes, with parked vs proceeded), in queue (`DISCOVERED` + `RELEVANCE_QUEUED`), in flight (sum of `queue_depth`), escalated, permanently failed (from `funnel` labels). Funnel bars scale live stages without the reject stock; rejected keeps the count and no fill. Ingest per day is volume vs the 30-day peak, stacked by source inside that width. See [scrape.md](scrape.md), [harvest-dashboard.md](harvest-dashboard.md), [landed.md](landed.md), and [today.md](today.md).

Charts are CSS bars (`.bar-row` / `.bar-track` / `.bar-fill`), not a JS chart library. Funnel is 13 fixed stages; relevance histogram is 10 buckets with an en dash (`0.0–0.1`). Missing DB → zeroed overview, not 500.

New dashboard numbers: add the field on `StatsOverview` + SQL in `stats_reader.py` + tests in `test_query_api_stats.py`, then a card or bar in `partials/dashboard_stats.html`. Do not compute corpus stats in the UI.

Ingest / budget analytics do **not** grow the dashboard card row or a one-liner strip. They get `GET /stats/<name>` + a page (scrape lag, harvest liability, today discovered). Write-up: `.dev/decision-logs/ops/2026-09-27-operator-ingest-pages.md`.

## How to change the UI

1. Edit templates / `style.css` / `main.py` (and query-api if the page needs new JSON).
2. Extend `tests/test_ui_routes.py`. Fake `_query_api_get` — do not hit a live API. Keep the no-store-imports kill test green.
3. If the JSON reads overlay, scrape interval, or harvest budget, add those keys to **query-api** compose `environment:` (`tests/test_compose.py`). Then `docker compose build` **and** `up -d query-api ui` so the query-api container is recreated. Rebuild-only keeps the old env.
4. Hard-refresh is usually unnecessary after a CSS change because `?v=` changes; if bars look unstyled, the image was not rebuilt or the browser still has the old HTML without `?v=`.
5. Browser-check the page you touched. Compose UI is the real render path.

### Adding a page

- Route in `main.py` that only calls `_query_api_*`.
- Template extending `base.html`; put a nav link in `base.html` if it is a top-level page.
- Prefer query-api JSON that already exists. New aggregates belong in query-api, not ad-hoc UI SQL.
- Upstream failure: same `error` slot pattern as `/batches`.
- If the page polls, follow dashboard: `HX-Request` returns a partial whose root has `hx-get` + `hx-swap="outerHTML"`.

## Stack notes

- FastAPI + Jinja2 + htmx 2.0.4 from unpkg. One CSS file. FRS first-pass tokens (`color-scheme: light dark`); gold is focus, `is-ok` / `is-warn` / `is-bad` / `is-dead` are health. As-built, not locked (operator 2026-09-27). See [design.md](design.md).
- Container listens on port **80** (`UI_CONTAINER_PORT = QUERY_API_HOST_PORT - STATE_WORKER_INTERNAL_PORT` → 8080 − 8000). Kill test: `test_ui_container_port_matches_wire_eighty`.
- `stub_main.py` is leftover and must not be the Docker CMD (`test_dockerfile_uses_real_main_entrypoint`).

## Architecture folder drift

`.dev/architecture/bishop/` still says `GET /` → `/batches` and omits `/dashboard` and `GET /stats/overview`. That folder is flagged stale in `AGENTS.md` — do not silently rewrite it from this note. This file is the live UI map.

## Do not

- Open SQLite, LanceDB, DuckDB, or BM25 from the UI process.
- Add Chart.js / React / a second CSS framework without an explicit product choice.
- Serve dashboard numbers by scanning `entries` in the browser or in `main.py`.
- Bind-mount `services/ui` in compose as a substitute for rebuild unless you are changing that contract on purpose.
- Recreate `.dev/ui.md` at the `.dev/` root; new UI notes go in this folder.
