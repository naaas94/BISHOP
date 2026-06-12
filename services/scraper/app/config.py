"""Scraper configuration — env-backed constants for M2 discovery slice."""

from __future__ import annotations

import os

STATE_WORKER_BASE_URL = os.environ.get("STATE_WORKER_URL", "http://state-worker:8000")

ARXIV_CATEGORIES: tuple[str, ...] = ("cs.AI", "cs.CL", "cs.LG")


def _int_from_env(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return int(raw)


ARXIV_BACKFILL_WINDOW_DAYS = _int_from_env("BISHOP_ARXIV_BACKFILL_WINDOW_DAYS", 7)
SCRAPER_SCHEDULE_INTERVAL_SEC = _int_from_env("BISHOP_SCRAPER_SCHEDULE_INTERVAL_SEC", 21600)
