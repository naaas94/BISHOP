"""Content-scraper entrypoint — asyncio scheduler invoking ``content_scrape_cycle``."""

from __future__ import annotations

import asyncio
import logging

from app.config import CONTENT_SCRAPE_POLL_INTERVAL_SEC, LOG_LEVEL
from app.loop import content_scrape_cycle
from app.state_worker_client import StateWorkerClient

logger = logging.getLogger(__name__)


async def run_scheduler() -> None:
    """Periodically run ``content_scrape_cycle`` until cancelled."""
    client = StateWorkerClient()
    try:
        while True:
            await content_scrape_cycle(state_client=client)
            await asyncio.sleep(CONTENT_SCRAPE_POLL_INTERVAL_SEC)
    finally:
        await client.aclose()


def main() -> None:
    logging.basicConfig(level=getattr(logging, LOG_LEVEL.upper(), logging.INFO))
    logger.info("content-scraper starting scheduler")
    asyncio.run(run_scheduler())


if __name__ == "__main__":
    main()
