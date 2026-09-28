# Corrections to `REPORTING.md`

`REPORTING.md` is the founding persona brief (2026-09-27). Its content is intentionally left unedited: it records what the hat believed before its first run. This file records what the first run proved wrong or under-specified. Source: `.dev/decision-logs/ops/2026-09-27-reporting-persona-review.md` §2b and §4.4.

**Rule:** where `REPORTING.md` and this file disagree, this file wins. Line refs are `REPORTING.md:<line>` as of 2026-09-27.

| ID | Brief says | Correction | Kind |
|----|-----------|------------|------|
| R1 | Time-to-INDEXED from `ingested_at` / "batch `completed_at`" (`:96`, `:165`) | `ingested_at` is time-to-scrape. Use Call 2 `batches.completed_at` via `entries.enrichment_stage2_batch_id` as a lower bound. See `glossary.md` → INDEXED-in-cohort | under-specified |
| R2 | One clock, discovery (`:65`, `:142`), yet "this week's arXiv" (`:29`) | Two clocks. Discovery = pipeline latency and uptime. Publication (`published_at`) = what came out. Check uptime before picking a window | missing concept |
| R3 | Promote needs a timestamp (E3, `:173`). Proceeded is defined by state (`:143`) | Promote *count* is exact from `pre_filter_tier`. Only *latency* needs a column. Define parked/proceeded by tier, not state | wrong premise |
| R4 | E5 implied new instrumentation (`:175`) | Answerable from ledger `first_seen_at` / `released_at`. The reconstruction matched live exactly | wrong premise |
| R5 | "One gate-1 pin" (`:58`), with no rule for per-source findings | Per-source numbers go to `config/source-notes/<source>.md` as dated intel, and to eval as a labeling request. Never as a threshold proposal | missing rule |
| R6 | "Reporting cannot start until [good week] is picked" (`:186`) | Escape hatch. It gates a *page headline* only. Runs need no good-week score | cut |
| R7 | Soft-launch pin vs gold under Cohorts (`:103`); steal-bar vs topic (`:109`) | Both are eval (PB-008). This function nominates slices (source_ids + reason); eval labels them. It never computes precision | cut / re-route |
| R8 | Must-look is PB-013 (`:120`); parked as a product (`:188`) | The bigger overlap is *parked*: same population as PB-013's promote-vs-leave pass. This function sizes it; PB-013 designs it | re-route |
| R9 | "Call-1 spend on parked that never promote" (`:115`) | **False.** Parked rows have no `entries` row and no Call 1 batch. Waste = gate-1 spend on rows that park and never promote | false |
| R10 | "`$` per tap-released GitHub row" (`:113`) | **Tautological:** equals the `$0.000764` input. Use modeled `$` per tap row that reached INDEXED | false |
| R11 | "GitHub tap the opposite [high yield]" (`:174`); "~0.7% on the 2024 slice" (`:115`) | **Falsified:** the 2026 tap passed 0.26% vs incremental 1.83%. The 0.7% figure is a different (2024) slice | false |
| R12 | Conversion row "DISCOVERED / gate-1 no / parked / proceeded / scraped / INDEXED / failed" (`:93`) | Not a partition (proceeded ⊃ scraped ⊃ INDEXED). Use the exclusive partition in `glossary.md` | wrong structure |

## Also cut (not errors, but not this function)

- Surfaces table and page plan (`:124–134`, `:192–198`). A page is earned by three runs asking the same question (README rule 8).
- Chart/bar contract (`:69`, `:147–152`). No chart without a page. If a page is ever earned, it moves to `.dev/ui/design.md`.
- Brainstorm sessions as a gate (`:182–190`). Sessions 2 (source strategy) and 3 (parked as a product) survive as *questions*. They are in `findings.yaml` → `open_questions`.
- Hat-merge note (`:210`) named backlog items instead of hats (review A4). The real merge candidates were the pipeline-operator and eval hats. The review ranked both below re-scope.

## What survived unchanged

The `{population, window, success, grain}` law, stock / flow / cohort, the two-dollar rule, the "do not" list (`:202–210`), and the E1–E6 experiment set, as queries that end in a routed verdict.
