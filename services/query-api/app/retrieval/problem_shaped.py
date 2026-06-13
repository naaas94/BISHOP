"""Problem-shaped query detection per spec §16.3 (M7 T4)."""

from __future__ import annotations

_PREFIX_PATTERNS: tuple[str, ...] = (
    "how to",
    "how do i",
    "how do you",
    "how can i",
    "what approaches",
    "best way to",
    "strategies for",
    "when to",
    "why does",
    "when does",
)

_CONTENT_SIGNALS: tuple[str, ...] = (
    "challenge",
    "problem",
    "issue",
    "error",
    "fail",
    "failure",
    "retry",
    "recover",
    "handle",
    "bottleneck",
    "tradeoff",
    "vs",
    "versus",
    "alternative",
)


def is_problem_shaped(query: str) -> bool:
    """Return True when §16.3 prefix or content heuristics match."""
    normalized = query.strip().lower()
    if not normalized:
        return False

    for prefix in _PREFIX_PATTERNS:
        if normalized.startswith(prefix):
            return True

    return any(signal in normalized for signal in _CONTENT_SIGNALS)
