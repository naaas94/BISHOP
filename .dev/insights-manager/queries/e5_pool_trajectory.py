"""E5 — drain honesty: does the harvest pool actually shrink?

Question: per UTC day, mill adds vs tap releases vs unreleased at end of day.
  population: harvest ledger candidates (sidecar, not bishop.db)
  window:     UTC dates [start, end); the pool is reconstructed from a base at `start`
  success:    releases > adds (pool shrinking). /harvest days-to-drain assumes adds = 0
  grain:      day

unreleased_eod(D) = count(first_seen_at < D+1) - count(released_at < D+1).
It matched live `released_at IS NULL` exactly on 2026-09-27; the check is re-printed.
Re-seen rows per day are not recoverable (last_seen_at is overwritten); not needed here.
harvest_runs `incomplete_results` = Search-capped windows: counted, not rated.
If the ledger read hits "attempt to write a readonly database" (WAL, scraper
mid-write), retry. Never drop mode=ro.

Usage: python e5_pool_trajectory.py 2026-09-13 2026-09-28
Seeded from .dev/scratch/reporting-e1/e1_followups.py.
"""

from datetime import date, timedelta

from _common import header, ledger, window_args

a = window_args(__doc__.splitlines()[0], default_days=7)
header("E5 pool trajectory", population="harvest ledger candidates", window=f"[{a.start}, {a.end}) UTC",
       success="released > adds", grain="day")

led = ledger()
one = lambda sql, *p: led.execute(sql, p).fetchone()[0]
adds = dict(led.execute("SELECT substr(first_seen_at,1,10), COUNT(*) FROM candidates WHERE first_seen_at >= ? AND first_seen_at < ? GROUP BY 1", (a.start, a.end)))
rels = dict(led.execute("SELECT substr(released_at,1,10), COUNT(*) FROM candidates WHERE released_at >= ? AND released_at < ? GROUP BY 1", (a.start, a.end)))
unrel = one("SELECT COUNT(*) FROM candidates WHERE first_seen_at < ?", a.start) - one("SELECT COUNT(*) FROM candidates WHERE released_at < ?", a.start)
print(f"unreleased at {a.start} 00:00: {unrel}")
print("day | adds | released | unreleased_eod | adds>released")
d = date.fromisoformat(a.start)
while d < date.fromisoformat(a.end):
    k = d.isoformat()
    unrel += adds.get(k, 0) - rels.get(k, 0)
    print(f"{k} | {adds.get(k, 0)} | {rels.get(k, 0)} | {unrel} | {adds.get(k, 0) > rels.get(k, 0)}")
    d += timedelta(days=1)
print(f"\nlive released_at IS NULL: {one('SELECT COUNT(*) FROM candidates WHERE released_at IS NULL')} (should equal last unreleased_eod if end >= tomorrow)")

print("\nharvest_runs by finished day | runs | items_upserted | incomplete_results")
for r in led.execute("SELECT substr(finished_at,1,10), COUNT(*), SUM(items_upserted), SUM(incomplete_results) FROM harvest_runs WHERE finished_at >= ? AND finished_at < ? GROUP BY 1 ORDER BY 1", (a.start, a.end)):
    print(" | ".join(map(str, r)))
