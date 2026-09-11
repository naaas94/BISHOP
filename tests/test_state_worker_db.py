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

from app import db as db_mod  # noqa: E402
from app.db import close_pool, get_db, init_pool, run_migrations  # noqa: E402
from bishop_shared.constants import SQLITE_BUSY_TIMEOUT_MS  # noqa: E402

EXPECTED_TABLES = frozenset(
    {"manifest", "entries", "batches", "error_log", "oov_tags_log", "scraper_state"}
)


@pytest.fixture
def temp_db(tmp_path: Path) -> Path:
    return tmp_path / "bishop.db"


def test_repo_root_resolves_shallow_app_layout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Falsifier: eager parents[3] breaks Docker layout (/app/app/db.py)."""
    shallow_root = tmp_path / "app"
    app_pkg = shallow_root / "app"
    app_pkg.mkdir(parents=True)
    (shallow_root / "alembic.ini").write_text("[alembic]\n", encoding="utf-8")
    fake_db_py = app_pkg / "db.py"
    fake_db_py.write_text("", encoding="utf-8")
    monkeypatch.setattr(db_mod, "__file__", str(fake_db_py))
    assert db_mod._repo_root() == shallow_root


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


def test_busy_timeout_applied_to_pooled_connections(temp_db: Path) -> None:
    async def _check() -> None:
        run_migrations(str(temp_db))
        await init_pool(str(temp_db), size=1)
        try:
            async with get_db() as conn:
                cursor = await conn.execute("PRAGMA busy_timeout")
                row = await cursor.fetchone()
                assert row is not None
                assert int(row[0]) == SQLITE_BUSY_TIMEOUT_MS
        finally:
            await close_pool()

    asyncio.run(_check())


def test_busy_timeout_env_override_honored(
    temp_db: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("BISHOP_SQLITE_BUSY_TIMEOUT_MS", "1234")

    async def _check() -> None:
        run_migrations(str(temp_db))
        await init_pool(str(temp_db), size=1)
        try:
            async with get_db() as conn:
                cursor = await conn.execute("PRAGMA busy_timeout")
                row = await cursor.fetchone()
                assert row is not None
                assert int(row[0]) == 1234
        finally:
            await close_pool()

    asyncio.run(_check())


def test_busy_timeout_non_integer_env_raises(
    temp_db: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("BISHOP_SQLITE_BUSY_TIMEOUT_MS", "not-an-int")

    async def _check() -> None:
        with pytest.raises(ValueError, match="BISHOP_SQLITE_BUSY_TIMEOUT_MS"):
            await init_pool(str(temp_db), size=1)

    asyncio.run(_check())


def test_migrations_do_not_disable_app_loggers(temp_db: Path) -> None:
    """Falsifier: Alembic's fileConfig defaults to disable_existing_loggers=True.

    run_migrations runs in-process at startup, so that default silenced every
    logger created at import time and the 2026-09-11 corruption produced 500s
    with an empty log. Regression guard for alembic/env.py.
    """
    import logging

    names = ("app.main", "app.db", "app.routers.entries")
    loggers = [logging.getLogger(name) for name in names]
    for logger in loggers:
        logger.disabled = False

    run_migrations(str(temp_db))

    still_enabled = {logger.name: not logger.disabled for logger in loggers}
    assert all(still_enabled.values()), f"loggers disabled by migrations: {still_enabled}"
    assert all(logger.isEnabledFor(logging.ERROR) for logger in loggers)
