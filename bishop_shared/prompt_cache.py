"""Shared Anthropic prompt-cache system-block construction.

Single emitter for the ``cache_control`` literal (§2 row 9). All three
Anthropic batch gates (pre-filter, enrichment Call 1, enrichment Call 2)
build their ``params["system"]`` block list through :func:`cached_system_blocks`
so that exactly one breakpoint, on the last block, with the frozen TTL, is
the only way a request can be marked cacheable.
"""

from __future__ import annotations

from typing import Final

# Claude Haiku 4.5's minimum cacheable prefix. Plan target with a 10% margin
# over this floor lives in the per-gate token-floor test, not here — this
# constant is the SDK/API floor itself, not the plan's padded target.
HAIKU_CACHE_MIN_TOKENS: Final[int] = 4096

# GA cache_control ttl. "1h" over the default "5m" so a batch that takes
# longer than 5 minutes to accumulate still hits a warm cache on write.
CACHE_TTL: Final[str] = "1h"


def cached_system_blocks(*texts: str) -> list[dict[str, object]]:
    """Build an Anthropic ``system`` content-block list with one breakpoint.

    Each ``text`` becomes one ``{"type": "text", "text": text}`` block, in
    the order given. ``cache_control`` is attached to the **last** block
    only. Every call returns a fresh tree of dicts — no block, and no
    ``cache_control`` dict, is ever shared or mutated in place across calls,
    so concurrent requests built from the same texts cannot alias.

    Raises:
        ValueError: if called with no text blocks.
    """
    if not texts:
        msg = "cached_system_blocks requires at least one system text block"
        raise ValueError(msg)

    blocks: list[dict[str, object]] = [{"type": "text", "text": text} for text in texts]
    blocks[-1]["cache_control"] = {"type": "ephemeral", "ttl": CACHE_TTL}
    return blocks
