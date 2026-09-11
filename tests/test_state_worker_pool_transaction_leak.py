"""Regression tests for the 2026-09-11 pooled-connection transaction leak.

Failure chain being guarded (see .dev/decision-logs/ops/sqlite-snapshot-and-integrity-gate.md):
a borrower raised mid-write, `async with get_db()` returned the connection to the
pool with its write transaction still open, that connection held the single WAL
write lock forever, and every subsequent writer failed with "database is locked"
while the next borrower of that connection failed with "cannot start a
transaction within a transaction". `/health` stayed green throughout.
"""

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
from app.transitions import run_retry_sweep  # noqa: E402


@pytest.fixture
def temp_db(tmp_path: Path) -> Path:
    return tmp_path / "bishop.db"


def test_pooled_connection_row_factory_is_set(temp_db: Path) -> None:
    """dict(row) must work on a pooled connection without a per-call-site opt-in."""

    async def _check() -> None:
        run_migrations(str(temp_db))
        await init_pool(str(temp_db), size=1)
        try:
            async with get_db() as conn:
                cursor = await conn.execute("SELECT version_num FROM alembic_version")
                row = await cursor.fetchone()
                assert row is not None
                assert dict(row)["version_num"]
                # Index access must keep working for existing call sites.
                assert row[0]
        finally:
            await close_pool()

    asyncio.run(_check())


def test_open_transaction_is_rolled_back_on_release(temp_db: Path) -> None:
    """A borrower that leaves a write transaction open must not poison the pool."""

    async def _check() -> None:
        run_migrations(str(temp_db))
        await init_pool(str(temp_db), size=1)
        try:
            # Borrower 1 opens a write transaction and abandons it.
            async with get_db() as conn:
                await conn.execute("BEGIN")
                await conn.execute(
                    "INSERT INTO scraper_state (source, updated_at) VALUES (?, ?)",
                    ("arxiv", "2026-09-11T00:00:00+00:00"),
                )
                assert conn.in_transaction

            # Borrower 2 gets the same connection back and must be able to BEGIN.
            async with get_db() as conn:
                assert not conn.in_transaction
                await conn.execute("BEGIN")
                await conn.execute("COMMIT")
                # The abandoned write must have been rolled back, not committed.
                cursor = await conn.execute("SELECT COUNT(*) FROM scraper_state")
                row = await cursor.fetchone()
                assert row is not None
                assert row[0] == 0
        finally:
            await close_pool()

    asyncio.run(_check())


def test_raising_borrower_does_not_hold_the_write_lock(temp_db: Path) -> None:
    """The real deadlock: one failed writer starved every other connection."""

    async def _check() -> None:
        run_migrations(str(temp_db))
        await init_pool(str(temp_db), size=2)
        try:
            with pytest.raises(RuntimeError, match="boom"):
                async with get_db() as conn:
                    await conn.execute("BEGIN")
                    await conn.execute(
                        "INSERT INTO scraper_state (source, updated_at) VALUES (?, ?)",
                        ("github", "2026-09-11T00:00:00+00:00"),
                    )
                    raise RuntimeError("boom")

            # A different pooled connection must still be able to write.
            async with get_db() as conn:
                await conn.execute("BEGIN")
                await conn.execute(
                    "INSERT INTO scraper_state (source, updated_at) VALUES (?, ?)",
                    ("lesswrong", "2026-09-11T00:00:00+00:00"),
                )
                await conn.execute("COMMIT")
        finally:
            await close_pool()

    asyncio.run(_check())


def test_retry_sweep_rolls_back_and_does_not_leak(temp_db: Path) -> None:
    """run_retry_sweep raised after its UPDATE and left the transaction open."""

    async def _check() -> None:
        run_migrations(str(temp_db))
        await init_pool(str(temp_db), size=1)
        try:
            async with get_db() as conn:
                await conn.execute(
                    """
                    INSERT INTO manifest (
                        source_id, source, url, title, discovered_at, domain,
                        processing_state, retry_count, next_retry_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "arxiv:2609.00001",
                        "arxiv",
                        "https://arxiv.org/abs/2609.00001",
                        "leak probe",
                        "2026-09-11T00:00:00+00:00",
                        "professional",
                        "SCRAPE_FAILED",
                        0,
                        "2026-01-01T00:00:00+00:00",
                    ),
                )
                await conn.commit()

            # The sweep now sets row_factory itself, so dict(row) cannot raise.
            async with get_db() as conn:
                requeued = await run_retry_sweep(conn)
                assert requeued == 1

            async with get_db() as conn:
                assert not conn.in_transaction
                cursor = await conn.execute(
                    "SELECT processing_state FROM manifest WHERE source_id = ?",
                    ("arxiv:2609.00001",),
                )
                row = await cursor.fetchone()
                assert row is not None
                # RETRY_TARGET_MAP sends SCRAPE_FAILED back to the work-ready
                # state; the poll claim is what moves it on to SCRAPE_QUEUED.
                assert row["processing_state"] == "RELEVANCE_PASSED"
        finally:
            await close_pool()

    asyncio.run(_check())


def test_retry_sweep_rollback_on_failure(temp_db: Path) -> None:
    """If the sweep raises mid-loop, its partial UPDATE must not survive."""

    async def _check() -> None:
        run_migrations(str(temp_db))
        await init_pool(str(temp_db), size=1)
        try:
            async with get_db() as conn:
                await conn.execute(
                    """
                    INSERT INTO manifest (
                        source_id, source, url, title, discovered_at, domain,
                        processing_state, retry_count, next_retry_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "arxiv:2609.00002",
                        "arxiv",
                        "https://arxiv.org/abs/2609.00002",
                        "rollback probe",
                        "2026-09-11T00:00:00+00:00",
                        "professional",
                        "SCRAPE_FAILED",
                        0,
                        "2026-01-01T00:00:00+00:00",
                    ),
                )
                await conn.commit()

            import app.transitions as transitions

            async def _boom(*_args: object, **_kwargs: object) -> None:
                raise sqlite3.OperationalError("simulated mid-sweep failure")

            original = transitions._fetch_entry
            transitions._fetch_entry = _boom  # type: ignore[assignment]
            try:
                async with get_db() as conn:
                    with pytest.raises(sqlite3.OperationalError):
                        await run_retry_sweep(conn)
            finally:
                transitions._fetch_entry = original  # type: ignore[assignment]

            async with get_db() as conn:
                assert not conn.in_transaction
                cursor = await conn.execute(
                    "SELECT processing_state FROM manifest WHERE source_id = ?",
                    ("arxiv:2609.00002",),
                )
                row = await cursor.fetchone()
                assert row is not None
                # Rolled back, so still the failed state rather than requeued.
                assert row["processing_state"] == "SCRAPE_FAILED"
        finally:
            await close_pool()

    asyncio.run(_check())
