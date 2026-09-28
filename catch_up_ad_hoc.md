# Catch-up ad hoc — 2026-09-26 / 2026-09-27

Operator note for the next person (human or agent) who touches the GitHub tap, the Haiku bill, or the harvest pool. Screenshots are the Anthropic console. Row counts are from this host, read after the burst and before the faucet was lowered.

**Live faucet after this note:** `BISHOP_HARVEST_DAILY_BUDGET_USD=4.52` → `N_cap=4712`. Yaml pin is still `$2` / `1413`. Env wins.

## Timeline (UTC)

| When | What |
|---|---|
| 2026-09-17 | Harvest tap landed. `N_cap=1413` at `$2`. Mill cursor was 2024-09-21. |
| 2026-09-22 .. 25 | Server out (~4 days, operator back from CABA). Console usage is a flat zero. |
| 2026-09-26 ~23:25 | Env raised to `$11.72` so `N_cap=14136` (~10×). Reason recorded as the outage catch-up. |
| 2026-09-26 23:14–23:59 | Tap releases 2,150 ledger rows. Pre-filter judges ~2,100 of them. |
| 2026-09-27 00:00–03:00 | Pre-filter runs hot: ~2,850 rows/hour, then ~1,700 in the 03:00 hour. Console tokens match. |
| 2026-09-27 ~03:00 | Batch path stops. One `pre_filter` batch is `failed` (50 rows). `error_log` has no rows for this window. Operator: the ~$6 credit balance ran out. |
| 2026-09-27 03:00–04:58 | **The tap keeps releasing.** Anthropic being empty does not stop `harvest_release`. Ledger `released_at` continues until 04:58. |
| 2026-09-27 ~05:00 | 6h scrape tick: Hugging Face, LessWrong, and a smaller GitHub increment. Mill cursor advances to `2024-12-10`. |
| 2026-09-27 ~09:00 | Credits refilled. Pre-filter resumes on rows already in `DISCOVERED`. Console shows a small 09:00 bar. |
| 2026-09-27 ~09:35 | This note. Faucet set to about a third of the catch-up cap. |

Local clock is Argentina (UTC−3). 03:00 UTC is midnight local. 09:00 UTC is 06:00 local.

## What the 10× tap actually released

It did not replay the four missed days of fresh ingest. It emptied the harvest pool in `pushed_at` order, and that pool is still a late-2024 walk.

Ledger `${BISHOP_DATA_ROOT}/harvest/ledger.sqlite` (`C:/Users/Ale/bishop_data/harvest/ledger.sqlite`), `mode=ro`:

| Released window | Rows | `pushed_at` |
|---|---|---|
| 2026-09-26 23:14–23:59 | 2,150 | 2,134 in the 2024 pool; 16 in 2026; **1** inside 48h |
| 2026-09-27 00:00–04:58 | 14,186 | **all** 2024-10 .. 2024-12. Zero in 2026. Oct 2,862 / Nov 10,724 / Dec 600 |

Release rule is “48h `pushed_at` first, then older.” The 48h bucket was empty because the mill has not harvested 2025–2026. Cursor at write time: `next_window_start=2024-12-10T14:18:40Z`, `harvest_until=2026-09-17T14:18:40Z`, `updated_at=2026-09-27T05:32:48Z`. Newest pool rows are early December 2024, so “recency” meant November 2024.

Pool after the dump: **35,157** candidates, **11,756** still unreleased. Last mill slices were `pushed:2024-12-05..10 stars:>10`, `incomplete_results=1`, capped at Search pages.

Dashboard at the same sitting (`GET /stats/overview`): `harvest_released_today=14136`, `harvest_n_cap=14136`, `harvest_projected_usd_today=10.799904`, `harvest_unreleased=11756`. The card and the ledger differ by **50**, one release batch: the cap check and the stamp are not the same instant.

## What Haiku actually did

Live DB is `C:/Users/Ale/bishop_data/sqlite_live/bishop.db` (compose mounts `sqlite_live`, not `sqlite/`). `sqlite/bishop.db` on this host is a stale file whose newest batch is 2026-09-11. Do not diagnose from that file.

`batches.created_at`, complete `pre_filter` only:

| UTC hour | Batches | Rows | `passed_count` | `failed_count` |
|---|---|---|---|---|
| 09-26 23:00 | 42 | 2,100 | 35 | 2,065 |
| 09-27 00:00 | 57 | 2,850 | 12 | 2,838 |
| 09-27 01:00 | 57 | 2,850 | 20 | 2,830 |
| 09-27 02:00 | 55 | 2,750 | 11 | 2,739 |
| 09-27 03:00 | 34 | 1,700 | 3 | 1,697 |
| 09-27 09:00 | 11 | 550 | 4 | 546 |
| **Complete sum** | **256** | **12,800** | **85** | **12,715** |

Pass rate on completed Gate 1: **85 / 12,800 = 0.66%**. Batch size is the live default 50. The 03:00 hour is short because credits died mid-hour. Also sitting at probe time: a few `submitted` / `processing` batches (the 09:00 resume) and one `failed` batch at 03:00.

Enrichment during the whole window: **one** Call 1 and **one** Call 2, both at 09-26 23:00, 13 rows, both complete. The bill is Gate 1 rejects.

`manifest` rows with `discovered_at >= 2026-09-26`, by current state:

| Source | Rejected | Discovered (not judged yet) | Queued | Parked | Scraped | Indexed |
|---|---|---|---|---|---|---|
| github | 12,372 | 4,926 | 150 | 56 | 9 | 4 |
| huggingface | 308 | 284 | 0 | 1 | 0 | 0 |
| lesswrong | 35 | 4 | 0 | 15 | 0 | 0 |

GitHub discoveries by hour are ~2,850 from 00:00 through 04:00, then 573 at 05:00. Hours 04:00 and 05:00 have discoveries and **no** pre-filter batches. That is the tap (and then the scrape tick) writing `DISCOVERED` while Haiku was down.

`error_log` from 2026-09-21 onward: **empty**. Credit exhaustion did not leave an error row. The only trace is `batches.status='failed'` on that one 50-row pre-filter batch.

## Console (screenshots the operator pasted)

Anthropic usage, workspace All, dates UTC. Grouped by token type. Model in the cache panels is Claude Haiku 4.5. Prices below are the batch prices already used in `.dev/decision-logs/ops/2026-09-15-day-performance.md` (cache read `$0.05` / MTok, 1h write `$1.00`, uncached input `$0.50`, output `$2.50`). They match these tooltips within rounding.

### Totals

| Window | Tokens in | Tokens out | Cost |
|---|---|---|---|
| Last 7 days (through ~09-27 09:00) | 90,122,607 | 1,087,558 | **$8.18** |
| Last 30 days | 256,554,317 | 3,345,372 | (no cost screenshot) |
| UTC 2026-09-27 | 62,032,217 | 755,166 | **$5.11** |
| UTC 2026-09-26 | (bar ~12M, mostly read) | (part of the 1.09M) | **$1.23** |
| UTC 2026-09-21, implied | residual of the 7-day bill | | **~$1.84** |

Sep 22, 23, 24, 25 are zero on both the 7-day and the 30-day charts. That is the outage, not a cache miss.

Sep 27 tooltip: input `$0.15`, 1h cache write `$0`, cache read `$3.11`, output `$1.86`, billed `$5.11`.

| Piece | Dollars | Share of $5.11 | Implied tokens at batch prices |
|---|---|---|---|
| Cache read | 3.11 | 61% | ~62.2M (`3.11 / 0.05e-6`) |
| Output | 1.86 | 36% | ~0.74M (`1.86 / 2.50e-6`); chart says 755,166 |
| Uncached input | 0.15 | 3% | ~0.30M |
| 1h cache write | 0.00 | 0% | under a cent, so the tooltip shows $0 |

`$3.11` of cache read is the same order as the 62.0M “tokens in” on the single-day chart. The day is a cache-read day. Output is 1.2% of tokens and 36% of dollars.

Sep 26 tooltip: input `$0.06`, 1h write `$0.14`, cache read `$0.63`, output `$0.39`, billed `$1.23`. The `$0.14` write is ~140k tokens at `$1/MTok` — a cold start, then the 27th rode it.

7-day caching panel (as of 09-27 03:00, updates hourly): uncached input **499K** (−68% vs prior 7 days), cache read **88.4M**, cache read ratio **99.4%**, Haiku 4.5 row **89M** input, read ratio **99.4%**, write amortization **132.8×**. Composition bar is almost entirely cache read. 5-minute writes do not appear.

Write-amortization chart (reads per write, log scale): Sep 21 sits around a few ×10 and fades toward ~10× as that day’s writes age. The line is absent across the outage. Sep 27 03:00 on a **6h** window is **574×**. The **24h** window is climbing toward ~1,000× at the right edge, because the cold-start writes are leaving the window while the reads stay.

Hourly Sep 27 token bars: ~17M at 00:00, 01:00, and 02:00, ~10M at 03:00, nothing until a ~1M bar at 09:00. 2,850 rows × a ~5.5k cached prefix is ~15.7M, which is the 17M bar once tails are included. The shape is “full batches, then a credit cliff,” not a cache cliff.

30-day shape, for context only: Sep 10–12 are mostly uncached input (orange on that chart’s legend). From Sep 14 the bars are cache reads. Sep 15–21 are the ~10–30M/day regime from the earlier spend note (~$3 on the rewind day). Sep 27 is ~60M in a few hours, about four ordinary days of tokens, spent on the 2024 pool.

### Observed unit vs the pin

Completed Gate 1 through the credit cliff (00:00–03:00, 11,150 rows) against the `$5.11` day bill is about **$0.00046 per judged row**. The pinned `unit_gate1_usd` is `$0.0005`. The dashboard projected **$10.80** (`14136 × $0.000764`) for a day whose Anthropic bill was **$5.11**. The pin is conservative on a hot cache. It is not wildly wrong. Do not retune it from this one burst; the `$0.000764` blend still includes a paper reserve and an enrichment rate this day did not spend.

`paper_daily_g1_reserve` of 400 did not show up as paper volume. Hugging Face was a few hundred rows at the scrape ticks. LessWrong was dozens.

## Why it stopped, and what the new credits will pay for

Two clocks:

1. **Haiku** stopped ~03:00 UTC because the credit balance hit zero. Refill ~09:00 UTC. Pre-filter woke up and started the backlog.
2. **The tap** stopped ~04:58 UTC because `released_today` hit `N_cap`. It does not look at Anthropic.

Still waiting on Gate 1 from this wave: **4,926** GitHub `DISCOVERED` + **150** `RELEVANCE_QUEUED`, plus **284** Hugging Face `DISCOVERED`. At the burst’s ~$0.00046/row that queue is on the order of **$2–2.5** if it all gets judged. The new credits drain that queue whether or not the tap is open. Lowering `N_cap` does not cancel `DISCOVERED`.

Incremental GitHub still POSTs `DISCOVERED` on the scrape cycle (cutover is PB-012). The 05:00 hour’s 573 GitHub rows are consistent with that path. `N_cap` does not cover it.

## Faucet now

`N_cap = floor((daily_budget − 0.92) / 0.000764)`.

| Budget | N_cap | Note |
|---|---|---|
| `$2.00` | 1413 | yaml pin, unchanged |
| `$11.72` | 14136 | catch-up, filled |
| `$4.52` | **4712** | **current env.** 4712 / 14136 = 1/3 |

`$11.72 / 3 = $3.91` is a third of the dollars and a smaller cap, because `$0.92` stays reserved for papers. The operator asked for the faucet at about a third. The cap is the faucet, so the env is `$4.52`.

`remaining_slots` is `min(N_cap − released_today, N_cap − github_in_queue)`, floored at 0. `released_today` is already ~14k, so **the tap inserts nothing more on UTC 2026-09-27**. Next open is 2026-09-28 00:00 UTC (21:00 ART on the 27th), at 4,712 rows.

Unreleased pool 11,756 at this cap is about **2.5 days**, and the mill is still only in December 2024. A full UTC day at 4,712 of this same slice, at $0.00046/row, is about **$2.2** of Haiku plus whatever the scrape tick adds outside the cap.

## Improvement signals

Ordered by how much they would change the next dollar. Each one is checkable.

1. **The pool’s “fresh” sort is fresh-inside-2024.** Until `harvest_cursor` reaches 2026, every raised cap judges `stars:>10` history. This burst indexed **4** GitHub rows and parked **56**, with 0.66% Gate 1 passes. Compare to the 2026-09-15 rewind day (mixed sources, 5.4% Gate 1 pass, 52 INDEXED) before calling the gate “stricter” or “broken.” The slice changed. A useful next measurement is pass rate split by `pushed_at` year, not another budget bump.

2. **Credits are the real kill switch. `N_cap` is not.** The judge died at 03:00 and the tap ran until 05:00. `error_log` stayed empty. If a credit wall should pause the release loop, that pause does not exist. If a failed batch should be visible, this one is only `batches.status='failed'`.

3. **Output is the expensive leftover inside a hot cache.** 36% of the Sep 27 dollars, 1.2% of the tokens, ~59 output tokens per Gate 1 row (`755166 / 12800`). Cache read is doing its job (99.4%, 574× on the burst, 132.8× on the 7-day panel). Shrinking the rationale is the spend lever that does not throw away the cache. Raising batch size further will not move a 574× day.

4. **Dashboard projected `$` is `released_today × $0.000764`.** It read `$10.80` while Anthropic billed `$5.11`. After this change the card can show a budget of `$4.52` and a projected figure still near `$10.80` until UTC midnight, because projected spend follows rows already released. PB-002 (persist `message.usage` on `batches`) is still the hole that made this note depend on screenshots.

5. **One failed batch, no `error_log` row.** Worth a look the next time someone is in the poller. Do not invent a retry policy from this note.

6. **Mill slices are still `incomplete_results`.** Latest runs upserted 500–1,000 of `total_count` 1,047–2,057 and advanced the cursor anyway. That behavior is the closed-range cap (10 pages). It is not new. It does mean the pool is a sample of busy days, not the full `stars:>10` set. Ranking or yield math on “the 2024 pool” should remember that.

## Easy misreads

- A flat console day during Sep 22–25 is the machine being off.
- Sep 27’s 60M tokens is four ordinary days compressed, aimed at November 2024, not proof that steady state is now 60M/day.
- `N_cap` 4712 with `released_today` 14136 means “tap closed until tomorrow,” not “the cap is broken.”
- Write amortization going to 574× means the cache was already warm. It does not mean writes are free forever; a cold hour still showed `$0.14` on Sep 26.
- `C:/Users/Ale/bishop_data/sqlite/bishop.db` is not the live database.

## Flip — mill walks backward (2026-09-27)

The forward walk is why the catch-up judged November 2024. The mill now starts at true now and retreats toward the already-walked floor. Daily scrape, release SQL, `$4.52`, and `N_cap=4712` were left alone. Implemented by [Flip harvest mill backward](cfbd797f-9d11-4e31-938a-ab3ca72cf6c7). Tests: 20 passed. Scraper image rebuilt (`bishop/scraper:m8`); the rest of the stack was left up.

### How to tell

Read `harvest_cursor` on `C:/Users/Ale/bishop_data/harvest/ledger.sqlite` and the latest `harvest_runs.query`.

| Column | During the backward gap |
|---|---|
| `next_window_start` | Floor. Frozen. Live value `2024-12-15T20:18:40Z` (it had already moved past 2024-12-10 before the flip). |
| `harvest_until` | High edge. Steps **down** after each persisted slice. |
| `walk_direction` | `backward` |
| `high_water` | Flip instant. Live `2026-09-27T10:07:56Z`. Not updated on later slices. |

First persisted query after the flip: `pushed:2026-09-25..2026-09-27 stars:>10` (run id 52, `total_count` 68040, 10 pages, 964 upserts). The probe was the wider `2026-09-20..2026-09-27`; overflow took the newer half. Next probes should keep the end date moving earlier. A query still on `2024-12-*` means the old image is running.

When `harvest_until` meets the floor, both edges are set back to `high_water` and `walk_direction` becomes `forward`. After that, the old “bump the ceiling to now and walk the new days” tail covers time that arrives later. Pool rows are not deleted.

### Why the marker exists

The old loop only knows “start here, add 7 days.” Editing the two timestamps and restarting would not reverse it. And if every process start did `harvest_until = now` whenever the high edge was behind the clock, the mill would re-walk this week forever and never reach 2025.

So the legacy row flips **once**: `walk_direction` was NULL, `next < until`, so the code set `harvest_until = now`, `high_water = now`, `walk_direction = backward`, and left the floor put. A later restart sees `backward` and continues from the retreated high edge. Columns are added with `PRAGMA table_info` plus `ALTER TABLE` (`CREATE TABLE IF NOT EXISTS` does not widen the live sidecar). Code: `bishop_shared/harvest_ledger.py` (`_ensure_cursor_walk_columns`, `set_cursor`) and `services/scraper/app/harvest_github.py` (`_harvest_into`).

### What this does to the tap

Release is still 48h `pushed_at` first, then older `pushed_at` descending. 2026 rows land in the pool ahead of the ~11k unreleased 2024 rows. The 10-page Search cap is unchanged: a late-2026 day with 68k hits still keeps about 1,000 repos and moves on. That sample is newest-updated inside the window, which is the valuable end, and it is still a sample.

Do not roll the scraper image back onto this cursor. Old code would see floor in 2024 and ceiling in 2026 and walk December 2024 forward again, raising the floor through the gap.

### Code map

- `services/scraper/app/harvest_github.py` — flip once, backward window `[max(floor, until-7d), until]`, newer-half overflow, retreat `harvest_until` to the slice start, done-state writes both edges to `high_water`.
- `bishop_shared/harvest_ledger.py` — `walk_direction`, `high_water`, idempotent ALTER.
- `tests/test_harvest_github.py` — legacy first tick ends at now and does not raise the floor; second tick is the next-older window; restart does not jump the high edge to now; overflow newer-half first; one-day overflow caps pages and retreats; harvest still does not POST DISCOVERED.
- `tests/test_harvest_ledger.py` — `test_cursor_walk_columns_alter_is_idempotent`.
- Write-up: `.dev/decision-logs/ops/2026-09-27-harvest-mill-backward.md`.

## Files touched with the faucet

- Host `.env`: `BISHOP_HARVEST_DAILY_BUDGET_USD=4.52` (gitignored).
- `config/harvest/economics.yaml` comment only. `daily_budget_usd` stays `2.00`. Tests still expect `n_cap == 1413` when the env is unset.
- Recreate `scraper` and `query-api`. No image rebuild.
- Decision log: `.dev/decision-logs/ops/2026-09-26-ncap-caba-override.md` (follow-up section).
