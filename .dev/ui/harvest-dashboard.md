# Harvest economics page

`GET /harvest` is the harvest surface. query-api `GET /stats/harvest` reads the sidecar `mode=ro` plus `economics.yaml` (env `BISHOP_HARVEST_DAILY_BUDGET_USD` still wins). Headline is **unreleased × blended GitHub unit**, rounded to the dollar on the page. That is the modeled pool liability. It is **not** live Anthropic usage (PB-002).

Walk forecast uses complete `harvest_runs` in the walked recent span (`harvest_until` → `high_water` while `walk_direction=backward`). Per-window rate is `total_count / window_days`; median and max of those rates × unwalked days × blend. Incomplete Search windows (cap 1000) are counted, not used as rates. Fewer than 3 complete windows shows “forecast waiting.” `forward` closes the gap; the band is $0.00.

Faucet uses the same `remaining_slots(n_cap, released_today, github_in_queue)` rule as the scraper tap. Released today above `N_cap` is overshoot (tap closed until UTC midnight). “Modeled cost of today’s releases” is `released_today × blended`. Days-to-drain is `ceil(unreleased / N_cap)`: days to drain the current unreleased pool at `N_cap` if the mill adds nothing. It does not price unwalked mill days. The page line is the same sentence (`harvest_stats.html`). At the Search-window cap, incomplete windows are censored, so the walk forecast stays “waiting” until 3 complete windows exist in the walked span (r001: 677/677 `harvest_runs` on 2026-09-27 were `incomplete_results`). `/today` keeps one faucet line; mill walk, unreleased pool, and the faucet cards stay here.

`GET /stats/harvest` is the full payload. Harvest numbers live only here. Do not restore the old harvest card grid or a dashboard one-liner. Doctrine: `.dev/decision-logs/ops/2026-09-27-operator-ingest-pages.md`.

Missing harvest sqlite → zeros and muted “Harvest sidecar not mounted.” Empty ledger with schema (release loop `connect_rw`) → sidecar present, pool 0. Economics yaml missing → `N_cap` and budget stay 0.

`N_cap` / released today full ≠ harvest paused. A flat pool with unreleased leftover and a stale `harvest_cursor` means the mill is waiting. Read `harvest_runs` + cursor, not just the faucet.

Rebuild `query-api` (sidecar mount + `config/harvest` COPY + `BISHOP_HARVEST_DAILY_BUDGET_USD`) and `ui` (`bishop/ui:m8` bakes the template) before treating the page as live. After adding env keys, recreate query-api (`docker compose up -d query-api`); rebuild-only keeps the old budget. `0` on that env zeros `N_cap` the same way it closes the scraper tap. Show the blend at six decimals (`$0.000764`); four decimals reads `$0.0008`.

Live 2026-09-17: tap inserted (`released_today=1413`). Mill hitchhiker. Pickup `harvest-pool-next.md`.

Live 2026-09-26: host env was `11.72`, `N_cap` **14136**. That cap filled the same UTC day it was raised into (card `released_today=14136`, projected `$10.80` at the pinned unit).

Live 2026-09-27: env `4.52`, `N_cap` **4712**. `released_today` stays above the new cap until UTC midnight, so the tap adds nothing more today. Modeled `$` of today’s releases is still `released_today × blended`, which can exceed the new budget number. Anthropic’s bill for the burst was about `$5.11`, not the modeled `$10.80`. Walk forecast waiting (0 complete Search windows in the walked span; incomplete capped windows censored). Prefer `GET /stats/harvest` over dashboard cards.
