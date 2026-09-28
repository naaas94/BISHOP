"""Scheduled scrape cycle per §10.3, plus §18.4 chunked backfill on cold start."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta

import httpx

from bishop_shared.enums import SourceEnum
from bishop_shared.scraper_config import BACKFILL_CONFIG

from app.adapters.arxiv import ARXIV_INTER_PAGE_DELAY_SEC
from app.adapters.base import SourceAdapter
from app.adapters.registry import ADAPTER_REGISTRY
from app.config import (
    BISHOP_BACKFILL_CHUNK_DAYS,
    BISHOP_BACKFILL_ENABLED,
    BISHOP_BACKFILL_INTER_CHUNK_DELAY_SEC,
    BISHOP_BACKFILL_WINDOW_OVERRIDE_DAYS,
)
from app.exceptions import EscalatableError, PermanentFailureError, RetryExhaustedError
from app.failure_envelope import failure_envelope, log_permanent_failure
from app.models import ManifestBatchResult, ManifestIngestEntry
from app.state_worker_client import StateWorkerClient

logger = logging.getLogger(__name__)

# One page of the arXiv export cap. A caught-up window can be thousands of
# rows; one POST of all of them is a large body. Chunks are idempotent, so a
# failed later chunk retries as skips and still does not stamp the cursor.
MANIFEST_POST_CHUNK = 100


def resolve_backfill_window_days(source: str) -> int:
    """BACKFILL_CONFIG.window_days, or the soft-launch overlay when set."""
    if BISHOP_BACKFILL_WINDOW_OVERRIDE_DAYS is not None:
        return BISHOP_BACKFILL_WINDOW_OVERRIDE_DAYS
    config = BACKFILL_CONFIG.get(source)
    return config.window_days if config is not None else 0


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


def _utc_day_start(value: datetime) -> datetime:
    utc = value.astimezone(UTC)
    return utc.replace(hour=0, minute=0, second=0, microsecond=0)


def _utc_day_end(day_start: datetime) -> datetime:
    return day_start.replace(hour=23, minute=59, second=59, microsecond=0)


def arxiv_days_to_scrape(
    last_run: datetime | None,
    now: datetime,
    *,
    window_days: int,
) -> list[datetime]:
    """UTC midnights still to fetch, oldest first, through today.

    The cursor counts only when it sits at 23:59:59 of a day. Anything earlier
    is a jump (the old stamp-now path). A jump restarts at the overlay floor
    so days that only received a partial page are fetched in full.
    """
    today = _utc_day_start(now)
    floor = today - timedelta(days=window_days)
    if last_run is None:
        start = floor
    else:
        last = last_run.astimezone(UTC)
        day_start = _utc_day_start(last)
        if last >= _utc_day_end(day_start):
            start = day_start + timedelta(days=1)
        else:
            start = floor
    if start < floor:
        start = floor
    days: list[datetime] = []
    cursor = start
    while cursor <= today:
        days.append(cursor)
        cursor += timedelta(days=1)
    return days


async def _scrape_arxiv_days(
    adapter: SourceAdapter,
    client: StateWorkerClient,
    last_run: datetime | None,
    now: datetime,
) -> None:
    """Fetch one calendar day, post it, stamp the end of that day, repeat.

    A failed day raises before its stamp. Days already stamped stay put.
    The cursor is never moved to ``now``.
    """
    days = arxiv_days_to_scrape(
        last_run,
        now,
        window_days=resolve_backfill_window_days(adapter.source.value),
    )
    if not days:
        logger.info(
            "arxiv day walk caught up",
            extra={"event": "arxiv_day_walk_caught_up", "source": adapter.source.value},
        )
        return
    for index, day_start in enumerate(days):
        if index > 0 and ARXIV_INTER_PAGE_DELAY_SEC > 0:
            await asyncio.sleep(ARXIV_INTER_PAGE_DELAY_SEC)
        day_end = _utc_day_end(day_start)
        entries = await failure_envelope(
            adapter.fetch_manifest,
            since=day_start,
            until=day_end,
            source=adapter.source,
        )
        if not entries:
            logger.info(
                "arxiv day empty",
                extra={
                    "event": "arxiv_day_empty",
                    "source": adapter.source.value,
                    "day": day_start.date().isoformat(),
                },
            )
        result = await _post_manifest_chunks(client, entries)
        await client.post_scraper_state(adapter.source, timestamp=day_end)
        logger.info(
            "arxiv day complete",
            extra={
                "event": "arxiv_day_complete",
                "source": adapter.source.value,
                "day": day_start.date().isoformat(),
                "inserted": result.inserted,
                "skipped": result.skipped,
            },
        )


async def _post_manifest_chunks(
    client: StateWorkerClient,
    entries: list[ManifestIngestEntry],
) -> ManifestBatchResult:
    """POST manifest rows in bounded chunks. Empty input still posts once."""
    if len(entries) <= MANIFEST_POST_CHUNK:
        return await client.post_manifest_batch(entries)
    inserted = 0
    skipped = 0
    for offset in range(0, len(entries), MANIFEST_POST_CHUNK):
        result = await client.post_manifest_batch(
            entries[offset : offset + MANIFEST_POST_CHUNK],
        )
        inserted += result.inserted
        skipped += result.skipped
    return ManifestBatchResult(inserted=inserted, skipped=skipped)


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
    window_days = resolve_backfill_window_days(source.value)
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
            result = await _post_manifest_chunks(client, entries)
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
        elif getattr(adapter, "walks_calendar_days", False):
            await _scrape_arxiv_days(adapter, client, last_run, now)
            return
        else:
            since = last_run
            if last_run is None and BISHOP_BACKFILL_WINDOW_OVERRIDE_DAYS is not None:
                since = now - timedelta(days=BISHOP_BACKFILL_WINDOW_OVERRIDE_DAYS)
            entries = await failure_envelope(
                adapter.fetch_manifest,
                since=since,
                source=source,
            )
            if not entries:
                logger.warning("empty manifest fetch", extra={"source": source.value})
            result = await _post_manifest_chunks(client, entries)
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
    except (httpx.TimeoutException, httpx.TransportError) as exc:
        logger.error(
            "state-worker request timed out",
            extra={
                "source": source.value,
                "error": type(exc).__name__,
                "event": "state_worker_error",
            },
        )
