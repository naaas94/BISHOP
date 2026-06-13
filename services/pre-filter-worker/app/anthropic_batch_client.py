"""Anthropic Messages Batch API client for pre-filter submissions."""

from __future__ import annotations

import logging
from typing import Any

from anthropic import Anthropic, BadRequestError

from app.models import AnthropicBatchSubmitResult, PreFilterBatchEntry
from bishop_shared.anthropic_batch_errors import anthropic_batch_400_event
from bishop_shared.anthropic_config import ANTHROPIC_MODEL_PREFILTER, get_anthropic_api_key
from bishop_shared.batch_custom_id import source_id_to_batch_custom_id

logger = logging.getLogger(__name__)

# Conservative cap for JSON decision + rationale per profile output spec.
_PREFILTER_MAX_TOKENS = 256


class AnthropicBatchClient:
    """Submit pre-filter batch requests with encoded source_id custom_ids."""

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
        system_prompt: str,
        entries: list[PreFilterBatchEntry],
    ) -> list[dict[str, Any]]:
        """Build wire payload; exposed for contract tests asserting custom_id encoding."""
        requests: list[dict[str, Any]] = []
        for entry in entries:
            requests.append(
                {
                    "custom_id": source_id_to_batch_custom_id(entry.source_id),
                    "params": {
                        "model": ANTHROPIC_MODEL_PREFILTER,
                        "max_tokens": _PREFILTER_MAX_TOKENS,
                        "system": system_prompt,
                        "messages": [
                            {"role": "user", "content": entry.user_message()},
                        ],
                    },
                }
            )
        return requests

    def submit_pre_filter_batch(
        self,
        *,
        system_prompt: str,
        entries: list[PreFilterBatchEntry],
    ) -> AnthropicBatchSubmitResult:
        """Submit batch to Anthropic; raises BadRequestError on HTTP 400."""
        requests = self.build_requests(system_prompt=system_prompt, entries=entries)
        batch = self._client.messages.batches.create(requests=requests)
        return AnthropicBatchSubmitResult(
            external_batch_id=batch.id,
            request_payload=requests,
        )


class ModelStringFatalError(Exception):
    """Raised when Anthropic rejects the pinned model string (HTTP 400)."""


def submit_pre_filter_batch_or_fatal(
    client: AnthropicBatchClient,
    *,
    system_prompt: str,
    entries: list[PreFilterBatchEntry],
) -> AnthropicBatchSubmitResult | None:
    """Submit batch; log structured 400 event and return None on HTTP 400."""
    try:
        return client.submit_pre_filter_batch(system_prompt=system_prompt, entries=entries)
    except BadRequestError as exc:
        event = anthropic_batch_400_event(exc)
        logger.error(
            "anthropic batch submit rejected",
            extra={"event": event, "detail": str(exc)},
        )
        return None
