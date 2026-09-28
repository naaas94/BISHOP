"""E1 — Tuesday cohort (REPORTING.md). Read-only. Frozen day: 2026-09-22 UTC."""

import sqlite3
import sys

DB = "C:/Users/Ale/bishop_data/sqlite_live/bishop.db"
LEDGER = "C:/Users/Ale/bishop_data/harvest/ledger.sqlite"
DAY = sys.argv[1] if len(sys.argv) > 1 else "2026-09-22"

conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)


def q(sql, *args):
    return conn.execute(sql, args).fetchall()


print("manifest cols:", [r[1] for r in q("PRAGMA table_info(manifest)")])
print("entries cols:", [r[1] for r in q("PRAGMA table_info(entries)")])
print("batches cols:", [r[1] for r in q("PRAGMA table_info(batches)")])
print("discovered_at sample:", q("SELECT discovered_at FROM manifest ORDER BY discovered_at DESC LIMIT 2"))

WHERE = "discovered_at >= ? AND discovered_at < date(?, '+1 day')"

print(f"\n== cohort {DAY} by source x processing_state ==")
for r in q(
    f"SELECT source, processing_state, relevance_decision, COUNT(*) FROM manifest "
    f"WHERE {WHERE} GROUP BY 1,2,3 ORDER BY 1,4 DESC",
    DAY, DAY,
):
    print(r)

print("\n== cohort totals by source: n, decided, pass, parked, indexed, rejected, undecided ==")
for r in q(
    f"""SELECT source, COUNT(*),
        SUM(relevance_decision IS NOT NULL),
        SUM(relevance_decision = 1),
        SUM(processing_state = 'RELEVANCE_PARKED'),
        SUM(processing_state = 'INDEXED'),
        SUM(relevance_decision = 0),
        SUM(relevance_decision IS NULL)
    FROM manifest WHERE {WHERE} GROUP BY 1 ORDER BY 2 DESC""",
    DAY, DAY,
):
    print(r)

print("\n== INDEXED in cohort: ingested_at lag (days) min/median-ish/max ==")
rows = q(
    """SELECT m.source, julianday(e.ingested_at) - julianday(m.discovered_at)
    FROM manifest m JOIN entries e ON e.source_id = m.source_id
    WHERE m.discovered_at >= ? AND m.discovered_at < date(?, '+1 day')
      AND e.processing_state = 'INDEXED'""",
    DAY, DAY,
)
by = {}
for s, lag in rows:
    by.setdefault(s, []).append(lag)
for s, lags in by.items():
    lags.sort()
    print(s, len(lags), round(lags[0], 3), round(lags[len(lags) // 2], 3), round(lags[-1], 3))

print("\n== entries in cohort by state (post-gate pipeline) ==")
for r in q(
    f"""SELECT m.source, e.processing_state, COUNT(*) FROM manifest m
    JOIN entries e ON e.source_id = m.source_id
    WHERE m.discovered_at >= ? AND m.discovered_at < date(?, '+1 day')
    GROUP BY 1,2 ORDER BY 1,3 DESC""",
    DAY, DAY,
):
    print(r)

print("\n== github cohort split: tap-released that UTC day vs not ==")
led = sqlite3.connect(f"file:{LEDGER}?mode=ro", uri=True)
released = {
    r[0]
    for r in led.execute(
        "SELECT source_id FROM candidates WHERE released_at >= ? AND released_at < date(?, '+1 day')",
        (DAY, DAY),
    )
}
print("ledger released that day:", len(released))
gh = q(
    f"SELECT source_id, processing_state, relevance_decision FROM manifest WHERE source='github' AND {WHERE}",
    DAY, DAY,
)
split = {}
for sid, st, dec in gh:
    k = "tap" if sid in released else "incremental"
    d = split.setdefault(k, {"n": 0, "pass": 0, "rej": 0, "undecided": 0, "indexed": 0, "parked": 0})
    d["n"] += 1
    d["pass"] += dec == 1
    d["rej"] += dec == 0
    d["undecided"] += dec is None
    d["indexed"] += st == "INDEXED"
    d["parked"] += st == "RELEVANCE_PARKED"
print(split)

print("\n== discovered volume last 10 UTC days by source ==")
for r in q(
    "SELECT substr(discovered_at,1,10) d, source, COUNT(*) FROM manifest "
    "WHERE discovered_at >= date(?, '-14 day') GROUP BY 1,2 ORDER BY 1,2",
    DAY,
):
    print(r)
