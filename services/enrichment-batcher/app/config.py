"""Enrichment-batcher configuration — env-backed constants for M5 slice."""

from __future__ import annotations

import os

STATE_WORKER_BASE_URL = os.environ.get("STATE_WORKER_URL", "http://state-worker:8000")


def _int_from_env(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return int(raw)


ENRICHMENT_STAGE1_BATCH_SIZE = _int_from_env("BISHOP_ENRICHMENT_STAGE1_BATCH_SIZE", 10)
ENRICHMENT_POLL_INTERVAL_SEC = _int_from_env("BISHOP_ENRICHMENT_POLL_INTERVAL_SEC", 120)

# Dev-only bypass for G3 gate when live probe is impractical (e.g. local mocks).
G3_DEV_BYPASS = os.environ.get("BISHOP_G3_VERIFIED") == "1"

LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
