"""E4-lite: settled discovery days 2026-09-11..2026-09-21 by source, plus E2 for 09-17. Read-only."""

import sqlite3

DB = "C:/Users/Ale/bishop_data/sqlite_live/bishop.db"
LEDGER = "C:/Users/Ale/bishop_data/harvest/ledger.sqlite"
conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)

print("source, discovered, undecided, pass, parked(peripheral), proceeded(core), indexed, promoted(peripheral not parked)")
for r in conn.execute(
    """SELECT source, COUNT(*),
        SUM(relevance_decision IS NULL),
        SUM(relevance_decision = 1),
        SUM(pre_filter_tier = 'peripheral'),
        SUM(pre_filter_tier = 'core'),
        SUM(processing_state = 'INDEXED'),
        SUM(pre_filter_tier = 'peripheral' AND processing_state != 'RELEVANCE_PARKED')
    FROM manifest
    WHERE discovered_at >= '2026-09-11' AND discovered_at < '2026-09-22'
    GROUP BY 1 ORDER BY 2 DESC"""
):
    print(r)

print("tier, passes, entries rows, with Call 1 batch:")
for r in conn.execute(
    """SELECT m.pre_filter_tier, COUNT(*), COUNT(e.id), SUM(e.enrichment_stage1_batch_id IS NOT NULL)
    FROM manifest m LEFT JOIN entries e ON e.source_id = m.source_id
    WHERE m.relevance_decision = 1 GROUP BY 1"""
):
    print(r)

led = sqlite3.connect(f"file:{LEDGER}?mode=ro", uri=True)
for day in ("2026-09-17", "2026-09-18"):
    released = {
        r[0]
        for r in led.execute(
            "SELECT source_id FROM candidates WHERE released_at >= ? AND released_at < date(?, '+1 day')",
            (day, day),
        )
    }
    split = {}
    for sid, st, dec, tier in conn.execute(
        "SELECT source_id, processing_state, relevance_decision, pre_filter_tier FROM manifest "
        "WHERE source='github' AND discovered_at >= ? AND discovered_at < date(?, '+1 day')",
        (day, day),
    ):
        k = "tap" if sid in released else "incremental"
        d = split.setdefault(k, {"n": 0, "pass": 0, "core": 0, "indexed": 0})
        d["n"] += 1
        d["pass"] += dec == 1
        d["core"] += tier == "core"
        d["indexed"] += st == "INDEXED"
    print(day, "released", len(released), split)
