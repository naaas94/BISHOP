# Glossary

Load-bearing language for every Insights Manager question. Carried forward from `REPORTING.md` and amended by the 2026-09-27 review (R1, R2, R3, R12). If a run needs a term that isn't here, add it here first.

## The four slots

Every question is `{population, window, success, grain}`.

- **Population** — which rows. Name the source *and* the path (e.g., "GitHub, tap-released", not "GitHub").
- **Window** — which clock (below) and which UTC bounds. Half-open: `>= start AND < end`.
- **Success** — one event from the partition below. Not "passed", unless you mean gate-1 yes.
- **Grain** — the group-by (source × UTC day, path × day, tier).

## Stocks, flows, cohorts

- **Stock** — the count sitting in a state now (`DISCOVERED` = 16k). This is what the `/dashboard` funnel shows. Not this function's job.
- **Flow** — the count that entered a state in a window.
- **Cohort** — rows sharing a window on one clock, followed forward to their current state. `/today` shows today's cohort *today*, mid-flight. A cohort run shows it settled.
- **Settled** — a cohort with 0 undecided and 0 in flight. On 2026-09-15, max discovered-to-Call-2 was 17.4 h. A cohort older than ~1 day is usually settled unless there was an outage. Check anyway.

## Two clocks (R2)

- **Discovery clock** — `manifest.discovered_at`, ingestion wall-clock UTC. Measures *pipeline* behavior. It records Bishop's uptime and catch-ups: 2026-09-22 has zero rows (host down 22–25 Sep), and arXiv 27 Sep has 16,719 rows (export-stuck catch-up).
- **Publication clock** — `published_at`. Measures *the world* ("what came out this week"). Use it for "this week's arXiv".
- UTC midnight is the day boundary on both clocks. It is the same boundary as scrape `discovered_today` and harvest `released_today`. Overlay days and mill Search windows are *not* the scrape tick.

## The exit partition (R3, R12)

Defined by **decision-time tier**, not current state, so a promoted row does not silently move from parked to proceeded. The buckets are exclusive and sum to discovered:

| Bucket | Definition |
|--------|------------|
| undecided | `relevance_decision IS NULL` |
| rejected | `relevance_decision = 0` |
| parked | `relevance_decision = 1 AND pre_filter_tier = 'peripheral'` |
| proceeded · INDEXED | `pre_filter_tier = 'core' AND processing_state = 'INDEXED'` |
| proceeded · failed/escalated | `pre_filter_tier = 'core' AND processing_state IN (*_FAILED, ESCALATION_FLAGGED, PERMANENTLY_FAILED)` |
| proceeded · in flight | `pre_filter_tier = 'core'`, any other state |
| pass · untiered | `relevance_decision = 1 AND pre_filter_tier IS NULL` (legacy; should be 0 — report it if not) |

Derived terms:

- **Pass** — `relevance_decision = 1` (gate-1 yes) = parked + proceeded + untiered. The lifetime "3% pass rate" card is a pass rate, not conversion.
- **Proceeded** — pass at `core` tier.
- **Parked** — pass at `peripheral` tier. It is a branch, not a success.
- **Promoted** — `pre_filter_tier = 'peripheral' AND processing_state != 'RELEVANCE_PARKED'`. `promote_parked` flips the state and only *logs* the event. The count is exact. **Promote latency is unknowable** without an event column (a schema change, and not this function's). Lifetime as of 2026-09-27: 0 of 968.
- **Yield** — INDEXED ÷ discovered, for one population and window. Say "yield", not "conversion", unless the success event is named.

## INDEXED-in-cohort (R1)

There is no `indexed_at`. Write down which proxy you used:

- **"Currently INDEXED"** — `processing_state = 'INDEXED'` now. The lie: says nothing about *when*. Fine for settled cohorts.
- **"INDEXED by T"** — `processing_state = 'INDEXED' AND stage2.completed_at <= T`, where `stage2` = `batches` joined on `entries.enrichment_stage2_batch_id`. This is a **lower bound** on INDEXED time, because the vector write comes after. Known lies: a Call 2 re-run overwrites the batch id, and pre-`m3` rows may lack it (count the missing joins).
- **Not a proxy:** `entries.ingested_at − discovered_at` is **time-to-scrape**. It said 0.26 h where the Call 2 clock said 2.46 h (GitHub, 2026-09-15). Never label it time-to-INDEXED.

## Two GitHub populations

- **Tap** — `source_id` whose harvest-ledger `candidates.released_at` falls in the same UTC day as its `discovered_at`. It is released by the `$N` faucet from the mill pool.
- **Incremental** — GitHub rows discovered that day that are *not* in that day's release set. They come from the scraper's `fetch_manifest` POST.
- The lie: release is skip-if-exists and still stamps `released_at`. A repo that incremental discovered earlier the same UTC day, and the tap then "released", counts as tap. The bias makes the tap look better, not worse.
- GitHub `discovered_today` mixes both. `last_successful_run_at` is incremental cursor lag, never mill progress.

## Pool (harvest ledger)

- **Unreleased at end of day D** = `count(first_seen_at < D+1) − count(released_at < D+1)`. It is reconstructable from ledger timestamps, and matched the live `released_at IS NULL` count exactly on 2026-09-27.
- **Mill adds** — new `first_seen_at` per UTC day. `harvest_runs.items_upserted` includes re-seen rows. Re-seen *per day* is not recoverable (`last_seen_at` is overwritten).
- **Censored window** — a `harvest_runs` row with `incomplete_results` (Search cap). Count it, don't rate it.

## Two dollars

- **Blend `$`** — modeled. `economics.yaml` unit × count, with a *guessed* `github_paid_path_rate` baked in. Label it "modeled".
- **Anthropic `$`** — billed. `message.usage` × price. Not persisted (PB-002). Label it "billed".
- They never share a card or a sum. A gap between them is model error, not savings. To test the model, compare a **parameter** (e.g., `github_paid_path_rate` 0.022) with an **observed rate** (tap proceeded 0.04%).
- **"`$` per tap-released row" is tautological** in the modeled series: it is the input parameter (`$0.000764`). The informative modeled figure is `$` per tap row that reached INDEXED (R10).
- **Waste on parked is gate-1 spend only.** Parked rows have no `entries` row and no Call 1 batch (R9).
