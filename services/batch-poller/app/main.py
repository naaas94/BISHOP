"""Batch-poller service entrypoint — startup scan then Anthropic poll loop."""

from __future__ import annotations

import asyncio
import logging
import os

from app.clients.anthropic import AnthropicBatchPollerClient
from app.clients.state_worker import StateWorkerClient
from app.loop import poll_loop

logger = logging.getLogger(__name__)


async def run_poller() -> None:
    state_client = StateWorkerClient()
    anthropic_client = AnthropicBatchPollerClient()
    try:
        await poll_loop(state_client, anthropic_client)
    finally:
        await state_client.aclose()


def main() -> None:
    level = os.environ.get("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(level=level)
    logger.info("batch-poller starting")
    asyncio.run(run_poller())


if __name__ == "__main__":
    main()
