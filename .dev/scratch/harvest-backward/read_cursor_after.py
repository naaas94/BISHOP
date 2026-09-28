import sqlite3

p = "C:/Users/Ale/bishop_data/harvest/ledger.sqlite"
c = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
c.row_factory = sqlite3.Row
print("cursor schema:")
print(c.execute("SELECT sql FROM sqlite_master WHERE name='harvest_cursor'").fetchone()[0])
print("pragma:")
for row in c.execute("PRAGMA table_info(harvest_cursor)"):
    print(dict(row))
print("cursor row:")
r = c.execute("SELECT * FROM harvest_cursor").fetchone()
print(dict(r) if r else None)
print("newest harvest_runs:")
rows = c.execute(
    """
    SELECT id, query, window_start, window_end, total_count,
           pages_fetched, items_upserted, started_at, finished_at
    FROM harvest_runs ORDER BY id DESC LIMIT 5
    """
).fetchall()
for x in rows:
    print(dict(x))
print("runs with 2026 query:")
rows = c.execute(
    """
    SELECT id, query, window_start, window_end, started_at
    FROM harvest_runs
    WHERE query LIKE '%2026-09%'
    ORDER BY id DESC LIMIT 5
    """
).fetchall()
for x in rows:
    print(dict(x))
