"""Shared per-source backfill window and schedule-interval config (§18.2, Appendix B).

Distinct from ``bishop_shared.source_config`` (the ArXiv category *gate* — a
zero-cost structural filter on primary category, landed and frozen for M8)
and from ``services/scraper/app/config.py`` (the env-backed
``ARXIV_BACKFILL_WINDOW_DAYS`` / ``SCRAPER_SCHEDULE_INTERVAL_SEC`` incremental
knobs). This module carries two things:

* ``BACKFILL_CONFIG`` — the spec §18.2 per-source backfill-window datum.
  ``BACKFILL_CONFIG["arxiv"].window_days == 60`` is the backfill-only value;
  it does **not** change the incremental ``resolve_effective_since(since=None)``
  default, which stays 7 days (``ARXIV_BACKFILL_WINDOW_DAYS``) until T8 wires
  backfill behind ``BISHOP_BACKFILL_ENABLED``.
* ``SOURCE_SCHEDULE_INTERVAL_SEC`` — the Appendix B per-source default poll
  cadence, in seconds, for all seven registered sources.

Landing this module does not change any incremental scraper behavior; it is
config-only until a later subtask (T8) reads it.
"""

from __future__ import annotations

from dataclasses import dataclass

import os

from bishop_shared.enums import SourceEnum


@dataclass(frozen=True)
class BackfillConfig:
    """Spec §18.2 per-source backfill window."""

    window_days: int
    categories: tuple[str, ...] = ()


BACKFILL_CONFIG: dict[str, BackfillConfig] = {
    SourceEnum.ARXIV.value: BackfillConfig(
        window_days=60,
        categories=("cs.AI", "cs.CL", "cs.LG"),
    ),
    SourceEnum.GITHUB.value: BackfillConfig(window_days=30),
    SourceEnum.SEMANTIC_SCHOLAR.value: BackfillConfig(window_days=60),
    SourceEnum.HUGGINGFACE.value: BackfillConfig(window_days=30),
    SourceEnum.PAPERSWITHCODE.value: BackfillConfig(window_days=60),
    SourceEnum.OPENREVIEW.value: BackfillConfig(window_days=90),
    SourceEnum.LESSWRONG.value: BackfillConfig(window_days=30),
}

# Appendix B "Default scraper schedules (G3)" — seconds.
SOURCE_SCHEDULE_INTERVAL_SEC: dict[str, int] = {
    SourceEnum.ARXIV.value: 6 * 3600,
    SourceEnum.GITHUB.value: 12 * 3600,
    SourceEnum.SEMANTIC_SCHOLAR.value: 24 * 3600,
    SourceEnum.HUGGINGFACE.value: 6 * 3600,
    SourceEnum.PAPERSWITHCODE.value: 24 * 3600,
    SourceEnum.OPENREVIEW.value: 24 * 3600,
    SourceEnum.LESSWRONG.value: 24 * 3600,
}

# Operator scrape page — registry order, Papers with Code is dead.
SCRAPE_SOURCE_ORDER: tuple[str, ...] = (
    SourceEnum.ARXIV.value,
    SourceEnum.GITHUB.value,
    SourceEnum.HUGGINGFACE.value,
    SourceEnum.LESSWRONG.value,
    SourceEnum.OPENREVIEW.value,
    SourceEnum.PAPERSWITHCODE.value,
    SourceEnum.SEMANTIC_SCHOLAR.value,
)
DEAD_SCRAPE_SOURCES: frozenset[str] = frozenset({SourceEnum.PAPERSWITHCODE.value})
_DEFAULT_SCHEDULE_INTERVAL_SEC = 21600


def schedule_interval_sec() -> int:
    """Live scrape tick. Env ``BISHOP_SCRAPER_SCHEDULE_INTERVAL_SEC``, default 6h."""
    raw = os.environ.get("BISHOP_SCRAPER_SCHEDULE_INTERVAL_SEC")
    if raw is None or raw == "":
        return _DEFAULT_SCHEDULE_INTERVAL_SEC
    return int(raw)


def overlay_window_days() -> int | None:
    """Soft-launch overlay. ``None`` means the per-source BACKFILL_CONFIG pin."""
    raw = os.environ.get("BISHOP_BACKFILL_WINDOW_OVERRIDE_DAYS")
    if raw is None or raw == "":
        return None
    return int(raw)


def backfill_enabled() -> bool:
    raw = os.environ.get("BISHOP_BACKFILL_ENABLED", "0").strip().lower()
    return raw in ("1", "true", "yes")
