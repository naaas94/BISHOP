"""Unit tests for state-worker database layer (migrations + async pool)."""

import asyncio
import sqlite3
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_STATE_WORKER_ROOT = _REPO_ROOT / "services" / "state-worker"

for path in (_STATE_WORKER_ROOT, _REPO_ROOT):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

from app.db import close_pool, get_db, init_pool, run_migrations  # noqa: E402

EXPECTED_TABLES = frozenset(
    {"manifest", "entries", "batches", "error_log", "oov_tags_log", "scraper_state"}
)


@pytest.fixture
def temp_db(tmp_path: Path) -> Path:
    return tmp_path / "bishop.db"


def test_migrations_create_six_tables(temp_db: Path) -> None:
    run_migrations(str(temp_db))
    conn = sqlite3.connect(temp_db)
    try:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    finally:
        conn.close()
    assert EXPECTED_TABLES.issubset(tables)


def test_wal_mode_enabled(temp_db: Path) -> None:
    async def _check_wal() -> None:
        run_migrations(str(temp_db))
        await init_pool(str(temp_db), size=1)
        try:
            async with get_db() as conn:
                cursor = await conn.execute("PRAGMA journal_mode")
                row = await cursor.fetchone()
                assert row is not None
                assert row[0].lower() == "wal"
        finally:
            await close_pool()

    asyncio.run(_check_wal())
