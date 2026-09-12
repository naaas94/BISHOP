"""Pre-filter cycle: poll → hash verify → Anthropic submit → POST /batches."""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from pathlib import Path

import httpx

from app.alerts import emit_profile_hash_mismatch_alert
from app.anthropic_batch_client import AnthropicBatchClient, submit_pre_filter_batch_or_fatal
from app.config import G3_DEV_BYPASS, PREFILTER_MAX_HOLD_MINUTES, PREFILTER_MIN_BATCH_SIZE
from app.models import BatchRegisterRequest, PreFilterBatchEntry
from app.state_worker_client import StateWorkerClient
from bishop_shared.anthropic_config import get_anthropic_api_key, verify_model_string
from bishop_shared.enums import DomainEnum
from bishop_shared.profile_renderer import (
    compute_profile_hash,
    load_profile,
    render_profile_prompt,
    resolve_profile_path,
)

logger = logging.getLogger(__name__)

_g3_verified = False

# Minimum-volume hold state (row 18/19): entries claimed from state-worker but not
# yet large enough to submit are held in-process across cycles. In-process only —
# resets on service restart; this is an accepted tradeoff (no BatchRecord schema
# change, D8). Per-gate, independent of stage1/stage2 (separate modules).
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


def _verify_profile_hash(profile_path: Path) -> tuple[str, str, str] | None:
    """Return (profile_version, render_hash, system_prompt) or None on mismatch."""
    profile = load_profile(profile_path)
    computed = compute_profile_hash(profile_path)
    if computed != profile.canonical_hash:
        logger.error(
            "profile canonical_hash mismatch at batch time",
            extra={
                "event": "profile_hash_mismatch",
                "expected_hash": profile.canonical_hash,
                "computed_hash": computed,
            },
        )
        emit_profile_hash_mismatch_alert(
            expected_hash=profile.canonical_hash,
            computed_hash=computed,
        )
        return None
    return profile.version, computed, render_profile_prompt(profile)


async def prefilter_cycle(
    state_client: StateWorkerClient | None = None,
    anthropic_client: AnthropicBatchClient | None = None,
    *,
    profile_path: Path | None = None,
) -> None:
    """Run one pre-filter cycle: poll, verify hash, submit Anthropic batch, register."""
    owns_state = state_client is None
    if state_client is None:
        state_client = StateWorkerClient()

    try:
        logger.info("prefilter cycle started", extra={"event": "prefilter_cycle_start"})
        try:
            poll = await state_client.poll_discovered_manifest()
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
                    "unsupported domain for M3 pre-filter",
                    extra={"domain": domain.value, "event": "unsupported_domain"},
                )
                return
            if _hold_started_at is None:
                _hold_started_at = _now()
            _pending_entries.extend(poll.entries)

        if not _pending_entries:
            logger.info(
                "empty manifest poll",
                extra={"claimed_count": poll.claimed_count, "event": "empty_poll"},
            )
            return

        held_count = len(_pending_entries)
        hold_elapsed_sec = _now() - _hold_started_at if _hold_started_at is not None else 0.0
        deadline_reached = hold_elapsed_sec >= (PREFILTER_MAX_HOLD_MINUTES * 60)
        if held_count < PREFILTER_MIN_BATCH_SIZE and not deadline_reached:
            logger.info(
                "batch held below minimum volume",
                extra={
                    "held_count": held_count,
                    "min_batch_size": PREFILTER_MIN_BATCH_SIZE,
                    "event": "batch_held",
                },
            )
            return

        domain = _pending_entries[0].domain

        resolved_path = profile_path or resolve_profile_path(domain, gate="prefilter")
        verified = _verify_profile_hash(resolved_path)
        if verified is None:
            # Hash abort: retain pending entries and hold_started_at unchanged so a
            # persistent mismatch cannot extend the hold deadline indefinitely (C9).
            return

        profile_version, profile_render_hash, system_prompt = verified

        if not ensure_g3_verified():
            return

        entries_to_submit = list(_pending_entries)
        batch_entries = [
            PreFilterBatchEntry(
                source_id=entry.source_id,
                title=entry.title,
                abstract=entry.abstract,
            )
            for entry in entries_to_submit
        ]

        if anthropic_client is None:
            anthropic_client = AnthropicBatchClient()

        submit_result = await asyncio.to_thread(
            submit_pre_filter_batch_or_fatal,
            anthropic_client,
            system_prompt=system_prompt,
            entries=batch_entries,
        )

        # Submission was attempted (accepted or fatally rejected by Anthropic) — the
        # held entries are consumed either way and the hold clock resets for the next
        # accumulation window.
        _pending_entries.clear()
        _hold_started_at = None

        if submit_result is None:
            return

        batch_id = str(uuid.uuid4())
        register_body = BatchRegisterRequest(
            batch_id=batch_id,
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
                "state-worker batch registration failed",
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
                "passed": 0,
                "rejected": 0,
                "event": "batch_registered",
            },
        )
        logger.info("prefilter cycle complete", extra={"event": "prefilter_cycle_complete"})
    finally:
        if owns_state:
            await state_client.aclose()
