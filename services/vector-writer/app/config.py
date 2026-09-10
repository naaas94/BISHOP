"""Vector-writer configuration — env-backed constants for M6 slice."""

from __future__ import annotations

import os
from pathlib import Path

from bishop_shared.index_policy import INDEX_POLICY_CONTAINER_PATH

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

# Gate 2 policy YAML; absent file falls back to permissive defaults (no behavior change).
INDEX_POLICY_PATH = Path(
    os.environ.get("BISHOP_INDEX_POLICY_PATH", str(INDEX_POLICY_CONTAINER_PATH))
)
