"""Map canonical BISHOP source_id values to Anthropic Batch API custom_id strings."""

from __future__ import annotations

import base64
import hashlib
import re

# Anthropic Messages Batch API — requests[].custom_id
_BATCH_CUSTOM_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")
# base64url without padding fits in 64 chars when source_id is at most 48 UTF-8 bytes.
_MAX_SOURCE_ID_BYTES = 48
# sha256 digest is 32 bytes → 43 chars base64url without padding.
_HASHED_CUSTOM_ID_PREFIX = "h"


def _b64url_nopad(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def source_id_to_batch_custom_id(source_id: str) -> str:
    """Encode a canonical ``source:raw_id`` into a Batch API-safe custom_id.

    Short IDs use URL-safe base64 without padding (bijective). IDs over 48
    UTF-8 bytes (HuggingFace ``org/repo`` paths, long GitHub names) use a
    deterministic SHA-256 digest so they still fit Anthropic's 64-char cap.
    The poll path looks up results by encoding ``batch.source_ids`` again,
    so the hash does not need to be reversible.
    """
    raw = source_id.encode("utf-8")
    if len(raw) <= _MAX_SOURCE_ID_BYTES:
        encoded = _b64url_nopad(raw)
    else:
        encoded = _HASHED_CUSTOM_ID_PREFIX + _b64url_nopad(hashlib.sha256(raw).digest())
    if len(encoded) > 64 or not _BATCH_CUSTOM_ID_PATTERN.fullmatch(encoded):
        msg = f"source_id encodes to invalid batch custom_id: {source_id!r}"
        raise ValueError(msg)
    return encoded


def batch_custom_id_to_source_id(custom_id: str) -> str:
    """Decode a Batch API custom_id back to canonical source_id.

    Hashed custom_ids (long source_ids) are not reversible; production poll
    never decodes — it re-encodes ``batch.source_ids``.
    """
    if not _BATCH_CUSTOM_ID_PATTERN.fullmatch(custom_id):
        msg = f"invalid batch custom_id: {custom_id!r}"
        raise ValueError(msg)
    # Hashed ids are ``h`` + 43-char sha256 digest. ASCII source_ids never
    # base64url-encode to a string starting with ``h``.
    if custom_id.startswith(_HASHED_CUSTOM_ID_PREFIX) and len(custom_id) == 44:
        msg = f"hashed custom_id is not reversible: {custom_id!r}"
        raise ValueError(msg)
    padding = "=" * (-len(custom_id) % 4)
    return base64.urlsafe_b64decode((custom_id + padding).encode("ascii")).decode("utf-8")
