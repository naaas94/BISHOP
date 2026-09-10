"""Scheduled scrape cycle per §10.3, plus §18.4 chunked backfill on cold start."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta

import httpx

from bishop_shared.enums import SourceEnum
from bishop_shared.scraper_config import BACKFILL_CONFIG

from app.adapters.base import SourceAdapter
from app.adapters.registry import ADAPTER_REGISTRY
from app.config import (
    BISHOP_BACKFILL_CHUNK_DAYS,
    BISHOP_BACKFILL_ENABLED,
    BISHOP_BACKFILL_INTER_CHUNK_DELAY_SEC,
)
from app.exceptions import EscalatableError, PermanentFailureError, RetryExhaustedError
from app.failure_envelope import failure_envelope, log_permanent_failure
from app.state_worker_client import StateWorkerClient

logger = logging.getLogger(__name__)


def compute_backfill_chunk_starts(
    *,
    window_days: int,
    chunk_days: int,
    now: datetime,
) -> list[datetime]:
    """Ascending ``since`` boundaries stepping ``chunk_days`` at a time back to
    ``window_days`` before ``now`` (§18.4: "fetch N days at a time").

    Each boundary is consumed as an adapter ``since`` value — adapters fetch
    ``[since, now]`` (no ``until`` parameter exists on the frozen adapter
    interface), so later chunks are supersets-minus-earlier-days rather than
    disjoint windows; the manifest insert path dedupes by ``source_id``, and
    the point of chunking is bounding single-request volume plus giving
    pre-filter an inter-chunk pause, not eliminating re-fetched rows. See
    ``.dev/decision-logs/m8-hardening-scale/T8-backfill-enable.md``.
    """
    if window_days <= 0:
        return [now]
    if chunk_days <= 0:
        return [now - timedelta(days=window_days)]

    starts: list[datetime] = []
    remaining = window_days
    while remaining > 0:
        starts.append(now - timedelta(days=remaining))
        remaining -= chunk_days
    return starts


async def _run_backfill_chunks(
    adapter: SourceAdapter,
    *,
    client: StateWorkerClient,
    source: SourceEnum,
    now: datetime,
) -> int:
    """Chunk-fetch backfill manifest rows: write each chunk before sleeping
    ``BISHOP_BACKFILL_INTER_CHUNK_DELAY_SEC`` so pre-filter can catch up
    before the next fetch (§18.4)."""
    config = BACKFILL_CONFIG.get(source.value)
    window_days = config.window_days if config is not None else 0
    chunk_starts = compute_backfill_chunk_starts(
        window_days=window_days,
        chunk_days=BISHOP_BACKFILL_CHUNK_DAYS,
        now=now,
    )
    total_inserted = 0
    last_index = len(chunk_starts) - 1
    for index, chunk_start in enumerate(chunk_starts):
        entries = await failure_envelope(adapter.fetch_manifest, since=chunk_start, source=source)
        if entries:
            result = await client.post_manifest_batch(entries)
            total_inserted += result.inserted
            logger.info(
                "backfill chunk complete",
                extra={
                    "event": "backfill_chunk_complete",
                    "source": source.value,
                    "chunk_start": chunk_start.isoformat(),
                    "chunk_end": now.isoformat(),
                    "chunk_index": index,
                    "chunk_count": len(chunk_starts),
                    "inserted": result.inserted,
                    "skipped": result.skipped,
                },
            )
        else:
            logger.info(
                "backfill chunk empty",
                extra={
                    "event": "backfill_chunk_complete",
                    "source": source.value,
                    "chunk_start": chunk_start.isoformat(),
                    "chunk_end": now.isoformat(),
                    "chunk_index": index,
                    "chunk_count": len(chunk_starts),
                    "inserted": 0,
                    "skipped": 0,
                },
            )
        if index < last_index:
            await asyncio.sleep(BISHOP_BACKFILL_INTER_CHUNK_DELAY_SEC)
    return total_inserted


async def scrape_cycle(client: StateWorkerClient | None = None) -> None:
    """Run one discovery pass for every adapter in ``ADAPTER_REGISTRY``."""
    owns_client = client is None
    if client is None:
        client = StateWorkerClient()

    try:
        logger.info("scrape cycle started", extra={"event": "scrape_cycle_start"})
        for AdapterClass in ADAPTER_REGISTRY:
            await _scrape_adapter(AdapterClass, client)
        logger.info("scrape cycle complete", extra={"event": "scrape_cycle_complete"})
    finally:
        if owns_client:
            await client.aclose()


async def _scrape_adapter(
    AdapterClass: type[SourceAdapter],
    client: StateWorkerClient,
) -> None:
    adapter = AdapterClass()
    source = adapter.source
    try:
        snapshot = await client.get_scraper_state(source)
        last_run = snapshot.last_successful_run_at
        now = datetime.now(UTC)
        if last_run is None and BISHOP_BACKFILL_ENABLED:
            logger.info(
                "backfill cycle started",
                extra={"event": "backfill_cycle_start", "source": source.value},
            )
            await _run_backfill_chunks(adapter, client=client, source=source, now=now)
        else:
            entries = await failure_envelope(
                adapter.fetch_manifest,
                since=last_run,
                source=source,
            )
            if not entries:
                logger.warning("empty manifest fetch", extra={"source": source.value})
            result = await client.post_manifest_batch(entries)
            logger.info(
                "manifest batch posted",
                extra={
                    "source": source.value,
                    "inserted": result.inserted,
                    "skipped": result.skipped,
                },
            )
        await client.post_scraper_state(source, timestamp=now)
        logger.info("scraper state updated", extra={"source": source.value})
    except PermanentFailureError as exc:
        log_permanent_failure(source, exc)
    except EscalatableError as exc:
        logger.error(
            "escalatable adapter failure",
            extra={
                "source": source.value,
                "http_status": exc.http_status,
                "event": "escalatable_failure",
            },
        )
    except RetryExhaustedError as exc:
        logger.error(
            "adapter retry exhausted",
            extra={
                "source": source.value,
                "attempt": exc.attempt,
                "event": "retry_exhausted",
            },
        )
    except httpx.HTTPStatusError as exc:
        logger.error(
            "state-worker HTTP error",
            extra={
                "source": source.value,
                "http_status": exc.response.status_code,
            },
        )
