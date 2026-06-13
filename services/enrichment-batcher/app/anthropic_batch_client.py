"""Anthropic Messages Batch API client for enrichment Call 1 submissions."""

from __future__ import annotations

import logging
from typing import Any

from anthropic import Anthropic, BadRequestError

from app.models import AnthropicBatchSubmitResult, Stage1BatchEntry, Stage2BatchEntry
from bishop_shared.anthropic_config import ANTHROPIC_MODEL_ENRICHMENT, get_anthropic_api_key
from bishop_shared.enrichment_prompts import (
    build_call1_system_prompt,
    build_call1_user_message,
    build_call2_system_prompt,
    build_call2_user_message,
)

logger = logging.getLogger(__name__)

# Call 1 JSON output: summary, concepts, tags, entry_type, challenge_hooks.
_CALL1_MAX_TOKENS = 1024
# Call 2 JSON output: relevance_score, relevance_reason, value_rationale.
_CALL2_MAX_TOKENS = 512


class AnthropicBatchClient:
    """Submit enrichment stage1 batch requests with custom_id = source_id."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        client: Anthropic | None = None,
    ) -> None:
        key = api_key if api_key is not None else get_anthropic_api_key()
        if client is None and not key:
            msg = "ANTHROPIC_API_KEY is required for Anthropic batch submission"
            raise ValueError(msg)
        self._client = client or Anthropic(api_key=key)

    def build_requests(
        self,
        *,
        entries: list[Stage1BatchEntry],
    ) -> list[dict[str, Any]]:
        """Build wire payload; exposed for contract tests asserting custom_id."""
        system_prompt = build_call1_system_prompt()
        requests: list[dict[str, Any]] = []
        for entry in entries:
            requests.append(
                {
                    "custom_id": entry.source_id,
                    "params": {
                        "model": ANTHROPIC_MODEL_ENRICHMENT,
                        "max_tokens": _CALL1_MAX_TOKENS,
                        "system": system_prompt,
                        "messages": [
                            {
                                "role": "user",
                                "content": build_call1_user_message(
                                    entry.title,
                                    entry.truncated_content,
                                ),
                            },
                        ],
                    },
                }
            )
        return requests

    def submit_stage1_batch(
        self,
        *,
        entries: list[Stage1BatchEntry],
    ) -> AnthropicBatchSubmitResult:
        """Submit batch to Anthropic; raises BadRequestError on HTTP 400."""
        requests = self.build_requests(entries=entries)
        batch = self._client.messages.batches.create(requests=requests)
        return AnthropicBatchSubmitResult(
            external_batch_id=batch.id,
            request_payload=requests,
        )

    def build_stage2_requests(
        self,
        *,
        profile_prompt: str,
        entries: list[Stage2BatchEntry],
    ) -> list[dict[str, Any]]:
        """Build Call 2 wire payload with cache_control system blocks."""
        system_blocks = build_call2_system_prompt(profile_prompt)
        requests: list[dict[str, Any]] = []
        for entry in entries:
            requests.append(
                {
                    "custom_id": entry.source_id,
                    "params": {
                        "model": ANTHROPIC_MODEL_ENRICHMENT,
                        "max_tokens": _CALL2_MAX_TOKENS,
                        "system": system_blocks,
                        "messages": [
                            {
                                "role": "user",
                                "content": build_call2_user_message(
                                    entry.title,
                                    entry.summary,
                                ),
                            },
                        ],
                    },
                }
            )
        return requests

    def submit_stage2_batch(
        self,
        *,
        profile_prompt: str,
        entries: list[Stage2BatchEntry],
    ) -> AnthropicBatchSubmitResult:
        """Submit Call 2 batch to Anthropic; raises BadRequestError on HTTP 400."""
        requests = self.build_stage2_requests(profile_prompt=profile_prompt, entries=entries)
        batch = self._client.messages.batches.create(requests=requests)
        return AnthropicBatchSubmitResult(
            external_batch_id=batch.id,
            request_payload=requests,
        )


def submit_stage1_batch_or_fatal(
    client: AnthropicBatchClient,
    *,
    entries: list[Stage1BatchEntry],
) -> AnthropicBatchSubmitResult | None:
    """Submit batch; log model_string_fatal and return None on HTTP 400."""
    try:
        return client.submit_stage1_batch(entries=entries)
    except BadRequestError as exc:
        logger.error(
            "anthropic batch submit rejected model string",
            extra={"event": "model_string_fatal", "detail": str(exc)},
        )
        return None


def submit_stage2_batch_or_fatal(
    client: AnthropicBatchClient,
    *,
    profile_prompt: str,
    entries: list[Stage2BatchEntry],
) -> AnthropicBatchSubmitResult | None:
    """Submit Call 2 batch; log model_string_fatal and return None on HTTP 400."""
    try:
        return client.submit_stage2_batch(profile_prompt=profile_prompt, entries=entries)
    except BadRequestError as exc:
        logger.error(
            "anthropic batch submit rejected model string",
            extra={"event": "model_string_fatal", "detail": str(exc)},
        )
        return None
