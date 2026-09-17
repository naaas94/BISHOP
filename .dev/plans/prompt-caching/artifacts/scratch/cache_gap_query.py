import sqlite3
from pathlib import Path

p = Path("C:/Users/Ale/bishop_data/sqlite_live/bishop.db")
con = sqlite3.connect(f"file:{p.as_posix()}?mode=ro", uri=True)
con.row_factory = sqlite3.Row

print("=== github INDEXED sample (score desc) ===")
for r in con.execute(
    """
    select source_id, title, relevance_score, entry_type, tags,
           substr(pre_filter_rationale, 1, 180) as rationale
    from entries
    where source_id like 'github:%' and processing_state = 'INDEXED'
    order by relevance_score desc
    limit 12
    """
):
    print(dict(r))

print("=== github INDEXED score histogram ===")
for r in con.execute(
    """
    select
      case
        when relevance_score is null then 'null'
        when relevance_score < 0.3 then '<0.3'
        when relevance_score < 0.5 then '0.3-0.5'
        when relevance_score < 0.7 then '0.5-0.7'
        else '>=0.7'
      end as band,
      count(*) n
    from entries
    where source_id like 'github:%' and processing_state = 'INDEXED'
    group by 1
    order by 1
    """
):
    print(dict(r))

print("=== github funnel ===")
for r in con.execute(
    """
    select processing_state, count(*) n
    from manifest
    where source = 'github'
    group by 1
    order by n desc
    """
):
    print(dict(r))

print("=== github parked sample ===")
for r in con.execute(
    """
    select source_id, title, substr(pre_filter_rationale, 1, 160) as rationale
    from manifest
    where source = 'github' and processing_state = 'RELEVANCE_PARKED'
    limit 8
    """
):
    print(dict(r))
