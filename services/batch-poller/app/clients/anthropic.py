"""Anthropic Batch API client for polling pre-filter batch completion."""

from __future__ import annotations

import logging
from typing import Any, Protocol

from bishop_shared.anthropic_config import get_anthropic_api_key

from app.models import AnthropicBatchResultItem

logger = logging.getLogger(__name__)


class AnthropicBatchStatus:
    """Normalized Anthropic batch processing states."""

    IN_PROGRESS = "in_progress"
    ENDED = "ended"


class AnthropicBatchOutcome:
    """Normalized terminal outcomes when processing has ended."""

    SUCCEEDED = "succeeded"
    FAILED = "failed"
    EXPIRED = "expired"
    CANCELED = "canceled"


class AnthropicBatchPollerClient:
    """Poll Anthropic batches by external_batch_id."""

    def __init__(self, *, api_key: str | None = None, client: Any | None = None) -> None:
        self._api_key = api_key if api_key is not None else get_anthropic_api_key()
        self._client = client
        self._owns_client = client is None

    def _ensure_client(self) -> Any:
        if self._client is not None:
            return self._client
        if not self._api_key:
            raise ValueError("ANTHROPIC_API_KEY is required for Anthropic batch polling")
        from anthropic import Anthropic

        self._client = Anthropic(api_key=self._api_key)
        return self._client

    async def retrieve_batch_status(
        self,
        external_batch_id: str,
    ) -> tuple[str, str | None]:
        """Return (processing_status, terminal_outcome_or_none)."""
        client = self._ensure_client()
        batch = client.batches.retrieve(external_batch_id)
        processing_status = getattr(batch, "processing_status", None) or batch.get(
            "processing_status",
        )
        if processing_status != AnthropicBatchStatus.ENDED:
            return processing_status, None
        outcome = getattr(batch, "results_url", None)
        # SDK exposes request_counts / processing_status; ended batches have a result.
        _ = outcome
        terminal = _extract_terminal_outcome(batch)
        return AnthropicBatchStatus.ENDED, terminal

    async def fetch_batch_results(
        self,
        external_batch_id: str,
    ) -> list[AnthropicBatchResultItem]:
        client = self._ensure_client()
        items: list[AnthropicBatchResultItem] = []
        for entry in client.batches.results(external_batch_id):
            custom_id = getattr(entry, "custom_id", None) or entry.get("custom_id", "")
            result = getattr(entry, "result", None) or entry.get("result")
            if result is None:
                items.append(AnthropicBatchResultItem(custom_id=custom_id, errored=True))
                continue
            result_type = getattr(result, "type", None) or result.get("type")
            if result_type == "errored":
                items.append(AnthropicBatchResultItem(custom_id=custom_id, errored=True))
                continue
            message = getattr(result, "message", None) or result.get("message", {})
            text = _extract_message_text(message)
            items.append(
                AnthropicBatchResultItem(custom_id=custom_id, text=text, errored=False),
            )
        return items


def _extract_terminal_outcome(batch: Any) -> str:
    """Map Anthropic batch object to succeeded/failed/expired/canceled."""
    for attr in ("results", "result", "processing_status"):
        value = getattr(batch, attr, None)
        if value is not None:
            break
    request_counts = getattr(batch, "request_counts", None)
    if request_counts is not None:
        errored = getattr(request_counts, "errored", 0) or 0
        succeeded = getattr(request_counts, "succeeded", 0) or 0
        if errored and not succeeded:
            return AnthropicBatchOutcome.FAILED
    ended_reason = getattr(batch, "ended_reason", None) or getattr(batch, "cancel_reason", None)
    if ended_reason in {"max_tokens", "error", "failed"}:
        return AnthropicBatchOutcome.FAILED
    if ended_reason == "expired":
        return AnthropicBatchOutcome.EXPIRED
    if ended_reason == "canceled":
        return AnthropicBatchOutcome.CANCELED
    return AnthropicBatchOutcome.SUCCEEDED


def _extract_message_text(message: Any) -> str | None:
    if message is None:
        return None
    content = getattr(message, "content", None) or message.get("content")
    if not content:
        return None
    first = content[0]
    if isinstance(first, dict):
        return first.get("text")
    return getattr(first, "text", None)


class AnthropicBatchPollerProtocol(Protocol):
    async def retrieve_batch_status(
        self,
        external_batch_id: str,
    ) -> tuple[str, str | None]: ...

    async def fetch_batch_results(
        self,
        external_batch_id: str,
    ) -> list[AnthropicBatchResultItem]: ...
