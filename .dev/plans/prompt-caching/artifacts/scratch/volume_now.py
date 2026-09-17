import sqlite3
from pathlib import Path

path = Path("C:/Users/Ale/bishop_data/sqlite_live/bishop.db")
con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
cur = con.cursor()

print("=== funnel ===")
for row in cur.execute(
    "SELECT processing_state, COUNT(*) FROM manifest GROUP BY 1 ORDER BY 2 DESC"
):
    print(f"{row[1]:6d}  {row[0]}")

print("\n=== totals by source ===")
for row in cur.execute(
    "SELECT source, COUNT(*) FROM manifest GROUP BY 1 ORDER BY 2 DESC"
):
    print(f"{row[1]:6d}  {row[0]}")

print("\n=== discovered_at by UTC day x source ===")
for row in cur.execute(
    """
    SELECT substr(discovered_at, 1, 10) AS d, source, COUNT(*)
    FROM manifest
    GROUP BY 1, 2
    ORDER BY 1, 2
    """
):
    print(f"{row[2]:6d}  {row[0]}  {row[1]}")

print("\n=== github published_at (pushed) by month ===")
for row in cur.execute(
    """
    SELECT substr(published_at, 1, 7) AS m, COUNT(*)
    FROM manifest
    WHERE source = 'github' AND published_at IS NOT NULL
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

print("\n=== batches last 24h by type/status ===")
for row in cur.execute(
    """
    SELECT batch_type, status, COUNT(*)
    FROM batches
    WHERE COALESCE(created_at, submitted_at, completed_at) >= datetime('now', '-1 day')
    GROUP BY 1, 2
    """
):
    print(row)

print("\n=== github last 48h states ===")
for row in cur.execute(
    """
    SELECT processing_state, COUNT(*)
    FROM manifest
    WHERE source = 'github' AND discovered_at >= datetime('now', '-2 days')
    GROUP BY 1
    ORDER BY 2 DESC
    """
):
    print(f"{row[1]:6d}  {row[0]}")

con.close()
