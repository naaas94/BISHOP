"""Shared Anthropic prompt-cache system-block construction.

Single emitter for the ``cache_control`` literal (§2 row 9). All three
Anthropic batch gates (pre-filter, enrichment Call 1, enrichment Call 2)
build their ``params["system"]`` block list through :func:`cached_system_blocks`
so that exactly one breakpoint, on the last block, with the frozen TTL, is
the only way a request can be marked cacheable.

Also carries :func:`send_cache_warmup_ping` (FU-CACHE-WARMUP-01) — a
best-effort synchronous cache-priming call issued right before a real batch
submit, so the first cohort after a cold start does not race Anthropic's
concurrent, out-of-order batch scheduler for the cache write.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from anthropic import Anthropic

logger = logging.getLogger(__name__)

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


def send_cache_warmup_ping(
    client: Anthropic,
    *,
    model: str,
    system_blocks: list[dict[str, object]],
) -> bool:
    """Best-effort synchronous cache-priming call (FU-CACHE-WARMUP-01).

    Anthropic's Batch API has no partial/streaming completion signal —
    results are only retrievable once the whole batch has ended — so a
    batch-based warmup (peel one real entry into its own tiny batch, poll it
    to completion, then submit the rest) would either submit that one
    manifest row through two separate Anthropic batches (double-processing,
    duplicate ``BatchRecord`` provenance) or block on an unbounded batch
    turnaround with no SLA. Priming via the synchronous Messages API instead
    writes the same cache entry (Anthropic scopes the cache by organization,
    model, and byte-identical prefix — not by which endpoint wrote it) in one
    blocking round-trip, before the real batch submit call, and never touches
    ``batches``/``BatchRecord`` bookkeeping or a real manifest row.

    Best-effort only: every failure (network, auth, rate limit, model
    rejection) is caught and logged — callers must submit the real batch
    regardless of this function's return value. Returns ``True`` if the call
    completed without raising, ``False`` otherwise. This call is itself the
    cache *write*; whether the following batch actually reads from it is not
    knowable here — that is the batch-poller's ``cache_read_tokens`` signal
    on the batch this warmup precedes, not this function's own ``usage``.
    """
    try:
        response = client.messages.create(
            model=model,
            max_tokens=1,
            system=system_blocks,
            messages=[{"role": "user", "content": "."}],
        )
    except Exception as exc:  # noqa: BLE001 - best-effort; must never block a real submit
        logger.warning(
            "cache warmup ping failed",
            extra={"event": "cache_warmup_failed", "detail": str(exc)},
        )
        return False

    usage = getattr(response, "usage", None)
    logger.info(
        "cache warmup ping sent",
        extra={
            "event": "cache_warmup_sent",
            "cache_creation_input_tokens": getattr(usage, "cache_creation_input_tokens", None),
            "cache_read_input_tokens": getattr(usage, "cache_read_input_tokens", None),
        },
    )
    return True
