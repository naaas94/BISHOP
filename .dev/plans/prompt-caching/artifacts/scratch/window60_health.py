import json
import sqlite3
from pathlib import Path

path = Path("C:/Users/Ale/bishop_data/sqlite_live/bishop.db")
con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
cur = con.cursor()

print("=== funnel (current state) ===")
for row in cur.execute(
    """
    SELECT processing_state, COUNT(*)
    FROM manifest
    GROUP BY 1
    ORDER BY 2 DESC
    """
):
    print(f"{row[1]:6d}  {row[0]}")

print("\n=== by source x state (top) ===")
for row in cur.execute(
    """
    SELECT source, processing_state, COUNT(*)
    FROM manifest
    GROUP BY 1, 2
    ORDER BY 1, 3 DESC
    """
):
    print(f"{row[2]:6d}  {row[0]:18s} {row[1]}")

print("\n=== totals by source ===")
for row in cur.execute(
    "SELECT source, COUNT(*) FROM manifest GROUP BY 1 ORDER BY 2 DESC"
):
    print(f"{row[1]:6d}  {row[0]}")

print("\n=== discovered_at last 6h by source ===")
for row in cur.execute(
    """
    SELECT source, COUNT(*)
    FROM manifest
    WHERE discovered_at >= datetime('now', '-6 hours')
    GROUP BY 1
    ORDER BY 2 DESC
    """
):
    print(f"{row[1]:6d}  {row[0]}")

print("\n=== github discovered_at date histogram (UTC day) ===")
for row in cur.execute(
    """
    SELECT substr(discovered_at, 1, 10) AS d, COUNT(*)
    FROM manifest
    WHERE source = 'github'
    GROUP BY 1
    ORDER BY 1
    """
):
    print(f"{row[1]:6d}  {row[0]}")

print("\n=== scraper_state ===")
for row in cur.execute(
    "SELECT source, last_successful_run_at FROM scraper_state ORDER BY source"
):
    print(row)

print("\n=== open batches ===")
for row in cur.execute(
    """
    SELECT batch_type, status, COUNT(*)
    FROM batches
    GROUP BY 1, 2
    ORDER BY 1, 2
    """
):
    print(row)

con.close()
