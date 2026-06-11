"""Background lock-state recovery and retry sweeps."""

from __future__ import annotations

import asyncio
import logging

from app.config import STUCK_THRESHOLD_SEC, SWEEP_INTERVAL_SEC
from app.db import get_db
from app.transitions import run_lock_state_recovery_sweep, run_retry_sweep

logger = logging.getLogger(__name__)


async def run_sweep_loop(shutdown: asyncio.Event) -> None:
    """Periodic sweep until shutdown is set."""
    while not shutdown.is_set():
        try:
            async with get_db() as conn:
                sweep_reset_count = await run_lock_state_recovery_sweep(
                    conn, STUCK_THRESHOLD_SEC
                )
                retry_requeue_count = await run_retry_sweep(conn)
            if sweep_reset_count:
                logger.info(
                    "lock_state_sweep complete",
                    extra={"sweep_reset_count": sweep_reset_count},
                )
            if retry_requeue_count:
                logger.info(
                    "retry_sweep complete",
                    extra={"retry_requeue_count": retry_requeue_count},
                )
        except Exception:
            logger.exception("sweep iteration failed")
        try:
            await asyncio.wait_for(shutdown.wait(), timeout=SWEEP_INTERVAL_SEC)
        except TimeoutError:
            pass


def start_sweep_task() -> tuple[asyncio.Task[None], asyncio.Event]:
    shutdown = asyncio.Event()
    task = asyncio.create_task(run_sweep_loop(shutdown))
    return task, shutdown
