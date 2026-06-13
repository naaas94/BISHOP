"""Classify Anthropic Batch API submit failures for structured logging."""

from __future__ import annotations

from anthropic import BadRequestError


def anthropic_batch_400_event(exc: BadRequestError) -> str:
    """Return a structured log event name for an HTTP 400 batch submit error."""
    message = str(exc).lower()
    if "custom_id" in message:
        return "batch_custom_id_rejected"
    if "model" in message:
        return "model_string_fatal"
    return "batch_submit_rejected"
