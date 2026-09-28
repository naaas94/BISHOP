# Today page

`GET /today` is the UTC-day **glance**. query-api `GET /stats/today`. Clock is **UTC midnight**, same as scrape `discovered_today` and harvest `released_today`.

Headline is discovered since midnight. Scrape health is a one-liner (caught up or worst lag, overlay, tick, DISCOVERED/queued pile, exception strip) plus discovered-by-source bars — not the lag-bar table. Harvest faucet is one line (`released / N_cap · $ · tap`) — not the mill, pool, or faucet cards. Those stay on `/scrape` and `/harvest`.

Pipeline numbers are the **discovered-at ≥ midnight cohort**: non-zero funnel bars, still-in-queue (DISCOVERED plus `*_QUEUED` / `*_SUBMITTED` / `*_CLAIMED`), entries with `ingested_at` today, batches with `completed_at` today, `error_log.timestamp` today. **Indexed** is that cohort already in `INDEXED`. There is no `indexed_at`.

`/dashboard` keeps lifetime cards. Rebuild `query-api` and `ui`.
