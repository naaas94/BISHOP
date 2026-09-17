"""Scraper service entrypoint — asyncio scheduler invoking scrape and release."""

from __future__ import annotations

import asyncio
import logging

from app.config import (
    BISHOP_HARVEST_RELEASE_INTERVAL_SEC,
    SCRAPER_SCHEDULE_INTERVAL_SEC,
)
from app.harvest_release import release_once
from app.loop import scrape_cycle
from app.state_worker_client import StateWorkerClient

logger = logging.getLogger(__name__)


async def _scrape_loop(client: StateWorkerClient) -> None:
    while True:
        await scrape_cycle(client)
        await asyncio.sleep(SCRAPER_SCHEDULE_INTERVAL_SEC)


async def _release_loop(client: StateWorkerClient) -> None:
    while True:
        try:
            await release_once(client)
        except Exception:
            logger.exception(
                "harvest release tick failed",
                extra={"event": "harvest_release_failed"},
            )
        await asyncio.sleep(BISHOP_HARVEST_RELEASE_INTERVAL_SEC)


async def run_scheduler() -> None:
    """Run scrape and harvest-release loops until cancelled."""
    client = StateWorkerClient()
    try:
        await asyncio.gather(
            _scrape_loop(client),
            _release_loop(client),
        )
    finally:
        await client.aclose()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    logger.info("scraper starting scheduler")
    asyncio.run(run_scheduler())


if __name__ == "__main__":
    main()
