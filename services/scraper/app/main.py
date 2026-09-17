"""Scraper service entrypoint — asyncio scheduler invoking scrape and release."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta

import httpx

from app.config import (
    BISHOP_HARVEST_MILL_INTERVAL_SEC,
    BISHOP_HARVEST_RELEASE_INTERVAL_SEC,
    BISHOP_HARVEST_SLICE_BUDGET_SEC,
    SCRAPER_SCHEDULE_INTERVAL_SEC,
)
from app.harvest_github import harvest_github_slices
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


async def _mill_loop() -> None:
    """Own-cadence GitHub Search harvest — no longer hitchhikes on scrape_cycle."""
    while True:
        try:
            deadline = datetime.now(UTC) + timedelta(
                seconds=BISHOP_HARVEST_SLICE_BUDGET_SEC
            )
            async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as harvest_client:
                await harvest_github_slices(
                    http_client=harvest_client,
                    deadline=deadline,
                )
        except Exception:
            logger.exception(
                "github harvest mill tick failed",
                extra={"event": "harvest_mill_failed"},
            )
        await asyncio.sleep(BISHOP_HARVEST_MILL_INTERVAL_SEC)


async def run_scheduler() -> None:
    """Run scrape, harvest-release, and harvest-mill loops until cancelled."""
    client = StateWorkerClient()
    try:
        await asyncio.gather(
            _scrape_loop(client),
            _release_loop(client),
            _mill_loop(),
        )
    finally:
        await client.aclose()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    logger.info("scraper starting scheduler")
    asyncio.run(run_scheduler())


if __name__ == "__main__":
    main()
