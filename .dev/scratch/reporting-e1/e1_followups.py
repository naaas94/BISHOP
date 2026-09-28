"""E1 follow-ups: tier/promote trace, Call-2 clock, E2 on a tap day, E5 feasibility. Read-only."""

import sqlite3

DB = "C:/Users/Ale/bishop_data/sqlite_live/bishop.db"
LEDGER = "C:/Users/Ale/bishop_data/harvest/ledger.sqlite"
conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
led = sqlite3.connect(f"file:{LEDGER}?mode=ro", uri=True)


def q(c, sql, *args):
    return c.execute(sql, args).fetchall()


print("== pre_filter_tier x processing_state (lifetime, decided=1) ==")
for r in q(conn, "SELECT pre_filter_tier, processing_state, COUNT(*) FROM manifest WHERE relevance_decision=1 GROUP BY 1,2 ORDER BY 3 DESC"):
    print(r)

print("\n== 2026-09-15 cohort: pre_filter_tier x state ==")
for r in q(conn, """SELECT source, pre_filter_tier, processing_state, COUNT(*) FROM manifest
    WHERE discovered_at >= '2026-09-15' AND discovered_at < '2026-09-16' AND relevance_decision=1
    GROUP BY 1,2,3 ORDER BY 1,4 DESC"""):
    print(r)

print("\n== 2026-09-15 INDEXED: discovered -> Call 2 batch completed_at (hours) ==")
rows = q(conn, """SELECT m.source,
      (julianday(b.completed_at) - julianday(m.discovered_at)) * 24,
      (julianday(e.ingested_at) - julianday(m.discovered_at)) * 24
    FROM manifest m JOIN entries e ON e.source_id = m.source_id
    LEFT JOIN batches b ON b.batch_id = e.enrichment_stage2_batch_id
    WHERE m.discovered_at >= '2026-09-15' AND m.discovered_at < '2026-09-16'
      AND e.processing_state = 'INDEXED'""")
by = {}
for s, c2, ing in rows:
    by.setdefault(s, []).append((c2, ing))
for s, v in by.items():
    c2s = sorted(x[0] for x in v if x[0] is not None)
    missing = sum(1 for x in v if x[0] is None)
    if c2s:
        print(s, "n", len(v), "call2 h min/med/max", round(c2s[0], 2), round(c2s[len(c2s) // 2], 2), round(c2s[-1], 2), "missing batch", missing)
    else:
        print(s, "n", len(v), "no call2 batch join", missing)

print("\n== batch_type x completed_at sample ==")
for r in q(conn, "SELECT batch_type, COUNT(*), MIN(completed_at), MAX(completed_at) FROM batches GROUP BY 1"):
    print(r)

for day in ("2026-09-17", "2026-09-26"):
    print(f"\n== E2 {day}: github tap vs incremental ==")
    released = {r[0] for r in q(led, "SELECT source_id FROM candidates WHERE released_at >= ? AND released_at < date(?, '+1 day')", day, day)}
    print("ledger released_at that day:", len(released))
    gh = q(conn, "SELECT source_id, processing_state, relevance_decision FROM manifest WHERE source='github' AND discovered_at >= ? AND discovered_at < date(?, '+1 day')", day, day)
    split = {}
    for sid, st, dec in gh:
        k = "tap" if sid in released else "incremental"
        d = split.setdefault(k, {"n": 0, "pass": 0, "rej": 0, "undecided": 0, "parked": 0, "indexed": 0})
        d["n"] += 1
        d["pass"] += dec == 1
        d["rej"] += dec == 0
        d["undecided"] += dec is None
        d["parked"] += st == "RELEVANCE_PARKED"
        d["indexed"] += st == "INDEXED"
    print(split)

print("\n== E5 feasibility: ledger daily first_seen (adds) vs released, last 14 days ==")
adds = dict(q(led, "SELECT substr(first_seen_at,1,10), COUNT(*) FROM candidates WHERE first_seen_at >= '2026-09-13' GROUP BY 1"))
rels = dict(q(led, "SELECT substr(released_at,1,10), COUNT(*) FROM candidates WHERE released_at >= '2026-09-13' GROUP BY 1"))
base_seen = q(led, "SELECT COUNT(*) FROM candidates WHERE first_seen_at < '2026-09-13'")[0][0]
base_rel = q(led, "SELECT COUNT(*) FROM candidates WHERE released_at < '2026-09-13'")[0][0]
unrel = base_seen - base_rel
print("unreleased at 2026-09-13 00:00:", unrel)
for d in sorted(set(adds) | set(rels)):
    unrel += adds.get(d, 0) - rels.get(d, 0)
    print(d, "adds", adds.get(d, 0), "released", rels.get(d, 0), "unreleased_eod", unrel)
print("now unreleased (released_at IS NULL):", q(led, "SELECT COUNT(*) FROM candidates WHERE released_at IS NULL")[0][0])
print("total candidates:", q(led, "SELECT COUNT(*) FROM candidates")[0][0])
print("harvest_runs by finished day (last 14):")
for r in q(led, "SELECT substr(finished_at,1,10), COUNT(*), SUM(items_upserted), SUM(incomplete_results) FROM harvest_runs WHERE finished_at >= '2026-09-13' GROUP BY 1 ORDER BY 1"):
    print(r)
