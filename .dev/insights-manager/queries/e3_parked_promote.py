"""E3 — parked leakage and promote count.

Question: of gate-1 passes, how many parked, and how many parked rows ever got promoted?
  population: manifest rows with relevance_decision = 1 (lifetime, or window if given)
  window:     lifetime by default; optional [start, end) on discovered_at
  success:    promoted = pre_filter_tier 'peripheral' AND state != RELEVANCE_PARKED
  grain:      tier x current state; plus entries / Call 1 presence per tier (R9 check)

Promote *count* is exact from tier. Promote *latency* is not knowable (no event
column; promote_parked only logs). Do not propose one from here.

Usage: python e3_parked_promote.py                          # lifetime
       python e3_parked_promote.py 2026-09-11 2026-09-22    # window
Seeded from .dev/scratch/reporting-e1/e1_followups.py + e4_settled_yield.py.
"""

import sys

from _common import bishop, header

win = sys.argv[1:3]
where, args = "m.relevance_decision = 1", ()
if len(win) == 2:
    where += " AND m.discovered_at >= ? AND m.discovered_at < ?"
    args = tuple(win)
header("E3 parked / promote", population="gate-1 passes", window=f"[{win[0]}, {win[1]}) discovered_at" if len(win) == 2 else "lifetime",
       success="promoted (tier peripheral, not RELEVANCE_PARKED)", grain="tier x state")

conn = bishop()
print("tier | processing_state | n")
for r in conn.execute(f"SELECT pre_filter_tier, processing_state, COUNT(*) FROM manifest m WHERE {where} GROUP BY 1, 2 ORDER BY 3 DESC", args):
    print(" | ".join(map(str, r)))

print("\ntier | passes | promoted | entries_rows | with_call1_batch")
for r in conn.execute(
    f"""SELECT m.pre_filter_tier, COUNT(*),
           SUM(m.pre_filter_tier = 'peripheral' AND m.processing_state != 'RELEVANCE_PARKED'),
           COUNT(e.id), SUM(e.enrichment_stage1_batch_id IS NOT NULL)
       FROM manifest m LEFT JOIN entries e ON e.source_id = m.source_id
       WHERE {where} GROUP BY 1""", args):
    print(" | ".join(map(str, r)))
