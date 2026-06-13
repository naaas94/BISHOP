"""Stage 1 cycle: poll SCRAPED → truncate → Anthropic submit → POST /batches."""

from __future__ import annotations

import asyncio
import logging
import uuid
from pathlib import Path

import httpx

from app.anthropic_batch_client import AnthropicBatchClient, submit_stage1_batch_or_fatal
from app.config import G3_DEV_BYPASS
from app.models import BatchRegisterRequest, ENRICHMENT_STAGE1_BATCH_TYPE, Stage1BatchEntry
from app.state_worker_client import StateWorkerClient
from bishop_shared.anthropic_config import get_anthropic_api_key, verify_model_string
from bishop_shared.content_truncation import truncate_content_for_call1
from bishop_shared.enums import DomainEnum
from bishop_shared.profile_renderer import load_profile, resolve_profile_path

logger = logging.getLogger(__name__)

_g3_verified = False


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
    path = profile_path or resolve_profile_path(domain)
    profile = load_profile(path)
    return profile.canonical_hash


async def stage1_cycle(
    state_client: StateWorkerClient | None = None,
    anthropic_client: AnthropicBatchClient | None = None,
    *,
    profile_path: Path | None = None,
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

        if not poll.entries:
            logger.info(
                "empty scraped poll",
                extra={"claimed_count": poll.claimed_count, "event": "empty_poll"},
            )
            return

        domain = poll.entries[0].domain
        if domain != DomainEnum.PROFESSIONAL:
            logger.error(
                "unsupported domain for M5 enrichment stage1",
                extra={"domain": domain.value, "event": "unsupported_domain"},
            )
            return

        if not ensure_g3_verified():
            return

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
            for entry in poll.entries
        ]

        if anthropic_client is None:
            anthropic_client = AnthropicBatchClient()

        submit_result = await asyncio.to_thread(
            submit_stage1_batch_or_fatal,
            anthropic_client,
            entries=batch_entries,
        )

        if submit_result is None:
            return

        profile_version = poll.entries[0].profile_version
        profile_render_hash = _profile_render_hash(domain, profile_path=profile_path)
        batch_id = str(uuid.uuid4())
        register_body = BatchRegisterRequest(
            batch_id=batch_id,
            batch_type=ENRICHMENT_STAGE1_BATCH_TYPE,
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
        logger.info("stage1 cycle complete", extra={"event": "stage1_cycle_complete"})
    finally:
        if owns_state:
            await state_client.aclose()
