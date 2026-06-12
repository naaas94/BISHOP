"""Scheduled scrape cycle per §10.3."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

import httpx

from app.adapters.base import SourceAdapter
from app.adapters.registry import ADAPTER_REGISTRY
from app.exceptions import EscalatableError, PermanentFailureError, RetryExhaustedError
from app.failure_envelope import failure_envelope, log_permanent_failure
from app.state_worker_client import StateWorkerClient

logger = logging.getLogger(__name__)


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
        await client.post_scraper_state(source, timestamp=datetime.now(UTC))
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
