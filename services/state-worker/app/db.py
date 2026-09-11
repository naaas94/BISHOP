"""SQLite access: sync Alembic migrations and async aiosqlite connection pool."""

from __future__ import annotations

import asyncio
import logging
import os
import sqlite3
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import aiosqlite
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

from bishop_shared.constants import (
    SQLITE_BUSY_TIMEOUT_MS,
    SQLITE_DB_PATH,
    SQLITE_SNAPSHOT_DIRNAME,
    SQLITE_SNAPSHOT_GLOB,
)

logger = logging.getLogger(__name__)

_pool: asyncio.Queue[aiosqlite.Connection] | None = None
_pool_size: int = 5
_pool_db_path: str | None = None

_ALLOWED_INTEGRITY_PRAGMAS = frozenset({"integrity_check", "quick_check"})
_INTEGRITY_PRAGMA_ENV = "BISHOP_SQLITE_INTEGRITY_PRAGMA"
_BUSY_TIMEOUT_ENV = "BISHOP_SQLITE_BUSY_TIMEOUT_MS"
_SNAPSHOT_HINT_LIMIT = 5
_INTEGRITY_LOG_LINE_LIMIT = 20


class SqliteIntegrityError(RuntimeError):
    """Raised when the startup integrity gate refuses to open a damaged database."""


def _busy_timeout_ms() -> int:
    raw = os.environ.get(_BUSY_TIMEOUT_ENV)
    if raw is None:
        return SQLITE_BUSY_TIMEOUT_MS
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(
            f"{_BUSY_TIMEOUT_ENV} must be an integer, got {raw!r}"
        ) from exc


def _integrity_pragma() -> str:
    pragma = os.environ.get(_INTEGRITY_PRAGMA_ENV, "integrity_check")
    if pragma not in _ALLOWED_INTEGRITY_PRAGMAS:
        raise ValueError(
            f"{_INTEGRITY_PRAGMA_ENV} must be one of "
            f"{sorted(_ALLOWED_INTEGRITY_PRAGMAS)}, got {pragma!r}"
        )
    return pragma


def _repo_root() -> Path:
    """Resolve directory containing alembic.ini (repo root locally, /app in Docker)."""
    here = Path(__file__).resolve()
    candidates: list[Path] = [Path("/app")]
    candidates.extend(here.parents)
    for candidate in candidates:
        ini = candidate / "alembic.ini"
        if ini.is_file():
            logger.info("alembic config root: %s", candidate)
            return candidate
    raise FileNotFoundError("alembic.ini not found relative to app.db")


def _alembic_config(db_path: str) -> Config:
    cfg = Config(str(_repo_root() / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    return cfg


def check_integrity(db_path: str | None = None) -> list[str]:
    """Run a read-only integrity pragma. Missing or 0-byte files are treated as fresh."""
    path = db_path or SQLITE_DB_PATH
    resolved = Path(path)
    if not resolved.exists() or resolved.stat().st_size == 0:
        logger.info(
            "sqlite integrity: fresh database at %s (Alembic will create it)",
            path,
        )
        return ["ok"]

    pragma = _integrity_pragma()
    uri = f"file:{resolved.as_posix()}?mode=ro"
    try:
        conn = sqlite3.connect(uri, uri=True)
        try:
            rows = conn.execute(f"PRAGMA {pragma}").fetchall()
        finally:
            conn.close()
    except sqlite3.DatabaseError as exc:
        return [f"unreadable: {exc}"]
    # sqlite3 returns integrity_check as one newline-joined row, so split it:
    # the caller caps how many issues it logs and wants real lines to cap.
    return [line for row in rows for line in str(row[0]).splitlines() if line]


def _snapshot_recovery_hint(db_path: str) -> str:
    snapshot_dir = Path(db_path).parent / SQLITE_SNAPSHOT_DIRNAME
    parts = [
        f"snapshot_dir={snapshot_dir}",
        "remediation: python scripts/sqlite_restore.py --latest",
    ]
    if not snapshot_dir.is_dir():
        parts.append("snapshot directory is missing")
        return " ".join(parts)
    names = sorted(
        (p.name for p in snapshot_dir.glob(SQLITE_SNAPSHOT_GLOB)),
        reverse=True,
    )
    if not names:
        parts.append("snapshot directory is empty")
    else:
        newest = names[:_SNAPSHOT_HINT_LIMIT]
        parts.append(f"newest_snapshots={newest}")
    return " ".join(parts)


def enforce_integrity(db_path: str | None = None) -> None:
    """Abort startup when the live SQLite file fails its integrity check."""
    path = db_path or SQLITE_DB_PATH
    result = check_integrity(path)
    if result == ["ok"]:
        logger.info(
            "event=sqlite_integrity_ok path=%s",
            path,
            extra={"event": "sqlite_integrity_ok"},
        )
        return

    preview = result[:_INTEGRITY_LOG_LINE_LIMIT]
    logger.error(
        "sqlite integrity check failed path=%s issues=%s",
        path,
        preview,
        extra={"event": "sqlite_integrity_failed"},
    )
    logger.error(
        "sqlite integrity recovery hint: %s",
        _snapshot_recovery_hint(path),
        extra={"event": "sqlite_integrity_failed"},
    )
    raise SqliteIntegrityError(
        f"SQLite integrity check failed for {path}; refusing to start"
    )


def run_migrations(db_path: str | None = None) -> None:
    """Run Alembic upgrade head synchronously before the asyncio event loop starts."""
    path = db_path or SQLITE_DB_PATH
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    cfg = _alembic_config(path)
    command.upgrade(cfg, "head")
    timeout_ms = _busy_timeout_ms()
    engine = create_engine(f"sqlite:///{path}")
    with engine.connect() as conn:
        conn.execute(text("PRAGMA journal_mode=WAL"))
        conn.execute(text(f"PRAGMA busy_timeout = {timeout_ms}"))
        conn.commit()
    engine.dispose()


async def init_pool(db_path: str | None = None, size: int = 5) -> None:
    """Create the async connection pool and enable WAL on each connection."""
    global _pool, _pool_size, _pool_db_path
    path = db_path or SQLITE_DB_PATH
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    timeout_ms = _busy_timeout_ms()
    logger.info("sqlite busy_timeout_ms=%s", timeout_ms)
    _pool_size = size
    _pool = asyncio.Queue(maxsize=size)
    _pool_db_path = path
    for _ in range(size):
        await _pool.put(await _new_connection(path, timeout_ms))


async def _new_connection(path: str, timeout_ms: int) -> aiosqlite.Connection:
    conn = await aiosqlite.connect(path)
    # Set row_factory once here, not per call site. Callers that forgot it used to
    # get plain tuples from a shared pooled connection, and `dict(row)` then raised
    # mid-transaction. aiosqlite.Row still supports row[0], so this is compatible.
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA journal_mode=WAL")
    await conn.execute(f"PRAGMA busy_timeout = {timeout_ms}")
    await conn.commit()
    return conn


async def close_pool() -> None:
    """Drain and close all pooled connections."""
    global _pool, _pool_db_path
    if _pool is None:
        return
    while not _pool.empty():
        conn = await _pool.get()
        await conn.close()
    _pool = None
    _pool_db_path = None


async def _release(conn: aiosqlite.Connection) -> None:
    """Return a connection to the pool, never while it still holds a transaction.

    A borrower that raised mid-write used to be handed straight back with its
    write transaction open. In WAL there is exactly one writer, so that one
    connection held the write lock forever: every other connection then failed
    with "database is locked" and the next borrower of this one failed with
    "cannot start a transaction within a transaction". Five sweeps poisoned all
    five connections and every SQLite route 500'd while /health stayed green.
    """
    try:
        if conn.in_transaction:
            logger.warning(
                "rolling back a transaction left open by the previous borrower",
                extra={"event": "sqlite_pool_rollback_on_release"},
            )
            await conn.rollback()
    except Exception:
        # Rollback failed, so this connection is unusable. Replace it rather than
        # recycling it or shrinking the pool.
        logger.exception(
            "discarding unusable pooled connection",
            extra={"event": "sqlite_pool_connection_discarded"},
        )
        try:
            await conn.close()
        except Exception:
            logger.exception("failed to close unusable pooled connection")
        if _pool is not None and _pool_db_path is not None:
            await _pool.put(await _new_connection(_pool_db_path, _busy_timeout_ms()))
        return
    if _pool is not None:
        await _pool.put(conn)


@asynccontextmanager
async def get_db() -> AsyncIterator[aiosqlite.Connection]:
    """Yield a pooled aiosqlite connection (WAL mode enabled at pool init)."""
    if _pool is None:
        raise RuntimeError("Database pool not initialized; call init_pool() first")
    conn = await _pool.get()
    try:
        yield conn
    finally:
        await _release(conn)
