# Harvest pool — first landing + live mill miss

**Date:** 2026-09-17
**Scope:** ops / GitHub sidecar + `$N` tap. Not cutover. Not paper exhaust.
**Status:** First landing shipped. Tap is live. Harvest mill is not the locked philosophy.
**Pickup:** `harvest-pool-next.md`. PB-011 (mill loop) then PB-012 (GitHub cutover).

## Verdict

Free harvest is unbounded. Paid judgment is a budget tap. That still holds.

First landing shipped the sidecar, GitHub closed-range writer, 60s release loop, `GET /manifest/count`, dashboard projected $, persist of Search facts. Incremental GitHub still POSTs `DISCOVERED`. HF not rewound.

Harvest was hitchhiked on the incremental scrape tick (90s leftover after all adapters). That was caution, not a requirement. Release correctly got its own 60s loop. Harvest should have too. Do not start GitHub cutover or paper exhaust until the mill is a sibling loop.

## What shipped (as-built)

| Surface | Where |
|---|---|
| Ledger | `${BISHOP_DATA_ROOT}/harvest/ledger.sqlite` — scraper rw, query-api `mode=ro`. Not `bishop.db`. Not `BISHOP_VOLUME_MOUNTS`. |
| Economics | `config/harvest/economics.yaml`. `N_cap=1413` at `$2`. Kill: `BISHOP_HARVEST_DAILY_BUDGET_USD=0`. |
| Harvest writer | `services/scraper/app/harvest_github.py` after adapters in `scrape_cycle` |
| Release tap | `services/scraper/app/harvest_release.py` gathered in `app.main` |
| Count | `GET /manifest/count` (github `DISCOVERED` + `RELEVANCE_QUEUED`) |
| Dashboard | `StatsOverview` harvest_* ; `.dev/ui/harvest-dashboard.md` |
| Persist | typed columns + `extras_json` + `harvest_runs`. Wire DTO stays thin. |

Search 30 req/min. Recursive date split until `total_count` ≤ 1000. A slice with `(end-start).days <= 1` that still overflows is `incomplete_results` and capped at 10 pages / 1000 hits, then the cursor advances. `.days` truncates, so a ~42h window counts as 1 day.

Harvest HTTP client timeout is **30s** (`loop.py`). First live tick `ReadTimeout` on httpx default 5s; incremental scrape was not failed (harvest exceptions are caught).

## Live snapshot (this host, 2026-09-17 ~14:22 UTC)

After rebuild of `state-worker` / `scraper` / `query-api` / `ui`:

- `harvest_pool_size` 2000, `unreleased` 587, `released_today` 1413, `N_cap` 1413, projected **$1.079532**
- Sidecar present. Two `harvest_runs`, both `incomplete_results`, 1000 upserts each (`2024-09-17` → `09-19` total_count 2072; `09-19` → `09-21` 1838)
- Cursor `next_window_start=2024-09-21T02:18:40Z`, `harvest_until=2026-09-17T14:18:40Z` — days into a 2y GitHub walk
- Live scraper env: `BISHOP_HARVEST_ENABLED=1`, `BISHOP_HARVEST_DAILY_BUDGET_USD=2`, `BISHOP_SCRAPER_SCHEDULE_INTERVAL_SEC=21600`. Slice budget is code default **90s** (not in compose).
- N_cap stopped the **tap**, not the pool. Pool stopped because the 90s budget ended and the next harvest waits **6h**.

Do not read a flat pool as “harvest is done” or “N_cap paused harvest.”

## Why harvest was on the scrape tick

Daily ingest must stay live (standing rule). First landing stuffed harvest into leftover scrape-cycle time so Search would not run unbounded beside incremental GitHub. That over-weighted caution. Philosophy already said mill unbounded, drip `$N`. Next landing: third asyncio loop in the scraper process (not a new worker), same sidecar writer, same Search 30/min. Incremental adapters keep their own interval.

## Do not (unchanged)

Paper exhaust into `DISCOVERED`. Dump the sidecar. Widen `ManifestIngestEntry`. Rewind HF. Treat PwC as live. Mechanical drops before the pool mix is visible. UI token fields before PB-002. GitHub-only profile / option 3. Rewrite `BACKFILL_CONFIG`.

## Operator 2026-09-17 (spend / calendar)

A few months to finish the GitHub window is fine. Daily incremental (papers + GitHub today/yesterday) stays up — that is already true and must stay true.

~**100 G1 batches/day** (~$3, ~25M tokens, batched, ~99% cache) is the intended faucet **after** PB-011, not a yaml bump this sitting. Current pin stays `$2` / `N_cap=1413`. Recalibrate `unit_gate1_usd` off a cache-true batch (yaml already says that). All-in at current units for 5000 G1 is closer to ~$4.70 with the paper reserve.

**~356k is 60d `stars:>10`, not 2y.** 2y is the mill (`WINDOW_DAYS=730`), Search-capped per slice. Do not quote 71 days as “2y done.” Order-of-magnitude at 5k/day is a few months.

Other sources: keep live incremental + paper reserve. Sidecar exhaust for papers/LW/OR/SS stays after GitHub mill + cutover. HF no rewind. PwC dead.

Do not implement PB-011 / PB-012 / budget bump in the sitting that logged this. Goal remains: mill loop, then the rest of the deferred list.

## Next sequence

1. **PB-011** — harvest mill loop (GitHub sidecar fill independent of the 6h scrape clock). **Not this sitting.**
2. Optional: raise toward ~100 G1 batches/day (`daily_budget_usd` / env) after a cache-true batch — not before the mill exists.
3. **PB-012** — GitHub incremental cutover (ledger-only harvest; `DISCOVERED` is the tap). Tap already inserts; mill is the remaining gate.
4. Paper/LW/OR/SS exhaust into the sidecar — after GitHub cutover, not before.
5. Mechanical drops / extra rank — after the mix is visible.
