import sqlite3
from pathlib import Path

path = Path("C:/Users/Ale/bishop_data/sqlite_live/bishop.db")
con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
cur = con.cursor()
print("pending_DISCOVERED")
for row in cur.execute(
    """
    SELECT source, COUNT(*)
    FROM manifest
    WHERE processing_state = 'DISCOVERED'
    GROUP BY 1
    ORDER BY 2 DESC
    """
):
    print(row)
print("scraper_state")
for row in cur.execute(
    "SELECT source, last_successful_run_at FROM scraper_state ORDER BY source"
):
    print(row)
con.close()
