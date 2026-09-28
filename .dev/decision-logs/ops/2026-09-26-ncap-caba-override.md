# Harvest N_cap override — back from caba

**Date:** 2026-09-26
**Scope:** ops / GitHub release tap budget. Not a unit-cost recalibration. Not PB-002.
**Status:** Live on this host via env. Yaml pin unchanged.

## Verdict

Operator override: **back from caba — server out for 4-ish days.**

Raise the GitHub tap about 10× for the catch-up. One variable: `BISHOP_HARVEST_DAILY_BUDGET_USD=11.72`. `config/harvest/economics.yaml` stays `daily_budget_usd: 2.00`. Compose injects the env into `scraper` and `query-api`, and that env wins over the yaml.

## Why 11.72 and not 20

`N_cap = floor((daily_budget − 0.92) / 0.000764)`. The `$0.92` paper reserve does not scale.

| Budget | N_cap | vs 1413 |
|---|---|---|
| `$2` (yaml pin) | 1413 | 1× |
| `$11.72` (this override) | 14136 | ~10× |
| `$20` (`$2` × 10) | 24973 | ~17.7× |

`$11.72` is the dollar figure that lands on ~10×. `$2` × 10 overshoots because every extra dollar after the paper reserve goes to GitHub.

## What did not change

- Unit costs, paid-path rates, paper reserve.
- Tests still assert the yaml worked example (`n_cap == 1413` at `$2`).
- No image rebuild. Recreate `scraper` and `query-api` so they read the new env.

## Follow-up 2026-09-27 — faucet to a third

The 14136 cap filled. Anthropic credits (~$6) stopped the batch path around 03:00 UTC; the release tap kept inserting until the cap (~04:58 UTC). Operator added credits and asked to close the faucet to about a third.

Env is now `BISHOP_HARVEST_DAILY_BUDGET_USD=4.52`.

| Budget | N_cap | vs 14136 |
|---|---|---|
| `$11.72` (spent) | 14136 | 1× |
| `$4.52` (current) | 4712 | 1/3 |
| `$2` (yaml pin) | 1413 | — |

`floor((4.52 - 0.92) / 0.000764) = 4712`. A third of the dollar figure (`$3.91`) would have been a smaller cap, because the paper reserve still does not scale. `released_today` is already above 4712, so the tap adds nothing more on UTC 2026-09-27. Rows already in `DISCOVERED` still go through Gate 1.

Numbers, screenshots, and what to change next: `catch_up_ad_hoc.md`.
