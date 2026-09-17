# Harvest pool — pickup

**Status:** first landing shipped 2026-09-17. Tap is live (`released_today` hit `N_cap`). Harvest mill is still a 90s hitchhiker on the 6h scrape tick — that is a miss, not the philosophy. Incremental GitHub still writes `DISCOVERED`. Not cut over. HF not rewound.

**Next:** PB-011 harvest mill loop, then PB-012 GitHub cutover. Do not start paper exhaust or cutover while the mill sleeps 6h.

**Related:** `.dev/decision-logs/ops/harvest-pool-first-landing.md`, `repo-gate-next.md`, `.dev/decision-logs/ops/soft-launch-precision-overlay.md`, `config/source-notes/github.md`, `.dev/sqlite.md`, `.dev/persist-vendor-payloads.md`, `.dev/ui/harvest-dashboard.md`

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
- Monthly spend is acceptable. `$N/day` is a faucet, not a reason to delay the ledger.
- If a vendor already returned a fact, persist it. Do not log-and-drop.

---

## Locked machine (first landing)

**Ingress C.** GitHub eventually always harvests into the sidecar; `DISCOVERED` is the release tap. Papers/LW/OR/SS stay on today’s `DISCOVERED` path until they have exhaust. HF incremental only. PwC dead.

**This landing does not cut GitHub incremental over.** Scraper still POSTs GitHub `fetch_manifest` into `DISCOVERED`. Harvest fills the ledger in parallel. Cutover is the next landing, once the release loop is visibly inserting.

**Ledger.** Sidecar SQLite `${BISHOP_DATA_ROOT}/harvest/ledger.sqlite`. Not `bishop.db`. Not a new `ProcessingState`. Upsert on `source_id`. Feature store stays in the sidecar; `POST /manifest/batch` stays the thin wire DTO.

**GitHub exhaust.** Closed ranges `pushed:START..END stars:>10`. Recursive date split until `total_count` ≤ 1000 (a slice with `(end-start).days <= 1` that still overflows is recorded `incomplete_results`, capped at 10 Search pages / 1000 hits, then the cursor advances — `.days` truncates, so ~42h counts as 1). Search **30 req/min**. Sibling harvest, not a break of `fetch_manifest(since)`. Cursor in the sidecar, not `scraper_state.last_successful_run_at`.

**Cadence (as-built, wrong vs philosophy).** Harvest runs at the **end** of `scrape_cycle` with `BISHOP_HARVEST_SLICE_BUDGET_SEC` default 90, then waits `BISHOP_SCRAPER_SCHEDULE_INTERVAL_SEC` (live **21600**). Release is a separate 60s loop. First landing over-weighted “don’t interrupt daily ingest.” Next landing: harvest gets its own loop in the same scraper process. Do not treat “time-boxed on the scrape tick” as the intended mill.

**Persist (typed + extras_json + harvest_runs).** GitHub Search already returns id, owner, created/updated/pushed, fork/archived/disabled, language, license, stars/forks/issues/size, topics, homepage, visibility, score. We currently keep title/tagline/url/pushed_at only. Keep the rest. `harvest_runs` stores query, window, `total_count`, `incomplete_results`, pages, rate-limit headers.

**Release.** Second asyncio loop in the scraper process (~60s), not a new worker. Insert ≤50 (`PREFILTER_BATCH_SIZE`) as `DISCOVERED`. Recency is **selection** (rolling 48h `pushed_at`, then older). Pre-filter keeps `ORDER BY discovered_at`. Skip-if-exists still sets `released_at`. `$0` kills the GitHub tap; `compose stop pre-filter-worker` kills all Haiku.

**Economics.** `config/harvest/economics.yaml`. Operator sets `daily_budget_usd` (default 2.00). Env `BISHOP_HARVEST_DAILY_BUDGET_USD` overrides (kill = 0).

```
blended_github = 0.0005 + 0.022 * 0.012 = 0.000764
paper_reserve  = 400 * 0.0005 + 400 * 0.15 * 0.012 = $0.92
N_cap          = floor((2.00 - 0.92) / 0.000764) = 1413
N_remaining    = min(N_cap - released_today, max(0, N_cap - github_in_queue))
```

`github_in_queue` = `GET /manifest/count` for github in `DISCOVERED` + `RELEVANCE_QUEUED`. Until cutover, incremental can already fill that queue; the tap adds zero when `used >= N_cap`.

**Dashboard.** Projected spend on `StatsOverview` (query-api reads harvest sidecar `mode=ro` + economics.yaml). Not live Anthropic usage (PB-002).

**Census** is `harvest_runs` plus an optional cheap `total_count` pass. Not a code gate. 60d GitHub `stars:>10` is already ~356k.

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

- **Harvest mill loop (PB-011) — next.** Hitchhiker on the scrape tick starves the 2y GitHub walk. Same process, new asyncio loop, not a new worker.
- GitHub cutover (PB-012) — after the mill is filling. Tap already inserts. Do not cut incremental over while harvest only moves every 6h.
- Paper/LW/OR/SS exhaust — would dump Haiku if it went to `DISCOVERED`. After GitHub cutover, into the sidecar.
- Mechanical drops / extra rank at release — persist now, use after we see the mix.
- Live Anthropic `$` on `batches` — PB-002. Poller already parses usage and only logs it. See `.dev/persist-vendor-payloads.md`.

## Live snapshot (this host, 2026-09-17 ~14:22 UTC)

Do not re-probe to “confirm” these; they age. Re-read `GET /stats/overview` + sidecar `harvest_cursor` / `harvest_runs`.

- Pool 2000 / unreleased 587 / released_today 1413 (= `N_cap`) / projected $1.08. Tap full. Mill not done.
- Two incomplete GitHub Search windows (~Sep 17–21 2024), 1000 upserts each. Cursor still `2024-09-21` of `harvest_until` 2026-09-17.
- `N_cap` did not pause harvest. The 90s budget + 6h scrape clock did.

---

## First landing files

- `config/harvest/queries.yaml`, `config/harvest/economics.yaml`
- `bishop_shared` harvest ledger + economics parse
- scraper: closed-range harvest writer + 60s release loop; compose harvest volume
- state-worker: `GET /manifest/count`
- query-api + UI: harvest fields on `StatsOverview`, dashboard card; harvest volume `mode=ro`
- tests: economics worked example, upsert/release, count endpoint, stats zeros if sidecar missing, compose volume matrix
