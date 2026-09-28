"""Shared read-only helpers for Insights Manager queries.

Every connection is `mode=ro`. Nothing here writes bishop.db or the harvest ledger.
Path resolution mirrors scripts/sqlite_snapshot.py: prefer `sqlite_live/` when it
exists (this host since 2026-09-11), because `sqlite/bishop.db` is a stale file here.
"""

import argparse
import os
import sqlite3
from pathlib import Path

DATA_ROOT = Path(os.environ.get("BISHOP_DATA_ROOT", "C:/Users/Ale/bishop_data"))

FAILED_STATES = (
    "SCRAPE_FAILED",
    "ENRICHMENT_STAGE1_FAILED",
    "ENRICHMENT_STAGE2_FAILED",
    "VECTOR_WRITE_FAILED",
    "ESCALATION_FLAGGED",
    "PERMANENTLY_FAILED",
)


def bishop_db_path() -> Path:
    live = DATA_ROOT / "sqlite_live" / "bishop.db"
    return live if live.exists() else DATA_ROOT / "sqlite" / "bishop.db"


def ledger_path() -> Path:
    return DATA_ROOT / "harvest" / "ledger.sqlite"


def _ro(path: Path) -> sqlite3.Connection:
    if not path.exists():
        raise SystemExit(f"missing: {path}")
    return sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)


def bishop() -> sqlite3.Connection:
    return _ro(bishop_db_path())


def ledger() -> sqlite3.Connection:
    return _ro(ledger_path())


def window_args(description: str, default_days: int = 1, clock: bool = False) -> argparse.Namespace:
    """`start` inclusive, `end` exclusive, UTC dates (YYYY-MM-DD)."""
    p = argparse.ArgumentParser(description=description)
    p.add_argument("start", help="UTC date, inclusive")
    p.add_argument("end", nargs="?", help=f"UTC date, exclusive (default start + {default_days}d)")
    if clock:
        p.add_argument("--clock", choices=("discovered_at", "published_at"), default="discovered_at")
    a = p.parse_args()
    if a.end is None:
        from datetime import date, timedelta

        a.end = (date.fromisoformat(a.start) + timedelta(days=default_days)).isoformat()
    return a


def header(title: str, **slots: str) -> None:
    """Print frozen-at stamp and DB paths so a run file can paste them verbatim."""
    from datetime import datetime, timezone

    print(f"# {title}")
    print(f"read_at_utc: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}")
    print(f"bishop_db: {bishop_db_path().as_posix()}")
    print(f"ledger: {ledger_path().as_posix()}")
    for k, v in slots.items():
        print(f"{k}: {v}")
    print()
