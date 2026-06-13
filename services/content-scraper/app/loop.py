"""Content scrape cycle: poll → fetch_content → POST content or failed."""

from __future__ import annotations

import logging

import httpx

from app.adapter_resolver import resolve_adapter
from app.failure_mapping import map_adapter_exception_to_failed
from app.models import ContentPostRequest, ManifestPollEntry
from app.state_worker_client import StateWorkerClient
from scraper_app.failure_envelope import failure_envelope
from scraper_app.models import ManifestIngestEntry

logger = logging.getLogger(__name__)


def _poll_entry_to_ingest(entry: ManifestPollEntry) -> ManifestIngestEntry:
    return ManifestIngestEntry(
        source_id=entry.source_id,
        source=entry.source,
        url=entry.url,
        title=entry.title,
        abstract=entry.abstract,
        published_at=entry.published_at,
        domain=entry.domain,
    )


async def content_scrape_cycle(state_client: StateWorkerClient | None = None) -> None:
    """Run one content scrape cycle for claimed RELEVANCE_PASSED manifest rows."""
    owns_client = state_client is None
    if state_client is None:
        state_client = StateWorkerClient()

    try:
        logger.info("content scrape cycle started", extra={"event": "content_scrape_cycle_start"})
        try:
            poll = await state_client.poll_relevance_passed()
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
                "empty manifest poll",
                extra={"claimed_count": poll.claimed_count, "event": "empty_poll"},
            )
            return

        for entry in poll.entries:
            await _process_entry(entry, state_client)

        logger.info("content scrape cycle complete", extra={"event": "content_scrape_cycle_complete"})
    finally:
        if owns_client:
            await state_client.aclose()


async def _process_entry(entry: ManifestPollEntry, state_client: StateWorkerClient) -> None:
    adapter = resolve_adapter(entry.source)
    if adapter is None:
        return

    ingest_entry = _poll_entry_to_ingest(entry)
    try:
        content_raw = await failure_envelope(
            adapter.fetch_content,
            ingest_entry,
            source=entry.source,
        )
    except Exception as exc:
        failed_body = map_adapter_exception_to_failed(entry.source_id, exc)
        try:
            await state_client.post_failed(failed_body)
        except httpx.HTTPStatusError as post_exc:
            logger.error(
                "state-worker failed POST error",
                extra={
                    "source_id": entry.source_id,
                    "source": entry.source.value,
                    "http_status": post_exc.response.status_code,
                    "event": "state_worker_error",
                },
            )
            return
        logger.error(
            "content scrape failed",
            extra={
                "source_id": entry.source_id,
                "source": entry.source.value,
                "error_class": failed_body.error_class,
                "event": "content_scrape_failed",
            },
        )
        return

    logger.info(
        "content fetched",
        extra={
            "source_id": entry.source_id,
            "source": entry.source.value,
            "event": "content_fetched",
        },
    )

    try:
        result = await state_client.post_content(
            ContentPostRequest(source_id=entry.source_id, content_raw=content_raw),
        )
    except httpx.HTTPStatusError as exc:
        logger.error(
            "state-worker content POST error",
            extra={
                "source_id": entry.source_id,
                "source": entry.source.value,
                "http_status": exc.response.status_code,
                "event": "state_worker_error",
            },
        )
        return

    logger.info(
        "content posted",
        extra={
            "source_id": entry.source_id,
            "source": entry.source.value,
            "entry_id": result.entry_id,
            "processing_state": result.processing_state,
            "event": "content_posted",
        },
    )
