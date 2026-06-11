"""Unit tests for background sweep task (T5)."""

from __future__ import annotations

import asyncio
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_STATE_WORKER_ROOT = _REPO_ROOT / "services" / "state-worker"

for path in (_STATE_WORKER_ROOT, _REPO_ROOT):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

from app.db import close_pool, get_db, init_pool, run_migrations  # noqa: E402
from app.enums import DomainEnum, ProcessingState, SourceEnum  # noqa: E402
from app.models.http import ManifestBatchEntryWire  # noqa: E402
from app.sweeps import run_sweep_loop, start_sweep_task  # noqa: E402
from app.transitions import claim_manifest_poll, ingest_manifest_batch  # noqa: E402

_NOW = datetime(2026, 6, 11, 12, 0, 0, tzinfo=UTC)
_OLD = _NOW - timedelta(hours=1)
_SOURCE = "arxiv:2301.00001"


@pytest.fixture
def temp_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "bishop.db"
    run_migrations(str(db_path))
    return db_path


async def _seed_stuck_relevance_queued(db_path: Path) -> None:
    await init_pool(str(db_path), size=1)
    async with get_db() as conn:
        await ingest_manifest_batch(
            conn,
            [
                ManifestBatchEntryWire(
                    source_id=_SOURCE,
                    source=SourceEnum.ARXIV,
                    url="https://arxiv.org/abs/2301.00001",
                    title="Stuck Paper",
                    abstract="An abstract",
                    published_at=_NOW,
                    domain=DomainEnum.PROFESSIONAL.value,
                )
            ],
            discovered_at=_OLD,
        )
        await claim_manifest_poll(conn, ProcessingState.DISCOVERED)
    await close_pool()


@pytest.mark.asyncio
async def test_sweep_loop_resets_stuck_lock_state(temp_db: Path) -> None:
    await _seed_stuck_relevance_queued(temp_db)
    await init_pool(str(temp_db), size=1)
    shutdown = asyncio.Event()

    with patch("app.sweeps.SWEEP_INTERVAL_SEC", 0.01), patch(
        "app.sweeps.STUCK_THRESHOLD_SEC", 60
    ):
        task = asyncio.create_task(run_sweep_loop(shutdown))
        await asyncio.sleep(0.05)
        shutdown.set()
        await task

    async with get_db() as conn:
        conn.row_factory = __import__("aiosqlite").Row
        cursor = await conn.execute(
            "SELECT processing_state FROM manifest WHERE source_id = ?",
            (_SOURCE,),
        )
        row = await cursor.fetchone()
        assert row is not None
        assert row[0] == ProcessingState.DISCOVERED.value
    await close_pool()


@pytest.mark.asyncio
async def test_sweep_loop_does_not_block_event_loop(temp_db: Path) -> None:
    """Falsifier: sweep uses blocking time.sleep and stalls concurrent coroutines."""
    await init_pool(str(temp_db), size=1)
    shutdown = asyncio.Event()
    heartbeat: list[float] = []

    async def heartbeat_task() -> None:
        for _ in range(5):
            heartbeat.append(time.monotonic())
            await asyncio.sleep(0.01)

    with patch("app.sweeps.SWEEP_INTERVAL_SEC", 0.02), patch(
        "app.sweeps.STUCK_THRESHOLD_SEC", 999999
    ), patch("time.sleep", side_effect=AssertionError("blocking sleep used")):
        sweep_task, shutdown = start_sweep_task()
        beat_task = asyncio.create_task(heartbeat_task())
        await asyncio.sleep(0.08)
        shutdown.set()
        await sweep_task
        await beat_task

    assert len(heartbeat) == 5
    await close_pool()
