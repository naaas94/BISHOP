"""SQLite access: sync Alembic migrations and async aiosqlite connection pool."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import aiosqlite
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

from bishop_shared.constants import SQLITE_DB_PATH

_pool: asyncio.Queue[aiosqlite.Connection] | None = None
_pool_size: int = 5


def _repo_root() -> Path:
    """Resolve directory containing alembic.ini (repo root locally, /app in Docker)."""
    here = Path(__file__).resolve()
    for candidate in (here.parents[3], here.parents[1], Path("/app")):
        if (candidate / "alembic.ini").is_file():
            return candidate
    raise FileNotFoundError("alembic.ini not found relative to app.db")


def _alembic_config(db_path: str) -> Config:
    cfg = Config(str(_repo_root() / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    return cfg


def run_migrations(db_path: str | None = None) -> None:
    """Run Alembic upgrade head synchronously before the asyncio event loop starts."""
    path = db_path or SQLITE_DB_PATH
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    cfg = _alembic_config(path)
    command.upgrade(cfg, "head")
    engine = create_engine(f"sqlite:///{path}")
    with engine.connect() as conn:
        conn.execute(text("PRAGMA journal_mode=WAL"))
        conn.commit()
    engine.dispose()


async def init_pool(db_path: str | None = None, size: int = 5) -> None:
    """Create the async connection pool and enable WAL on each connection."""
    global _pool, _pool_size
    path = db_path or SQLITE_DB_PATH
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    _pool_size = size
    _pool = asyncio.Queue(maxsize=size)
    for _ in range(size):
        conn = await aiosqlite.connect(path)
        await conn.execute("PRAGMA journal_mode=WAL")
        await conn.commit()
        await _pool.put(conn)


async def close_pool() -> None:
    """Drain and close all pooled connections."""
    global _pool
    if _pool is None:
        return
    while not _pool.empty():
        conn = await _pool.get()
        await conn.close()
    _pool = None


@asynccontextmanager
async def get_db() -> AsyncIterator[aiosqlite.Connection]:
    """Yield a pooled aiosqlite connection (WAL mode enabled at pool init)."""
    if _pool is None:
        raise RuntimeError("Database pool not initialized; call init_pool() first")
    conn = await _pool.get()
    try:
        yield conn
    finally:
        await _pool.put(conn)
