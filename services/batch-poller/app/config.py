"""Batch-poller configuration — env-backed constants for M3 pre-filter slice."""

from __future__ import annotations

import os

STATE_WORKER_BASE_URL = os.environ.get("STATE_WORKER_URL", "http://state-worker:8000")


def _int_from_env(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return int(raw)


BATCH_POLL_INTERVAL_SEC = _int_from_env("BISHOP_BATCH_POLL_INTERVAL_SEC", 120)
BATCH_TIMEOUT_HOURS = _int_from_env("BISHOP_BATCH_TIMEOUT_HOURS", 48)
