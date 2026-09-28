"""E1 — how long a discovery cohort takes to reach Call 2 (the INDEXED lower bound).

Question: for rows discovered in W that are INDEXED now, hours from discovery to
their Call 2 batch completed_at, by source.
  population: manifest rows discovered in [start, end) with entries.processing_state = INDEXED
  window:     UTC dates, discovery clock
  success:    Call 2 batch completed (batches via entries.enrichment_stage2_batch_id)
  grain:      source; min / median / max hours

Lower bound on INDEXED time (the vector write comes later). The ingested_at column is
printed for contrast only: it is time-to-scrape, never time-to-INDEXED (glossary R1).
`missing_batch` counts rows whose stage-2 batch id is NULL or re-run-overwritten.

Usage: python e1_settle_clock.py 2026-09-15
Seeded from .dev/scratch/reporting-e1/e1_followups.py.
"""

from _common import bishop, header, window_args

a = window_args(__doc__.splitlines()[0])
header("E1 settle clock", population="discovered cohort, currently INDEXED", window=f"[{a.start}, {a.end}) discovered_at",
       success="Call 2 batch completed_at", grain="source")

rows = bishop().execute(
    """SELECT m.source,
          (julianday(b.completed_at) - julianday(m.discovered_at)) * 24,
          (julianday(e.ingested_at) - julianday(m.discovered_at)) * 24
       FROM manifest m JOIN entries e ON e.source_id = m.source_id
       LEFT JOIN batches b ON b.batch_id = e.enrichment_stage2_batch_id
       WHERE m.discovered_at >= ? AND m.discovered_at < ? AND e.processing_state = 'INDEXED'""",
    (a.start, a.end),
).fetchall()


def mmm(xs):
    xs = sorted(xs)
    return (round(xs[0], 2), round(xs[len(xs) // 2], 2), round(xs[-1], 2)) if xs else None


by = {}
for src, c2, ing in rows:
    by.setdefault(src, []).append((c2, ing))
print("source | n | call2_h min/med/max | missing_batch | (ingested_h min/med/max — NOT time-to-INDEXED)")
for src, v in sorted(by.items()):
    c2 = [x for x, _ in v if x is not None]
    ing = [y for _, y in v if y is not None]
    print(f"{src} | {len(v)} | {mmm(c2)} | {len(v) - len(c2)} | ({mmm(ing)})")
