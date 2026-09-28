# Queries

Promoted from `.dev/scratch/reporting-e1/` on 2026-09-27. Each file answers one question. Its docstring carries `{population, window, success, grain}` and the known lies. Every connection is `mode=ro` via `_common.py`. Nothing here writes either DB, and nothing here is imported by `services/`.

| File | Question | Feeds |
|------|----------|-------|
| `e1_cohort_partition.py` | Where did window W's rows exit, by source? Exclusive partition, tier-based, with a sum check. `--clock published_at` for world-time | F-005, Q-002 |
| `e1_settle_clock.py` | Hours from discovery to Call 2 `completed_at` for INDEXED rows (a lower bound) | glossary R1 |
| `e2_github_tap_split.py` | Tap vs incremental GitHub, per day: pass / core / INDEXED, modeled `$` per tap INDEXED | F-001, F-002, F-006, Q-001 |
| `e3_parked_promote.py` | Parked share of passes; promoted count; entries / Call 1 on parked (the R9 check) | F-004 |
| `e5_pool_trajectory.py` | Ledger adds vs releases vs unreleased EOD, plus censored `harvest_runs` | F-003, Q-003 |

No E4 file: the E1 settled-window table covers yield vs volume. No E6 file: it is blocked on PB-002 (Q-004). Write it when usage exists. Do not invent token fields.

## Running

```powershell
cd .dev/insights-manager/queries
python e1_cohort_partition.py 2026-09-11 2026-09-22
```

Paste the printed header (`read_at_utc`, DB paths, the four slots) into the run file. That header is the freeze stamp.

## Load-bearing

- **Live DB on this host is `sqlite_live/bishop.db`.** `_common.py` prefers it when it exists. `sqlite/bishop.db` here is a stale 2026-09-11 file. `.dev/sqlite.md` documents the override. The rule file still names `sqlite/` as canonical, which is correct for the repo and wrong for this host.
- The ledger is 1.7 GB and WAL. A read can hit `attempt to write a readonly database` while the scraper writes. Retry; never drop `mode=ro`.
- E2 loads each day's release set into memory: fine for days, slow for months. Keep windows to days.
- `UNIT_MODELED_USD` in `e2` mirrors `/harvest`'s blended unit (`$0.000764`). If `economics.yaml` is recalibrated (F-002), update the constant *and* say so in the run file.

## Adding a query

One question per file, named `e<N>_<what>.py` after the experiment it serves. Docstring first line is the question; then the four slots, the known lies, usage, and what it was seeded from. Read-only via `_common`. If a question needs a column that doesn't exist, the file prints the proxy and says so. It never asks for a migration.
