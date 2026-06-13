"""Pre-filter worker entrypoint — asyncio scheduler invoking ``prefilter_cycle``."""

from __future__ import annotations

import asyncio
import logging

from app.config import LOG_LEVEL, PREFILTER_POLL_INTERVAL_SEC
from app.loop import prefilter_cycle
from app.state_worker_client import StateWorkerClient

logger = logging.getLogger(__name__)


async def run_scheduler() -> None:
    """Periodically run ``prefilter_cycle`` until cancelled."""
    client = StateWorkerClient()
    try:
        while True:
            await prefilter_cycle(state_client=client)
            await asyncio.sleep(PREFILTER_POLL_INTERVAL_SEC)
    finally:
        await client.aclose()


def main() -> None:
    logging.basicConfig(level=getattr(logging, LOG_LEVEL.upper(), logging.INFO))
    logger.info("pre-filter-worker starting scheduler")
    asyncio.run(run_scheduler())


if __name__ == "__main__":
    main()
