"""E1 — cohort exit partition by source.

Question: of rows in window W, by source, where did each one exit?
  population: manifest rows (all sources) whose clock falls in [start, end)
  window:     UTC dates, half-open. --clock discovered_at (pipeline) | published_at (world)
  success:    proceeded · INDEXED (currently INDEXED; see glossary "INDEXED-in-cohort")
  grain:      source

Buckets are exclusive and sum to n (glossary "exit partition"). Tier-based, not
state-based, so promoted rows stay counted under parked; `promoted` is a sub-count.
Rows with a NULL published_at drop out under --clock published_at; the count is printed.

Usage: python e1_cohort_partition.py 2026-09-15            # one UTC day
       python e1_cohort_partition.py 2026-09-11 2026-09-22 # settled window
Seeded from .dev/scratch/reporting-e1/e1_tuesday_cohort.py + e4_settled_yield.py.
"""

from _common import FAILED_STATES, bishop, header, window_args

a = window_args(__doc__.splitlines()[0], clock=True)
clock = a.clock
failed = ",".join(f"'{s}'" for s in FAILED_STATES)
header("E1 cohort partition", population="manifest, all sources", window=f"[{a.start}, {a.end}) on {clock}",
       success="core tier AND INDEXED", grain="source")

conn = bishop()
if clock == "published_at":
    nulls = conn.execute(
        "SELECT COUNT(*) FROM manifest WHERE published_at IS NULL AND discovered_at >= ? AND discovered_at < ?",
        (a.start, a.end),
    ).fetchone()[0]
    print(f"published_at NULL among same discovered_at window (excluded): {nulls}\n")

cols = ("source", "n", "undecided", "rejected", "parked", "core_indexed", "core_failed",
        "core_in_flight", "pass_untiered", "promoted", "indexed_any")
rows = conn.execute(
    f"""SELECT source, COUNT(*),
        SUM(relevance_decision IS NULL),
        SUM(relevance_decision = 0),
        SUM(relevance_decision = 1 AND pre_filter_tier = 'peripheral'),
        SUM(pre_filter_tier = 'core' AND processing_state = 'INDEXED'),
        SUM(pre_filter_tier = 'core' AND processing_state IN ({failed})),
        SUM(pre_filter_tier = 'core' AND processing_state != 'INDEXED'
            AND processing_state NOT IN ({failed})),
        SUM(relevance_decision = 1 AND pre_filter_tier IS NULL),
        SUM(pre_filter_tier = 'peripheral' AND processing_state != 'RELEVANCE_PARKED'),
        SUM(processing_state = 'INDEXED')
    FROM manifest WHERE {clock} >= ? AND {clock} < ?
    GROUP BY 1 ORDER BY 2 DESC""",
    (a.start, a.end),
).fetchall()

print(" | ".join(cols))
tot = [0] * (len(cols) - 1)
for r in rows:
    print(" | ".join(str(x) for x in r))
    tot = [t + (x or 0) for t, x in zip(tot, r[1:])]
print(" | ".join(["ALL"] + [str(t) for t in tot]))

n, und, rej, park, idx, fail, fly, untiered = tot[:8]
if und + rej + park + idx + fail + fly + untiered != n:
    print("\nWARNING: partition does not sum to n — a tier/decision combination is unaccounted for")
passes = park + idx + fail + fly + untiered
if n:
    print(f"\npass {passes}/{n} = {passes / n:.1%}; INDEXED(core) {idx}/{n} = {idx / n:.2%}")
if passes:
    print(f"parked share of passes {park}/{passes} = {park / passes:.0%}")
print(f"settled: {und == 0 and fly == 0} (undecided={und}, in_flight={fly})")
