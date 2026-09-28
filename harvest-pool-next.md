# Harvest pool — pickup

**Status:** first landing shipped 2026-09-17. Tap is live (`released_today` hit `N_cap`). Harvest mill now has its own asyncio loop in the scraper process (`_mill_loop`) — see `.dev/decision-logs/ops/harvest-mill-loop.md`. Incremental GitHub still writes `DISCOVERED`. Not cut over. HF not rewound.

**Next:** PB-012 GitHub cutover, after the mill is filling. Daily ingest stays up. A few months at ~100 G1 batches/day is an acceptable mine. Do not start paper exhaust.

**Related:** `.dev/decision-logs/ops/harvest-mill-loop.md`, `.dev/decision-logs/ops/harvest-pool-first-landing.md`, `.dev/decision-logs/ops/2026-09-27-operator-ingest-pages.md`, `repo-gate-next.md`, `.dev/decision-logs/ops/soft-launch-precision-overlay.md`, `config/source-notes/github.md`, `.dev/sqlite.md`, `.dev/persist-vendor-payloads.md`, `.dev/ui/harvest-dashboard.md`, `.dev/ui/scrape.md`

---

## Intent

**Free harvest is unbounded. Paid judgment is a budget tap.**

Discover as far back as we want (years, not days) on the canonical sources. Persist every candidate for idempotency. Rank the pool. Release into the existing LLM gates only as daily budget allows. Stop the tap without stopping harvest.

Do not dump the pool into `DISCOVERED`. Today that state means “pre-filter will take you.”

---

## Standing operator rule (not only this feature)

- Today and yesterday stay live. Do not take down daily ingest to mine a backlog.
- Recency first, then the pool. Keep Haiku cache warm; work in batches.
- Measure (and mine) the current high-signal set before adding sources.
- Monthly spend is acceptable. A few months to walk the GitHub window is fine. Operator 2026-09-17: ~**100 G1 batches/day** (~$3, batched, mostly cache hits) is a good faucet once PB-011 exists — do not raise `daily_budget_usd` in this sitting. Daily incremental stays live.
- If a vendor already returned a fact, persist it. Do not log-and-drop.

---

## Locked machine (first landing)

**Ingress C.** GitHub eventually always harvests into the sidecar; `DISCOVERED` is the release tap. Papers/LW/OR/SS stay on today’s `DISCOVERED` path until they have exhaust. HF incremental only. PwC dead.

**This landing does not cut GitHub incremental over.** Scraper still POSTs GitHub `fetch_manifest` into `DISCOVERED`. Harvest fills the ledger in parallel. Cutover is the next landing, once the release loop is visibly inserting.

**Ledger.** Sidecar SQLite `${BISHOP_DATA_ROOT}/harvest/ledger.sqlite`. Not `bishop.db`. Not a new `ProcessingState`. Upsert on `source_id`. Feature store stays in the sidecar; `POST /manifest/batch` stays the thin wire DTO.

**GitHub exhaust.** Closed ranges `pushed:START..END stars:>10`. Recursive date split until `total_count` ≤ 1000 (a slice with `(end-start).days <= 1` that still overflows is recorded `incomplete_results`, capped at 10 Search pages / 1000 hits, then the cursor moves — `.days` truncates, so ~42h counts as 1). Search **30 req/min**. Sibling harvest, not a break of `fetch_manifest(since)`. Cursor in the sidecar, not `scraper_state.last_successful_run_at`.

**Direction (2026-09-27).** The mill now walks **backward**. Floor stays in `next_window_start` (live floor `2024-12-15`). `harvest_until` retreats from true now toward that floor. `walk_direction=backward` and `high_water=<flip now>` are the marker. Overflow takes the newer half first. When the high edge meets the floor, both edges restore to `high_water` and `walk_direction=forward` so new days still get the bump-until tail. Do not run the old scraper image on this cursor: it would walk December 2024 forward and raise the floor. Write-up: `.dev/decision-logs/ops/2026-09-27-harvest-mill-backward.md`. Ad hoc: `catch_up_ad_hoc.md`.

**Cadence (as-built, wrong vs philosophy).** First landing: harvest ran at the **end** of `scrape_cycle` with `BISHOP_HARVEST_SLICE_BUDGET_SEC` default 90, then waited `BISHOP_SCRAPER_SCHEDULE_INTERVAL_SEC` (live **21600**). Release is a separate 60s loop. First landing over-weighted “don’t interrupt daily ingest.” **Mill loop landed 2026-09-17** — harvest is no longer coupled to `BISHOP_SCRAPER_SCHEDULE_INTERVAL_SEC`. See `.dev/decision-logs/ops/harvest-mill-loop.md`.

**Persist (typed + extras_json + harvest_runs).** GitHub Search already returns id, owner, created/updated/pushed, fork/archived/disabled, language, license, stars/forks/issues/size, topics, homepage, visibility, score. We currently keep title/tagline/url/pushed_at only. Keep the rest. `harvest_runs` stores query, window, `total_count`, `incomplete_results`, pages, rate-limit headers.

**Release.** Second asyncio loop in the scraper process (~60s), not a new worker. Insert ≤50 (`PREFILTER_BATCH_SIZE`) as `DISCOVERED`. Recency is **selection** (rolling 48h `pushed_at`, then older). Pre-filter keeps `ORDER BY discovered_at`. Skip-if-exists still sets `released_at`. `$0` kills the GitHub tap; `compose stop pre-filter-worker` kills all Haiku.

**Economics.** `config/harvest/economics.yaml`. Operator sets `daily_budget_usd` (default 2.00). Env `BISHOP_HARVEST_DAILY_BUDGET_USD` overrides (kill = 0).

```
blended_github = 0.0005 + 0.022 * 0.012 = 0.000764
paper_reserve  = 400 * 0.0005 + 400 * 0.15 * 0.012 = $0.92
N_cap          = floor((2.00 - 0.92) / 0.000764) = 1413
N_remaining    = min(N_cap - released_today, max(0, N_cap - github_in_queue))
```

**Live override.** Yaml pin stays `$2` / `N_cap=1413`. Env wins.

- 2026-09-26: `BISHOP_HARVEST_DAILY_BUDGET_USD=11.72` → `N_cap=14136` (~10×). Reason: back from caba, server out ~4 days. That cap filled on UTC 2026-09-27 (ledger 14,186 released; card sat on 14,136).
- 2026-09-27: env `4.52` → `N_cap=4712` (`floor((4.52 - 0.92) / 0.000764)`), about a third of 14,136. Catch-up is done; Anthropic credits ran out around 03:00 UTC and were refilled later. Because `released_today` is already above 4712, the tap stays shut until the next UTC midnight, then 4712/day.

Report: `catch_up_ad_hoc.md`. Write-up: `.dev/decision-logs/ops/2026-09-26-ncap-caba-override.md`.

`github_in_queue` = `GET /manifest/count` for github in `DISCOVERED` + `RELEVANCE_QUEUED`. Until cutover, incremental can already fill that queue; the tap adds zero when `used >= N_cap`.

**Operator pages.** `/harvest` is the mill + faucet (`GET /stats/harvest`: unreleased × blend, walk forecast, `N_cap`). `/scrape` is incremental cursors (`GET /stats/scrape`). `/today` is the UTC-day glance (`GET /stats/today`). Dashboard keeps pipeline cards. Not live Anthropic usage (PB-002). Do not put harvest cards back on `/dashboard`. Days-to-drain on `/harvest` is `ceil(unreleased / N_cap)` if the mill adds nothing. That is the stopped-mill figure, not a forecast of a growing pool (F-003, `.dev/insights-manager/runs/2026-09-27-r001.md`).

**Census.** `harvest_runs` plus optional cheap `total_count`. **~356k is 60 days** of `stars:>10`, not the 2y mill. 2y is closed-range and Search-capped (busy day ≤1000); size is unknown until the mill walks it. At ~5000 G1/day a 2y walk is **a few months**, which is accepted. Do not write 71 days as if 356k were the 730-day pool.

---

## Do not

- Insert the full harvest into `DISCOVERED` / `manifest` as a one-shot.
- Treat `DISCOVERED` as the ledger.
- Widen `ManifestIngestEntry` for stars/language/fork.
- Commit candidate rows into git.
- Raise `stars:>50` as the slop filter.
- Rewind Hugging Face.
- New worker / new cache key / GitHub-only profile.
- Rewrite `BACKFILL_CONFIG`. Overlay env stays overlay.
- A second LLM pre-pre-filter. Mechanical drops wait until after we can see the pool.
- Cut GitHub incremental to ledger-only in this landing.
- Hard-cap enrichment workers.
- Invent UI token fields before PB-002 schema.

---

## Deferred (with cause)

- GitHub cutover (PB-012) — after the mill is filling. Tap already inserts. Do not cut incremental over while harvest only moves every 6h. Also gated on tap yield (F-001, run r001): tap days 2026-09-17, 09-18, and 09-26 reached INDEXED on 2/4,976 rows (0.04%) versus incremental GitHub 14/1,909 (0.73%). Cutover replaces the higher-yield path. Before this leaves deferred, run Q-001 (`queries/e2_github_tap_split.py`) on 5+ settled, uptime-clean tap days under `N_cap` 4712. The open investigation is harvest `stars:>10` pushed-window versus incremental `fetch_manifest`. Same pin. Registry: `.dev/insights-manager/findings.yaml`.
- Paper/LW/OR/SS exhaust — would dump Haiku if it went to `DISCOVERED`. After GitHub cutover, into the sidecar.
- Mechanical drops / extra rank at release — persist now, use after we see the mix.
- Live Anthropic `$` on `batches` — PB-002. Poller already parses usage and only logs it. See `.dev/persist-vendor-payloads.md`.

## Live snapshot (this host, 2026-09-17 ~14:22 UTC)

Do not re-probe to “confirm” these; they age. Re-read `GET /stats/harvest` + sidecar `harvest_cursor` / `harvest_runs` (glance fields also on `GET /stats/overview`). Incremental lag is `GET /stats/scrape`, not the harvest cursor.

- Pool 2000 / unreleased 587 / released_today 1413 (= `N_cap`) / projected $1.08. Tap full. Mill not done.
- Two incomplete GitHub Search windows (~Sep 17–21 2024), 1000 upserts each. Cursor still `2024-09-21` of `harvest_until` 2026-09-17.
- `N_cap` did not pause harvest. The 90s budget + 6h scrape clock did.

---

## First landing files

- `config/harvest/queries.yaml`, `config/harvest/economics.yaml`
- `bishop_shared` harvest ledger + economics parse
- scraper: closed-range harvest writer + 60s release loop; compose harvest volume
- state-worker: `GET /manifest/count`
- query-api + UI: `GET /stats/harvest` + `/harvest` page; glance fields on `StatsOverview`; harvest volume `mode=ro`
- tests: economics worked example, upsert/release, count endpoint, stats zeros if sidecar missing, compose volume matrix
