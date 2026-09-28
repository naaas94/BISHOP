# Scrape page

`GET /scrape` is the incremental ingest surface. query-api `GET /stats/scrape` reads `scraper_state` and today’s `manifest.discovered_at` from `bishop.db` (`mode=ro`). Headline is the worst live-source lag vs now (`last_successful_run_at`). Papers with Code is dead and does not set the headline. Stale is lag greater than two scrape ticks.

Cadence on the page follows scraper env, passed through **query-api** compose: `BISHOP_SCRAPER_SCHEDULE_INTERVAL_SEC` (default 21600), `BISHOP_BACKFILL_WINDOW_OVERRIDE_DAYS` (live overlay 60), `BISHOP_BACKFILL_ENABLED`. Per-source pin windows stay `BACKFILL_CONFIG`. After adding those keys, recreate query-api (`docker compose up -d query-api`); rebuild-only leaves the old env.

GitHub incremental still writes `DISCOVERED`. The mill and tap are `/harvest`. Hugging Face is incremental only and was not rewound. GitHub `discovered_today` on this page mixes incremental POSTs and harvest-tap releases — it is not mill walk progress. The GitHub row prints harvest `released_today` next to `today` so the tap share is visible.

UTC-day volume and scrape health glance live on `/today`. This page keeps cursors, lag bars, overlay, and `last_successful_run_at`. A one-liner links `N discovered · queue Q` to `/today`. Rebuild `query-api` and `ui` after edits.

Live 2026-09-27: the 12:21 UTC stamp (`2026-09-27T12:21:08Z`, 2,211 rows for 17–24 Sep) was a jump. Earlier overlay days are still partial (9 Sep 104/307, 16 Sep 0/338). The scraper now walks one UTC day at a time from the 60-day floor and stamps 23:59:59 of each finished day. A green bar only means the cursor moved. Prefer `GET /stats/scrape`. Write-up: `.dev/decision-logs/ops/2026-09-27-arxiv-export-stuck.md`.

Doctrine: `.dev/decision-logs/ops/2026-09-27-operator-ingest-pages.md`.
