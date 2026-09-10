"""Unit tests for bishop_shared.scraper_config (M8 T1-bis: §18.2 + Appendix B)."""

from __future__ import annotations

from bishop_shared.enums import SourceEnum
from bishop_shared.scraper_config import (
    BACKFILL_CONFIG,
    SOURCE_SCHEDULE_INTERVAL_SEC,
    BackfillConfig,
)

_ALL_SOURCE_VALUES = {member.value for member in SourceEnum}


def test_backfill_config_round_trip() -> None:
    config = BackfillConfig(window_days=30, categories=("cs.AI",))
    assert config.window_days == 30
    assert config.categories == ("cs.AI",)


def test_backfill_config_round_trip_default_categories() -> None:
    config = BackfillConfig(window_days=30)
    assert config.categories == ()


def test_backfill_config_matches_spec_defaults() -> None:
    """§18.2 per-source window_days, all seven source keys present."""
    assert set(BACKFILL_CONFIG) == _ALL_SOURCE_VALUES

    assert BACKFILL_CONFIG["arxiv"] == BackfillConfig(
        window_days=60,
        categories=("cs.AI", "cs.CL", "cs.LG"),
    )
    assert BACKFILL_CONFIG["github"].window_days == 30
    assert BACKFILL_CONFIG["semantic_scholar"].window_days == 60
    assert BACKFILL_CONFIG["huggingface"].window_days == 30
    assert BACKFILL_CONFIG["paperswithcode"].window_days == 60
    assert BACKFILL_CONFIG["openreview"].window_days == 90
    assert BACKFILL_CONFIG["lesswrong"].window_days == 30


def test_schedule_defaults() -> None:
    """Appendix B default scraper schedules, converted to seconds."""
    assert set(SOURCE_SCHEDULE_INTERVAL_SEC) == _ALL_SOURCE_VALUES

    assert SOURCE_SCHEDULE_INTERVAL_SEC["arxiv"] == 6 * 3600
    assert SOURCE_SCHEDULE_INTERVAL_SEC["github"] == 12 * 3600
    assert SOURCE_SCHEDULE_INTERVAL_SEC["semantic_scholar"] == 24 * 3600
    assert SOURCE_SCHEDULE_INTERVAL_SEC["huggingface"] == 6 * 3600
    assert SOURCE_SCHEDULE_INTERVAL_SEC["paperswithcode"] == 24 * 3600
    assert SOURCE_SCHEDULE_INTERVAL_SEC["openreview"] == 24 * 3600
    assert SOURCE_SCHEDULE_INTERVAL_SEC["lesswrong"] == 24 * 3600
