"""E2 — GitHub tap vs incremental, per UTC day.

Question: on each day, does the $N tap convert GitHub rows as well as incremental does?
  population: manifest source='github' discovered on day D, split by whether the
              source_id's ledger released_at is also on D (tap) or not (incremental)
  window:     UTC dates [start, end), discovery clock, one row per day
  success:    pass, proceeded (tier core), currently INDEXED
  grain:      day x path

Known lie (glossary "Two GitHub populations"): release is skip-if-exists, so a repo
incremental found earlier that day and the tap then stamped counts as tap. The bias
favors the tap. Days with 0 tap releases print but carry no tap signal.
Modeled $ printed is the blend (economics.yaml unit), labeled modeled. Never billed.

Usage: python e2_github_tap_split.py 2026-09-17 2026-09-19
Seeded from .dev/scratch/reporting-e1/e1_followups.py + e4_settled_yield.py.
"""

from datetime import date, timedelta

from _common import bishop, header, ledger, window_args

UNIT_MODELED_USD = 0.000764

a = window_args(__doc__.splitlines()[0])
header("E2 GitHub tap split", population="github discovered, tap vs incremental", window=f"[{a.start}, {a.end}) discovered_at",
       success="pass / core / INDEXED", grain="day x path")

conn, led = bishop(), ledger()
print("day | path | n | undecided | pass | core | indexed")
agg = {"tap": [0, 0, 0, 0, 0], "incremental": [0, 0, 0, 0, 0]}
d = date.fromisoformat(a.start)
while d < date.fromisoformat(a.end):
    day, nxt = d.isoformat(), (d + timedelta(days=1)).isoformat()
    released = {r[0] for r in led.execute(
        "SELECT source_id FROM candidates WHERE released_at >= ? AND released_at < ?", (day, nxt))}
    split = {"tap": [0, 0, 0, 0, 0], "incremental": [0, 0, 0, 0, 0]}
    for sid, st, dec, tier in conn.execute(
        "SELECT source_id, processing_state, relevance_decision, pre_filter_tier FROM manifest "
        "WHERE source = 'github' AND discovered_at >= ? AND discovered_at < ?", (day, nxt)):
        s = split["tap" if sid in released else "incremental"]
        for i, hit in enumerate((True, dec is None, dec == 1, tier == "core", st == "INDEXED")):
            s[i] += hit
    print(f"{day} | ledger_released={len(released)}")
    for path, s in split.items():
        print(f"{day} | {path} | " + " | ".join(map(str, s)))
        agg[path] = [x + y for x, y in zip(agg[path], s)]
    d += timedelta(days=1)

print("\nsum | path | n | undecided | pass | core | indexed | pass% | indexed%")
for path, (n, und, ps, core, idx) in agg.items():
    rate = (lambda k: f"{k / n:.2%}") if n else (lambda k: "-")
    print(f"sum | {path} | {n} | {und} | {ps} | {core} | {idx} | {rate(ps)} | {rate(idx)}")
tn, tidx = agg["tap"][0], agg["tap"][4]
if tidx:
    print(f"\nmodeled $ per tap INDEXED: {tn} x ${UNIT_MODELED_USD} / {tidx} = ${tn * UNIT_MODELED_USD / tidx:.2f} (modeled)")
if tn:
    print(f"observed tap proceeded rate {agg['tap'][3]}/{tn} = {agg['tap'][3] / tn:.3%} vs economics.yaml github_paid_path_rate (parameter)")
