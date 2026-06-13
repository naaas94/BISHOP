"""Startup scan — recover in-flight pre-filter batches from state-worker."""

from __future__ import annotations

import logging

from app.clients.state_worker import StateWorkerClient
from app.models import PRE_FILTER_BATCH_TYPE, BatchRecordWire

logger = logging.getLogger(__name__)


def _is_pre_filter_batch(batch: BatchRecordWire) -> bool:
    if batch.batch_type == PRE_FILTER_BATCH_TYPE:
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
    """GET /batches?status=submitted,processing and return pre_filter batches only."""
    batches = await state_client.get_in_flight_batches()
    tracked = [batch for batch in batches if _is_pre_filter_batch(batch)]
    logger.info(
        "startup scan complete",
        extra={
            "event": "startup_scan",
            "total": len(batches),
            "tracked": len(tracked),
        },
    )
    return tracked
