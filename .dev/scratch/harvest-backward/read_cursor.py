import sqlite3

p = "C:/Users/Ale/bishop_data/harvest/ledger.sqlite"
c = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
c.row_factory = sqlite3.Row
print("tables:", [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")])
print("cursor schema:")
print(c.execute("SELECT sql FROM sqlite_master WHERE name='harvest_cursor'").fetchone()[0])
print("cursor row:")
r = c.execute("SELECT * FROM harvest_cursor").fetchone()
print(dict(r) if r else None)
print("recent runs:")
rows = c.execute(
    """
    SELECT id, query, window_start, window_end, total_count,
           pages_fetched, items_upserted, started_at, finished_at
    FROM harvest_runs ORDER BY id DESC LIMIT 8
    """
).fetchall()
for x in rows:
    print(dict(x))
