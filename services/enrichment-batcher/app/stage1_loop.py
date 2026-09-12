"""Stage 1 cycle: poll SCRAPED → truncate → Anthropic submit → POST /batches."""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from pathlib import Path

import httpx

from app.anthropic_batch_client import AnthropicBatchClient, submit_stage1_batch_or_fatal
from app.config import (
    ENRICHMENT_STAGE1_MAX_HOLD_MINUTES,
    ENRICHMENT_STAGE1_MIN_BATCH_SIZE,
    G3_DEV_BYPASS,
)
from app.models import BatchRegisterRequest, ENRICHMENT_STAGE1_BATCH_TYPE, Stage1BatchEntry
from app.state_worker_client import StateWorkerClient
from bishop_shared.anthropic_config import get_anthropic_api_key, verify_model_string
from bishop_shared.content_truncation import truncate_content_for_call1
from bishop_shared.enums import DomainEnum
from bishop_shared.profile_renderer import load_profile, resolve_profile_path
from bishop_shared.rubric_assets import compute_rubric_hash, load_rubric, resolve_rubric_path

logger = logging.getLogger(__name__)

_g3_verified = False

# Minimum-volume hold state (row 18/19), stage 1 gate — independent of stage 2's
# clock (separate module, gathered concurrently by app.main). In-process only —
# resets on service restart; accepted tradeoff (no BatchRecord schema change, D8).
_pending_entries: list[object] = []
_hold_started_at: float | None = None


def _now() -> float:
    """Monotonic clock, indirected for test time-injection."""
    return time.monotonic()


def reset_g3_gate_for_tests() -> None:
    """Test helper — reset module-level G3 latch."""
    global _g3_verified
    _g3_verified = False


def ensure_g3_verified() -> bool:
    """Verify G3 model string once before the first live Anthropic call."""
    global _g3_verified
    if _g3_verified:
        return True
    if G3_DEV_BYPASS:
        logger.info("G3 dev bypass via BISHOP_G3_VERIFIED=1")
        _g3_verified = True
        return True

    api_key = get_anthropic_api_key()
    if not api_key:
        logger.error(
            "G3 verification blocked: ANTHROPIC_API_KEY not set",
            extra={"event": "model_string_fatal"},
        )
        return False

    try:
        if not verify_model_string(api_key=api_key):
            logger.error(
                "G3 model string verification failed",
                extra={"event": "model_string_fatal"},
            )
            return False
    except Exception as exc:
        logger.error(
            "G3 model string verification error",
            extra={"event": "model_string_fatal", "detail": str(exc)},
        )
        return False

    _g3_verified = True
    logger.info("G3 model string verified")
    return True


def _profile_render_hash(
    domain: DomainEnum,
    *,
    profile_path: Path | None = None,
) -> str:
    path = profile_path or resolve_profile_path(domain, gate="enrichment")
    profile = load_profile(path)
    return profile.canonical_hash


def _verify_rubric_hash(rubric_path: Path) -> str | None:
    """Return rubric body on hash match, or None on mismatch.

    Log-only on mismatch — no CRITICAL alert. §2 row 12 asymmetry: only
    pre-filter emits the CRITICAL alert path; stage 1 and stage 2 log only,
    matching the M5 T4 deferral. Changing that asymmetry is out of scope.
    """
    doc = load_rubric(rubric_path)
    computed = compute_rubric_hash(rubric_path)
    if computed != doc.canonical_hash:
        logger.error(
            "rubric canonical_hash mismatch at batch time",
            extra={
                "event": "rubric_hash_mismatch",
                "rubric_id": doc.rubric_id,
                "expected_hash": doc.canonical_hash,
                "computed_hash": computed,
            },
        )
        return None
    return doc.body


async def stage1_cycle(
    state_client: StateWorkerClient | None = None,
    anthropic_client: AnthropicBatchClient | None = None,
    *,
    profile_path: Path | None = None,
    rubric_path: Path | None = None,
) -> None:
    """Run one Call 1 cycle: poll SCRAPED, truncate, submit Anthropic batch, register."""
    owns_state = state_client is None
    if state_client is None:
        state_client = StateWorkerClient()

    try:
        logger.info("stage1 cycle started", extra={"event": "stage1_cycle_start"})
        try:
            poll = await state_client.poll_scraped_entries()
        except httpx.HTTPStatusError as exc:
            logger.error(
                "state-worker poll failed",
                extra={"http_status": exc.response.status_code, "event": "state_worker_error"},
            )
            return

        global _hold_started_at

        if poll.entries:
            domain = poll.entries[0].domain
            if domain != DomainEnum.PROFESSIONAL:
                logger.error(
                    "unsupported domain for M5 enrichment stage1",
                    extra={"domain": domain.value, "event": "unsupported_domain"},
                )
                return
            if _hold_started_at is None:
                _hold_started_at = _now()
            _pending_entries.extend(poll.entries)

        if not _pending_entries:
            logger.info(
                "empty scraped poll",
                extra={"claimed_count": poll.claimed_count, "event": "empty_poll"},
            )
            return

        held_count = len(_pending_entries)
        hold_elapsed_sec = _now() - _hold_started_at if _hold_started_at is not None else 0.0
        deadline_reached = hold_elapsed_sec >= (ENRICHMENT_STAGE1_MAX_HOLD_MINUTES * 60)
        if held_count < ENRICHMENT_STAGE1_MIN_BATCH_SIZE and not deadline_reached:
            logger.info(
                "batch held below minimum volume",
                extra={
                    "held_count": held_count,
                    "min_batch_size": ENRICHMENT_STAGE1_MIN_BATCH_SIZE,
                    "event": "batch_held",
                },
            )
            return

        domain = _pending_entries[0].domain

        resolved_rubric_path = rubric_path or resolve_rubric_path("call1_rubric")
        if _verify_rubric_hash(resolved_rubric_path) is None:
            # Hash abort: retain pending entries and hold_started_at unchanged so a
            # persistent mismatch cannot extend the hold deadline indefinitely (C9).
            return

        if not ensure_g3_verified():
            # G3 abort: retain pending entries and hold_started_at unchanged so a
            # persistent block cannot extend the hold deadline indefinitely (C9).
            return

        entries_to_submit = list(_pending_entries)
        batch_entries = [
            Stage1BatchEntry(
                source_id=entry.source_id,
                source=entry.source,
                title=entry.title,
                truncated_content=truncate_content_for_call1(
                    entry.source.value,
                    entry.title,
                    entry.content_raw,
                ),
            )
            for entry in entries_to_submit
        ]

        if anthropic_client is None:
            anthropic_client = AnthropicBatchClient()

        submit_result = await asyncio.to_thread(
            submit_stage1_batch_or_fatal,
            anthropic_client,
            entries=batch_entries,
        )

        # Submission was attempted (accepted or fatally rejected by Anthropic) — the
        # held entries are consumed either way and the hold clock resets for the next
        # accumulation window.
        _pending_entries.clear()
        _hold_started_at = None

        if submit_result is None:
            return

        profile_version = entries_to_submit[0].profile_version
        profile_render_hash = _profile_render_hash(domain, profile_path=profile_path)
        batch_id = str(uuid.uuid4())
        register_body = BatchRegisterRequest(
            batch_id=batch_id,
            batch_type=ENRICHMENT_STAGE1_BATCH_TYPE,
            domain=domain,
            profile_version=profile_version,
            profile_render_hash=profile_render_hash,
            source_ids=[entry.source_id for entry in entries_to_submit],
            external_batch_id=submit_result.external_batch_id,
            entry_count=len(entries_to_submit),
        )

        try:
            registered = await state_client.register_batch(register_body)
        except httpx.HTTPStatusError as exc:
            logger.error(
                "state-worker batch registration failed after anthropic submit",
                extra={
                    "http_status": exc.response.status_code,
                    "batch_id": batch_id,
                    "external_batch_id": submit_result.external_batch_id,
                    "event": "state_worker_error",
                },
            )
            return

        logger.info(
            "batch registered",
            extra={
                "batch_id": registered.batch_id,
                "external_batch_id": submit_result.external_batch_id,
                "entry_count": len(entries_to_submit),
                "event": "batch_registered",
            },
        )
        logger.info("stage1 cycle complete", extra={"event": "stage1_cycle_complete"})
    finally:
        if owns_state:
            await state_client.aclose()
