"""Enrichment-batcher entrypoint — asyncio scheduler for stage1 and stage2 cycles."""

from __future__ import annotations

import asyncio
import logging

from app.config import ENRICHMENT_POLL_INTERVAL_SEC, LOG_LEVEL
from app.stage1_loop import stage1_cycle
from app.stage2_loop import stage2_cycle
from app.state_worker_client import StateWorkerClient

logger = logging.getLogger(__name__)


async def run_scheduler() -> None:
    """Periodically run stage1 and stage2 cycles until cancelled."""
    client = StateWorkerClient()
    try:
        while True:
            await asyncio.gather(
                stage1_cycle(state_client=client),
                stage2_cycle(state_client=client),
            )
            await asyncio.sleep(ENRICHMENT_POLL_INTERVAL_SEC)
    finally:
        await client.aclose()


def main() -> None:
    logging.basicConfig(level=getattr(logging, LOG_LEVEL.upper(), logging.INFO))
    logger.info("enrichment-batcher starting scheduler")
    asyncio.run(run_scheduler())


if __name__ == "__main__":
    main()
