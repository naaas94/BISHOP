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


def _optional_int_from_env(name: str) -> int | None:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return None
    return int(raw)


# AD HOC overlay (2026-09-11), not intended. When set, replaces
# BACKFILL_CONFIG.window_days for every source and, on cold start with backfill
# disabled, supplies since=now-N instead of None so adapters do not fall back
# to their 30–90 day first-run windows. Unset restores intended
# BACKFILL_CONFIG / adapter defaults. See
# .dev/decision-logs/ops/soft-launch-precision-overlay.md.
BISHOP_BACKFILL_WINDOW_OVERRIDE_DAYS = _optional_int_from_env(
    "BISHOP_BACKFILL_WINDOW_OVERRIDE_DAYS"
)


GITHUB_TOKEN = _optional_str_from_env("GITHUB_TOKEN")
SEMANTIC_SCHOLAR_API_KEY = _optional_str_from_env("SEMANTIC_SCHOLAR_API_KEY")
HUGGINGFACE_TOKEN = _optional_str_from_env("HUGGINGFACE_TOKEN")

# Harvest pool (sidecar). Incremental GitHub still POSTs DISCOVERED.
BISHOP_HARVEST_ENABLED = _bool_from_env("BISHOP_HARVEST_ENABLED", True)
BISHOP_HARVEST_WINDOW_DAYS = _int_from_env("BISHOP_HARVEST_WINDOW_DAYS", 730)
BISHOP_HARVEST_SLICE_BUDGET_SEC = _int_from_env("BISHOP_HARVEST_SLICE_BUDGET_SEC", 90)
BISHOP_HARVEST_RELEASE_INTERVAL_SEC = _int_from_env(
    "BISHOP_HARVEST_RELEASE_INTERVAL_SEC", 60
)
BISHOP_HARVEST_RELEASE_BATCH = _int_from_env("BISHOP_HARVEST_RELEASE_BATCH", 50)
BISHOP_HARVEST_QUERY_ID = (
    _optional_str_from_env("BISHOP_HARVEST_QUERY_ID") or "github-pushed-stars10-v1"
)
