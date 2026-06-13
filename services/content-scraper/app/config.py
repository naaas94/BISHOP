"""Content-scraper configuration — env-backed constants for M4 slice."""

from __future__ import annotations

import os

STATE_WORKER_BASE_URL = os.environ.get("STATE_WORKER_URL", "http://state-worker:8000")


def _int_from_env(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return int(raw)


CONTENT_SCRAPE_BATCH_SIZE = _int_from_env("BISHOP_CONTENT_SCRAPE_BATCH_SIZE", 10)
CONTENT_SCRAPE_POLL_INTERVAL_SEC = _int_from_env("BISHOP_CONTENT_SCRAPE_POLL_INTERVAL_SEC", 120)

LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
