"""Startup scan — recover in-flight batches from state-worker."""

from __future__ import annotations

import logging

from app.clients.state_worker import StateWorkerClient
from app.models import TRACKED_BATCH_TYPES, BatchRecordWire

logger = logging.getLogger(__name__)


def _is_tracked_batch(batch: BatchRecordWire) -> bool:
    if batch.batch_type in TRACKED_BATCH_TYPES:
        return True
    logger.warning(
        "batch_type rejected",
        extra={
            "batch_id": batch.batch_id,
            "batch_type": batch.batch_type,
            "event": "enrichment_batch_rejected",
        },
    )
    return False


async def startup_scan(state_client: StateWorkerClient) -> list[BatchRecordWire]:
    """GET /batches?status=submitted,processing and return tracked batch types."""
    batches = await state_client.get_in_flight_batches()
    tracked = [batch for batch in batches if _is_tracked_batch(batch)]
    logger.info(
        "startup scan complete",
        extra={
            "event": "startup_scan",
            "total": len(batches),
            "tracked": len(tracked),
        },
    )
    return tracked
