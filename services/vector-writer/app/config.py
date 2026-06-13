"""Vector-writer configuration — env-backed constants for M6 slice."""

from __future__ import annotations

import os

STATE_WORKER_BASE_URL = os.environ.get("STATE_WORKER_URL", "http://state-worker:8000")

VECTOR_WRITE_POLL_STATE = "VECTOR_WRITE_QUEUED"


def _int_from_env(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return int(raw)


VECTOR_WRITE_BATCH_SIZE = _int_from_env("BISHOP_VECTOR_WRITE_BATCH_SIZE", 10)
VECTOR_WRITE_POLL_INTERVAL_SEC = _int_from_env("BISHOP_VECTOR_WRITE_POLL_INTERVAL_SEC", 120)

LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
