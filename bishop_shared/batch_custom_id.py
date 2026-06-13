"""Map canonical BISHOP source_id values to Anthropic Batch API custom_id strings."""

from __future__ import annotations

import base64
import re

# Anthropic Messages Batch API — requests[].custom_id
_BATCH_CUSTOM_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")
# base64url without padding fits in 64 chars when source_id is at most 48 UTF-8 bytes.
_MAX_SOURCE_ID_BYTES = 48


def source_id_to_batch_custom_id(source_id: str) -> str:
    """Encode a canonical ``source:raw_id`` into a Batch API-safe custom_id.

    Uses URL-safe base64 without padding so the mapping is bijective and
    survives arbitrary punctuation in raw_id (arxiv dots, github slashes, etc.).
    """
    encoded = (
        base64.urlsafe_b64encode(source_id.encode("utf-8")).decode("ascii").rstrip("=")
    )
    if len(source_id.encode("utf-8")) > _MAX_SOURCE_ID_BYTES:
        msg = f"source_id exceeds {_MAX_SOURCE_ID_BYTES} UTF-8 bytes: {source_id!r}"
        raise ValueError(msg)
    if len(encoded) > 64 or not _BATCH_CUSTOM_ID_PATTERN.fullmatch(encoded):
        msg = f"source_id encodes to invalid batch custom_id: {source_id!r}"
        raise ValueError(msg)
    return encoded


def batch_custom_id_to_source_id(custom_id: str) -> str:
    """Decode a Batch API custom_id back to canonical source_id."""
    if not _BATCH_CUSTOM_ID_PATTERN.fullmatch(custom_id):
        msg = f"invalid batch custom_id: {custom_id!r}"
        raise ValueError(msg)
    padding = "=" * (-len(custom_id) % 4)
    return base64.urlsafe_b64decode((custom_id + padding).encode("ascii")).decode("utf-8")
