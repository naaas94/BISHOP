# Operator ingest pages — dashboard glance vs Scrape / Harvest / Today

**Date:** 2026-09-27
**Scope:** UI + query-api stats. Not mill direction, not GitHub cutover, not PB-002.
**Status:** `/scrape`, `/harvest`, and `/today` live. Dashboard pipeline cards kept.
**Pickup:** `.dev/ui/agent-reference.md`. Notes: `.dev/ui/scrape.md`, `.dev/ui/harvest-dashboard.md`, `.dev/ui/today.md`.

## Verdict

Dashboard is pipeline health. Each ingest path gets its own page.

| Surface | Headline | Source of truth |
|---------|----------|-----------------|
| `/dashboard` | Funnel, queues, relevance, batches | `GET /stats/overview` |
| `/today` | UTC-day glance | `GET /stats/today` ← `manifest.discovered_at` ≥ UTC midnight |
| `/scrape` | Worst live cursor lag | `GET /stats/scrape` ← `scraper_state.last_successful_run_at` |
| `/harvest` | Unreleased modeled liability | `GET /stats/harvest` ← harvest sidecar + `economics.yaml` |

Glance fields may sit on `StatsOverview` (lag hours, unreleased `$`, tap open/closed, today discovered). Full payload stays on the dedicated route. Do not put harvest, scrape, or today card grids back on the dashboard.

`/scrape` is incremental `DISCOVERED` into `bishop.db` (cursors, lag, overlay). `/harvest` is the GitHub mill + `$N` tap (walk, pool, full faucet). `/today` is the UTC-day glance of both (same midnight as scrape `discovered_today` and harvest `released_today`) — scrape health + harvest one-liner, not the specialist tables. They are siblings, not two views of one cursor.

## Easy to get wrong

- **Query-api env.** Overlay, scrape interval, and harvest budget must be in the **query-api** compose `environment:` block, not only scraper / `.env`. After adding keys, `docker compose up -d query-api` so the container is recreated. Rebuild-only leaves the old env.
- **Two rebuilds.** `bishop/ui:m8` bakes templates and CSS. Stats JSON lives in query-api. Touch both, then recreate.
- **Two GitHub paths.** `/scrape` github row is `last_successful_run_at` on the incremental adapter. Mill progress is the sidecar cursor on `/harvest`. GitHub `discovered_today` on `/scrape` mixes incremental POSTs and tap releases.
- **Harvest `$`.** Headline is `unreleased × blended_github_usd` (`$0.000764`). `released_today × blend` is today’s faucet, not the pool. Four decimal places on the blend reads `$0.0008` — use six.
- **PwC.** Dead. Does not set the scrape headline. Stale = lag greater than two scrape ticks. Papers with Code is excluded from “worst live.”
- **Walk forecast.** Complete `harvest_runs` in the walked recent span only. Search-capped incomplete windows are counted, not used as rates. Fewer than 3 complete windows → “forecast waiting.” `N_cap` full is the tap, not the mill.

## What did not change

Pipeline cards on `/dashboard`. Incremental GitHub still writes `DISCOVERED`. HF not rewound. PwC dead. PB-002 (live Anthropic usage on `batches`) still not built — `/harvest` dollars are the pinned blend.
