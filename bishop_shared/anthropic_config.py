"""Frozen Anthropic model constants and G3 model-string verification gate."""

from __future__ import annotations

import os

# Spec §12.1 / charter G3 — pinned dated snapshot; do not use undated aliases.
ANTHROPIC_MODEL_PREFILTER = "claude-haiku-4-5-20251001"
ANTHROPIC_MODEL_ENRICHMENT = "claude-haiku-4-5-20251001"

_G3_PROBE_MESSAGE = "ping"


def get_anthropic_api_key() -> str | None:
    """Return ANTHROPIC_API_KEY from the environment; no default."""
    return os.environ.get("ANTHROPIC_API_KEY")


def verify_model_string(*, api_key: str | None = None) -> bool:
    """Verify ANTHROPIC_MODEL_PREFILTER via one Anthropic Messages API call.

    Returns True when Anthropic accepts the model (non-400 response).
    Returns False on HTTP 400 (invalid model string).
    Raises on other API or network errors.
    """
    key = api_key if api_key is not None else get_anthropic_api_key()
    if not key:
        raise ValueError("ANTHROPIC_API_KEY is required for live model verification")

    from anthropic import Anthropic, BadRequestError

    client = Anthropic(api_key=key)
    try:
        client.messages.create(
            model=ANTHROPIC_MODEL_PREFILTER,
            max_tokens=1,
            messages=[{"role": "user", "content": _G3_PROBE_MESSAGE}],
        )
    except BadRequestError:
        return False
    return True
