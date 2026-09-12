"""Stage 2 cycle: poll ENRICHMENT_STAGE2_QUEUED → hash verify → Call 2 submit → POST /batches."""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from pathlib import Path

import httpx

from app.anthropic_batch_client import AnthropicBatchClient, submit_stage2_batch_or_fatal
from app.config import ENRICHMENT_STAGE2_MAX_HOLD_MINUTES, ENRICHMENT_STAGE2_MIN_BATCH_SIZE
from app.models import (
    ENRICHMENT_STAGE2_BATCH_TYPE,
    BatchRegisterRequest,
    Stage2BatchEntry,
)
from app.stage1_loop import ensure_g3_verified
from app.state_worker_client import StateWorkerClient
from bishop_shared.enums import DomainEnum
from bishop_shared.profile_renderer import (
    compute_profile_hash,
    load_profile,
    render_profile_prompt,
    resolve_profile_path,
)
from bishop_shared.rubric_assets import compute_rubric_hash, load_rubric, resolve_rubric_path

logger = logging.getLogger(__name__)

# Minimum-volume hold state (row 18/19), stage 2 gate — independent of stage 1's
# clock (separate module, gathered concurrently by app.main). In-process only —
# resets on service restart; accepted tradeoff (no BatchRecord schema change, D8).
_pending_entries: list[object] = []
_hold_started_at: float | None = None


def _now() -> float:
    """Monotonic clock, indirected for test time-injection."""
    return time.monotonic()


def _verify_profile_hash(profile_path: Path) -> tuple[str, str, str] | None:
    """Return (profile_version, render_hash, profile_prompt) or None on mismatch.

    ``include_output=False``: Call 2's cached prefix must not carry the
    gate-1-specific ``{"decision": 0 or 1}`` output instruction (§5.4 C4) —
    the real relevance schema is supplied by ``build_call2_system_prompt``.
    """
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
        return None
    return profile.version, computed, render_profile_prompt(profile, include_output=False)


def _verify_rubric_hash(rubric_path: Path) -> str | None:
    """Return rubric body on hash match, or None on mismatch.

    Log-only on mismatch — no CRITICAL alert. §2 row 12 asymmetry: only
    pre-filter emits the CRITICAL alert path; stage 1 and stage 2 log only,
    matching the M5 T4 deferral. Changing that asymmetry is out of scope.
    Mirrors stage1_loop._verify_rubric_hash.
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


async def stage2_cycle(
    state_client: StateWorkerClient | None = None,
    anthropic_client: AnthropicBatchClient | None = None,
    *,
    profile_path: Path | None = None,
    rubric_path: Path | None = None,
) -> None:
    """Run one Call 2 cycle: poll stage2 queued, verify hash, submit, register."""
    owns_state = state_client is None
    if state_client is None:
        state_client = StateWorkerClient()

    try:
        logger.info("stage2 cycle started", extra={"event": "stage2_cycle_start"})
        try:
            poll = await state_client.poll_stage2_queued_entries()
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
                    "unsupported domain for M5 enrichment stage2",
                    extra={"domain": domain.value, "event": "unsupported_domain"},
                )
                return
            if _hold_started_at is None:
                _hold_started_at = _now()
            _pending_entries.extend(poll.entries)

        if not _pending_entries:
            logger.info(
                "empty stage2 poll",
                extra={"claimed_count": poll.claimed_count, "event": "empty_poll"},
            )
            return

        held_count = len(_pending_entries)
        hold_elapsed_sec = _now() - _hold_started_at if _hold_started_at is not None else 0.0
        deadline_reached = hold_elapsed_sec >= (ENRICHMENT_STAGE2_MAX_HOLD_MINUTES * 60)
        if held_count < ENRICHMENT_STAGE2_MIN_BATCH_SIZE and not deadline_reached:
            logger.info(
                "batch held below minimum volume",
                extra={
                    "held_count": held_count,
                    "min_batch_size": ENRICHMENT_STAGE2_MIN_BATCH_SIZE,
                    "event": "batch_held",
                },
            )
            return

        domain = _pending_entries[0].domain

        path = profile_path or resolve_profile_path(domain, gate="enrichment")
        verified = _verify_profile_hash(path)
        if verified is None:
            # Hash abort: retain pending entries and hold_started_at unchanged so a
            # persistent mismatch cannot extend the hold deadline indefinitely (C9).
            return

        profile_version, profile_render_hash, profile_prompt = verified

        resolved_rubric_path = rubric_path or resolve_rubric_path("call2_rubric")
        rubric_body = _verify_rubric_hash(resolved_rubric_path)
        if rubric_body is None:
            # Hash abort: retain pending entries and hold_started_at unchanged so a
            # persistent mismatch cannot extend the hold deadline indefinitely (C9).
            return

        if not ensure_g3_verified():
            return

        entries_to_submit = list(_pending_entries)
        batch_entries: list[Stage2BatchEntry] = []
        for entry in entries_to_submit:
            if not entry.summary:
                logger.error(
                    "stage2 entry missing summary",
                    extra={"source_id": entry.source_id, "event": "missing_summary"},
                )
                return
            batch_entries.append(
                Stage2BatchEntry(
                    source_id=entry.source_id,
                    title=entry.title,
                    summary=entry.summary,
                )
            )

        if anthropic_client is None:
            anthropic_client = AnthropicBatchClient()

        submit_result = await asyncio.to_thread(
            submit_stage2_batch_or_fatal,
            anthropic_client,
            profile_prompt=profile_prompt,
            rubric_body=rubric_body,
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
            batch_type=ENRICHMENT_STAGE2_BATCH_TYPE,
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
        logger.info("stage2 cycle complete", extra={"event": "stage2_cycle_complete"})
    finally:
        if owns_state:
            await state_client.aclose()
