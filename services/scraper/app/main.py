"""Scraper service entrypoint — asyncio scheduler invoking ``scrape_cycle``."""

from __future__ import annotations

import asyncio
import logging

from app.config import SCRAPER_SCHEDULE_INTERVAL_SEC
from app.loop import scrape_cycle
from app.state_worker_client import StateWorkerClient

logger = logging.getLogger(__name__)


async def run_scheduler() -> None:
    """Periodically run ``scrape_cycle`` until cancelled."""
    client = StateWorkerClient()
    try:
        while True:
            await scrape_cycle(client)
            await asyncio.sleep(SCRAPER_SCHEDULE_INTERVAL_SEC)
    finally:
        await client.aclose()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    logger.info("scraper starting scheduler")
    asyncio.run(run_scheduler())


if __name__ == "__main__":
    main()
