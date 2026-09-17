import sqlite3
from pathlib import Path

con = sqlite3.connect("file:C:/Users/Ale/bishop_data/sqlite_live/bishop.db?mode=ro", uri=True)
cur = con.cursor()
print("=== all sources ===")
for row in cur.execute(
    """
    SELECT
      COUNT(*) AS n,
      SUM(processing_state = 'RELEVANCE_REJECTED') AS rejected,
      SUM(processing_state = 'RELEVANCE_PARKED') AS parked,
      SUM(processing_state IN (
        'RELEVANCE_PASSED','SCRAPE_QUEUED','SCRAPED',
        'ENRICHMENT_STAGE1_QUEUED','ENRICHMENT_STAGE1_SUBMITTED','ENRICHMENT_STAGE1_COMPLETE',
        'ENRICHMENT_STAGE2_QUEUED','ENRICHMENT_STAGE2_CLAIMED','ENRICHMENT_STAGE2_SUBMITTED',
        'ENRICHMENT_STAGE2_COMPLETE','VECTOR_WRITE_QUEUED','INDEXED'
      )) AS paid_path,
      SUM(processing_state = 'INDEXED') AS indexed
    FROM manifest
    """
):
    n, rej, park, paid, idx = row
    print(f"n={n} rej={rej} park={park} paid_path={paid} indexed={idx}")
    print(f"not_reject={(park or 0)+(paid or 0)} ({100*((park or 0)+(paid or 0))/n:.1f}%)")
    print(f"paid_of_all={100*(paid or 0)/n:.2f}%  indexed_of_all={100*(idx or 0)/n:.2f}%")

print("\n=== github ===")
for row in cur.execute(
    """
    SELECT
      COUNT(*) AS n,
      SUM(processing_state = 'RELEVANCE_REJECTED') AS rejected,
      SUM(processing_state = 'RELEVANCE_PARKED') AS parked,
      SUM(processing_state IN (
        'RELEVANCE_PASSED','SCRAPE_QUEUED','SCRAPED',
        'ENRICHMENT_STAGE1_QUEUED','ENRICHMENT_STAGE1_SUBMITTED','ENRICHMENT_STAGE1_COMPLETE',
        'ENRICHMENT_STAGE2_QUEUED','ENRICHMENT_STAGE2_CLAIMED','ENRICHMENT_STAGE2_SUBMITTED',
        'ENRICHMENT_STAGE2_COMPLETE','VECTOR_WRITE_QUEUED','INDEXED'
      )) AS paid_path,
      SUM(processing_state = 'INDEXED') AS indexed
    FROM manifest
    WHERE source = 'github'
    """
):
    n, rej, park, paid, idx = row
    print(f"n={n} rej={rej} park={park} paid_path={paid} indexed={idx}")
    print(f"not_reject={100*((park or 0)+(paid or 0))/n:.1f}%")
    print(f"paid_of_github={100*(paid or 0)/n:.2f}%  indexed_of_github={100*(idx or 0)/n:.2f}%")
con.close()
