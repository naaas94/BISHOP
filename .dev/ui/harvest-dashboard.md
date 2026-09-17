# Harvest dashboard

Projected spend on `/dashboard` comes from query-api `GET /stats/overview`: sidecar `released_today * blended_github_usd`, plus pool / unreleased / N_cap / budget. It is **not** live Anthropic usage (PB-002).

Missing harvest sqlite → zeros and muted “Harvest sidecar not mounted.” Empty ledger with schema (release loop `connect_rw`) → sidecar present, pool 0. Economics yaml missing → N_cap and budget stay 0.

`N_cap` / released today full ≠ harvest paused. A flat pool with unreleased leftover and a stale `harvest_cursor` means the mill is waiting on the scrape interval (live 6h) or the 90s slice budget ended. Read `harvest_runs` + cursor, not just the card.

Rebuild `query-api` (sidecar mount + `config/harvest` COPY + `BISHOP_HARVEST_DAILY_BUDGET_USD`) and `ui` (`bishop/ui:m8` bakes the template) before treating the card as live. `0` on that env zeros dashboard `N_cap` the same way it closes the scraper tap.

Live 2026-09-17: tap inserted (`released_today=1413`). Mill hitchhiker. Pickup `harvest-pool-next.md`.
