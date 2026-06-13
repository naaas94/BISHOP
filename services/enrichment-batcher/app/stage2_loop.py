"""Stage 2 cycle: poll ENRICHMENT_STAGE2_QUEUED → hash verify → Call 2 submit → POST /batches."""

from __future__ import annotations

import asyncio
import logging
import uuid
from pathlib import Path

import httpx

from app.anthropic_batch_client import AnthropicBatchClient, submit_stage2_batch_or_fatal
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

logger = logging.getLogger(__name__)


def _verify_profile_hash(profile_path: Path) -> tuple[str, str, str] | None:
    """Return (profile_version, render_hash, profile_prompt) or None on mismatch."""
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
    return profile.version, computed, render_profile_prompt(profile)


async def stage2_cycle(
    state_client: StateWorkerClient | None = None,
    anthropic_client: AnthropicBatchClient | None = None,
    *,
    profile_path: Path | None = None,
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

        if not poll.entries:
            logger.info(
                "empty stage2 poll",
                extra={"claimed_count": poll.claimed_count, "event": "empty_poll"},
            )
            return

        domain = poll.entries[0].domain
        if domain != DomainEnum.PROFESSIONAL:
            logger.error(
                "unsupported domain for M5 enrichment stage2",
                extra={"domain": domain.value, "event": "unsupported_domain"},
            )
            return

        path = profile_path or resolve_profile_path(domain)
        verified = _verify_profile_hash(path)
        if verified is None:
            return

        profile_version, profile_render_hash, profile_prompt = verified

        if not ensure_g3_verified():
            return

        batch_entries: list[Stage2BatchEntry] = []
        for entry in poll.entries:
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
            entries=batch_entries,
        )

        if submit_result is None:
            return

        batch_id = str(uuid.uuid4())
        register_body = BatchRegisterRequest(
            batch_id=batch_id,
            batch_type=ENRICHMENT_STAGE2_BATCH_TYPE,
            domain=domain,
            profile_version=profile_version,
            profile_render_hash=profile_render_hash,
            source_ids=[entry.source_id for entry in poll.entries],
            external_batch_id=submit_result.external_batch_id,
            entry_count=len(poll.entries),
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
                "entry_count": len(poll.entries),
                "event": "batch_registered",
            },
        )
        logger.info("stage2 cycle complete", extra={"event": "stage2_cycle_complete"})
    finally:
        if owns_state:
            await state_client.aclose()
