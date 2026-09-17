"""Aggregate stats route — read-only SQLite (M7)."""

from __future__ import annotations

from fastapi import APIRouter

from app.models import StatsOverview
from app.stats_reader import read_stats_overview

router = APIRouter(tags=["stats"])


@router.get("/stats/overview", response_model=StatsOverview)
def get_stats_overview() -> StatsOverview:
    return read_stats_overview()
