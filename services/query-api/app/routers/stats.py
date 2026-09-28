"""Aggregate stats route — read-only SQLite (M7)."""

from __future__ import annotations

from fastapi import APIRouter

from app.models import HarvestStats, ScrapeStats, StatsOverview, TodayStats
from app.stats_reader import (
    read_harvest_stats,
    read_scrape_stats,
    read_stats_overview,
    read_today_stats,
)

router = APIRouter(tags=["stats"])


@router.get("/stats/overview", response_model=StatsOverview)
def get_stats_overview() -> StatsOverview:
    return read_stats_overview()


@router.get("/stats/harvest", response_model=HarvestStats)
def get_stats_harvest() -> HarvestStats:
    return read_harvest_stats()


@router.get("/stats/scrape", response_model=ScrapeStats)
def get_stats_scrape() -> ScrapeStats:
    return read_scrape_stats()


@router.get("/stats/today", response_model=TodayStats)
def get_stats_today() -> TodayStats:
    return read_today_stats()
