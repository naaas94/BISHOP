"""Poll loop — Anthropic batch polling, results POST, timeout enforcement."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import UTC, datetime, timedelta
from typing import Callable

import httpx

from app.clients.anthropic import (
    AnthropicBatchOutcome,
    AnthropicBatchPollerProtocol,
    AnthropicBatchStatus,
)
from app.clients.state_worker import StateWorkerClient, iso_timestamp
from app.config import BATCH_POLL_INTERVAL_SEC, BATCH_TIMEOUT_HOURS
from app.models import (
    PRE_FILTER_BATCH_TYPE,
    BatchPatchRequest,
    BatchRecordWire,
    ParsedPreFilterDecision,
    PreFilterResultEntryWire,
    PreFilterResultsRequest,
)
from app.startup import startup_scan

logger = logging.getLogger(__name__)

AioSleep = Callable[[float], asyncio.Future[None]]

_JSON_OBJECT_RE = re.compile(r"\{[^{}]*\}", re.DOTALL)


def _merge_tracked(
    tracked: dict[str, BatchRecordWire],
    batches: list[BatchRecordWire],
) -> None:
    for batch in batches:
        if batch.batch_type != PRE_FILTER_BATCH_TYPE:
            logger.warning(
                "batch_type rejected",
                extra={
                    "batch_id": batch.batch_id,
                    "batch_type": batch.batch_type,
                    "event": "enrichment_batch_rejected",
                },
            )
            continue
        if batch.status in {"complete", "failed", "batch_timed_out"}:
            tracked.pop(batch.batch_id, None)
            continue
        tracked[batch.batch_id] = batch


def _batch_timed_out(batch: BatchRecordWire, *, now: datetime) -> bool:
    if batch.submitted_at is None:
        return False
    submitted = batch.submitted_at
    if submitted.tzinfo is None:
        submitted = submitted.replace(tzinfo=UTC)
    compare_now = now if now.tzinfo is not None else now.replace(tzinfo=UTC)
    return compare_now >= submitted + timedelta(hours=BATCH_TIMEOUT_HOURS)


def parse_pre_filter_response(source_id: str, text: str | None) -> ParsedPreFilterDecision:
    """Parse LLM JSON decision; malformed responses count as reject (decision 0)."""
    if not text:
        return ParsedPreFilterDecision(
            source_id=source_id,
            decision=0,
            pre_filter_rationale="empty model response",
            parse_failed=True,
        )
    candidate = text.strip()
    try:
        payload = json.loads(candidate)
    except json.JSONDecodeError:
        match = _JSON_OBJECT_RE.search(candidate)
        if match is None:
            return ParsedPreFilterDecision(
                source_id=source_id,
                decision=0,
                pre_filter_rationale="malformed JSON response",
                parse_failed=True,
            )
        try:
            payload = json.loads(match.group(0))
        except json.JSONDecodeError:
            return ParsedPreFilterDecision(
                source_id=source_id,
                decision=0,
                pre_filter_rationale="malformed JSON response",
                parse_failed=True,
            )
    if not isinstance(payload, dict):
        return ParsedPreFilterDecision(
            source_id=source_id,
            decision=0,
            pre_filter_rationale="malformed JSON response",
            parse_failed=True,
        )
    decision = payload.get("decision")
    rationale = payload.get("rationale")
    if decision not in (0, 1) or not isinstance(rationale, str) or not rationale.strip():
        return ParsedPreFilterDecision(
            source_id=source_id,
            decision=0,
            pre_filter_rationale="malformed JSON response",
            parse_failed=True,
        )
    return ParsedPreFilterDecision(
        source_id=source_id,
        decision=int(decision),
        pre_filter_rationale=rationale.strip(),
        parse_failed=False,
    )


async def _handle_timeout(
    state_client: StateWorkerClient,
    batch: BatchRecordWire,
    tracked: dict[str, BatchRecordWire],
) -> None:
    result = await state_client.post_batch_timeout(batch.batch_id)
    logger.error(
        "batch timed out",
        extra={
            "batch_id": batch.batch_id,
            "external_batch_id": batch.external_batch_id,
            "event": "batch_timeout",
            "entries_reset": result.entries_reset,
        },
    )
    tracked.pop(batch.batch_id, None)


async def _handle_anthropic_failed(
    state_client: StateWorkerClient,
    batch: BatchRecordWire,
    tracked: dict[str, BatchRecordWire],
) -> None:
    await state_client.patch_batch(
        batch.batch_id,
        BatchPatchRequest(status="failed"),
    )
    logger.error(
        "anthropic batch failed",
        extra={
            "batch_id": batch.batch_id,
            "external_batch_id": batch.external_batch_id,
            "event": "anthropic_batch_failed",
        },
    )
    tracked.pop(batch.batch_id, None)


async def _handle_batch_complete(
    state_client: StateWorkerClient,
    anthropic_client: AnthropicBatchPollerProtocol,
    batch: BatchRecordWire,
    tracked: dict[str, BatchRecordWire],
) -> None:
    if not batch.external_batch_id:
        logger.error(
            "missing external_batch_id",
            extra={"batch_id": batch.batch_id, "event": "missing_external_batch_id"},
        )
        return

    raw_results = await anthropic_client.fetch_batch_results(batch.external_batch_id)
    results_by_id = {item.custom_id: item for item in raw_results}
    entries: list[PreFilterResultEntryWire] = []
    passed_count = 0
    failed_count = 0

    for source_id in batch.source_ids:
        item = results_by_id.get(source_id)
        if item is None or item.errored:
            parsed = ParsedPreFilterDecision(
                source_id=source_id,
                decision=0,
                pre_filter_rationale="missing or errored anthropic result",
                parse_failed=True,
            )
        else:
            parsed = parse_pre_filter_response(source_id, item.text)

        if parsed.parse_failed or parsed.decision == 0:
            failed_count += 1
        else:
            passed_count += 1
        entries.append(
            PreFilterResultEntryWire(
                source_id=parsed.source_id,
                decision=parsed.decision,
                pre_filter_rationale=parsed.pre_filter_rationale,
            ),
        )

    request = PreFilterResultsRequest(
        batch_id=batch.batch_id,
        profile_version=batch.profile_version,
        entries=entries,
    )
    try:
        response = await state_client.post_pre_filter_results(request)
    except httpx.HTTPStatusError:
        logger.error(
            "pre-filter-results post failed",
            extra={
                "batch_id": batch.batch_id,
                "external_batch_id": batch.external_batch_id,
                "event": "pre_filter_results_failed",
            },
        )
        return

    completed_at = datetime.now(UTC)
    await state_client.patch_batch(
        batch.batch_id,
        BatchPatchRequest(
            status="complete",
            passed_count=passed_count,
            failed_count=failed_count,
            completed_at=completed_at,
        ),
    )
    logger.info(
        "batch complete",
        extra={
            "batch_id": batch.batch_id,
            "external_batch_id": batch.external_batch_id,
            "event": "batch_complete",
            "passed": response.passed,
            "rejected": response.rejected,
        },
    )
    tracked.pop(batch.batch_id, None)


async def poll_once(
    state_client: StateWorkerClient,
    anthropic_client: AnthropicBatchPollerProtocol,
    tracked: dict[str, BatchRecordWire],
    *,
    now: datetime | None = None,
) -> None:
    """Single poll cycle: refresh queue, enforce timeouts, poll Anthropic."""
    current = now or datetime.now(UTC)
    in_flight = await state_client.get_in_flight_batches()
    _merge_tracked(tracked, in_flight)

    for batch_id, batch in list(tracked.items()):
        if _batch_timed_out(batch, now=current):
            await _handle_timeout(state_client, batch, tracked)
            continue

        if not batch.external_batch_id:
            continue

        processing_status, terminal = await anthropic_client.retrieve_batch_status(
            batch.external_batch_id,
        )
        if processing_status != AnthropicBatchStatus.ENDED:
            if batch.status == "submitted":
                await state_client.patch_batch(
                    batch.batch_id,
                    BatchPatchRequest(status="processing"),
                )
                batch.status = "processing"
                tracked[batch_id] = batch
            continue

        if terminal in {
            AnthropicBatchOutcome.FAILED,
            AnthropicBatchOutcome.EXPIRED,
            AnthropicBatchOutcome.CANCELED,
        }:
            await _handle_anthropic_failed(state_client, batch, tracked)
            continue

        await _handle_batch_complete(state_client, anthropic_client, batch, tracked)


async def poll_loop(
    state_client: StateWorkerClient,
    anthropic_client: AnthropicBatchPollerProtocol,
    *,
    poll_interval_sec: float | None = None,
    sleep_fn: AioSleep | None = None,
) -> None:
    """Startup scan then infinite Anthropic poll loop."""
    tracked_list = await startup_scan(state_client)
    tracked = {batch.batch_id: batch for batch in tracked_list}
    interval = float(poll_interval_sec if poll_interval_sec is not None else BATCH_POLL_INTERVAL_SEC)
    sleep = sleep_fn or asyncio.sleep

    while True:
        logger.info("poll cycle start", extra={"event": "poll_cycle_start"})
        await poll_once(state_client, anthropic_client, tracked)
        logger.info("poll cycle end", extra={"event": "poll_cycle_end"})
        await sleep(interval)
