"""Vector-write cycle: poll VECTOR_WRITE_QUEUED → index_entry per row."""

from __future__ import annotations

import logging

import httpx

from app.index_entry import IndexStores, index_entry
from app.state_worker_client import StateWorkerClient

logger = logging.getLogger(__name__)


async def index_cycle(
    state_client: StateWorkerClient | None = None,
    stores: IndexStores | None = None,
) -> None:
    """Run one vector-write cycle for VECTOR_WRITE_QUEUED entries."""
    owns_client = state_client is None
    if state_client is None:
        state_client = StateWorkerClient()

    try:
        logger.info("index cycle started", extra={"event": "index_cycle_start"})
        try:
            poll = await state_client.poll_vector_write_queued()
        except httpx.HTTPStatusError as exc:
            logger.error(
                "state-worker poll failed",
                extra={
                    "http_status": exc.response.status_code,
                    "event": "state_worker_error",
                },
            )
            return

        if not poll.entries:
            logger.info(
                "empty entry poll",
                extra={"claimed_count": poll.claimed_count, "event": "empty_poll"},
            )
            return

        if stores is None:
            raise RuntimeError("index_cycle requires IndexStores when processing entries")

        for entry in poll.entries:
            await index_entry(entry, stores, state_client)

        logger.info("index cycle complete", extra={"event": "index_cycle_complete"})
    finally:
        if owns_client:
            await state_client.aclose()
