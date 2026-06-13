"""Pre-filter cycle: poll → hash verify → Anthropic submit → POST /batches."""

from __future__ import annotations

import asyncio
import logging
import uuid
from pathlib import Path

import httpx

from app.alerts import emit_profile_hash_mismatch_alert
from app.anthropic_batch_client import AnthropicBatchClient, submit_pre_filter_batch_or_fatal
from app.config import G3_DEV_BYPASS
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

        if not poll.entries:
            logger.info(
                "empty manifest poll",
                extra={"claimed_count": poll.claimed_count, "event": "empty_poll"},
            )
            return

        domain = poll.entries[0].domain
        if domain != DomainEnum.PROFESSIONAL:
            logger.error(
                "unsupported domain for M3 pre-filter",
                extra={"domain": domain.value, "event": "unsupported_domain"},
            )
            return

        resolved_path = profile_path or resolve_profile_path(domain)
        verified = _verify_profile_hash(resolved_path)
        if verified is None:
            return

        profile_version, profile_render_hash, system_prompt = verified

        if not ensure_g3_verified():
            return

        batch_entries = [
            PreFilterBatchEntry(
                source_id=entry.source_id,
                title=entry.title,
                abstract=entry.abstract,
            )
            for entry in poll.entries
        ]

        if anthropic_client is None:
            anthropic_client = AnthropicBatchClient()

        submit_result = await asyncio.to_thread(
            submit_pre_filter_batch_or_fatal,
            anthropic_client,
            system_prompt=system_prompt,
            entries=batch_entries,
        )

        if submit_result is None:
            return

        batch_id = str(uuid.uuid4())
        register_body = BatchRegisterRequest(
            batch_id=batch_id,
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
                "entry_count": len(poll.entries),
                "passed": 0,
                "rejected": 0,
                "event": "batch_registered",
            },
        )
        logger.info("prefilter cycle complete", extra={"event": "prefilter_cycle_complete"})
    finally:
        if owns_state:
            await state_client.aclose()
