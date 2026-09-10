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


def _bool_from_env(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


# §18.4 backfill chunking — off by default; T8-bis enables via compose once G4/G5/G6 gates pass.
BISHOP_BACKFILL_ENABLED = _bool_from_env("BISHOP_BACKFILL_ENABLED", False)
BISHOP_BACKFILL_CHUNK_DAYS = _int_from_env("BISHOP_BACKFILL_CHUNK_DAYS", 7)
BISHOP_BACKFILL_INTER_CHUNK_DELAY_SEC = _int_from_env("BISHOP_BACKFILL_INTER_CHUNK_DELAY_SEC", 300)


def _optional_str_from_env(name: str) -> str | None:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return None
    return raw


GITHUB_TOKEN = _optional_str_from_env("GITHUB_TOKEN")
SEMANTIC_SCHOLAR_API_KEY = _optional_str_from_env("SEMANTIC_SCHOLAR_API_KEY")
