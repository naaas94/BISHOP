"""Structured alert emission for pre-filter-worker (stdout CRITICAL; no SQLite)."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def emit_profile_hash_mismatch_alert(*, expected_hash: str, computed_hash: str) -> None:
    """Dual-signal alert: ERROR event in loop plus CRITICAL alert_type per §14.3 pattern."""
    logger.critical(
        "profile canonical_hash mismatch at batch time",
        extra={
            "alert_type": "profile_hash_mismatch",
            "event": "profile_hash_mismatch",
            "expected_hash": expected_hash,
            "computed_hash": computed_hash,
        },
    )
