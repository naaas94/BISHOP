"""HTTP request/response models for query-api (M7 T5)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    """Query parameters for GET /search (binding contract surface)."""

    q: str = Field(min_length=1)
    domain: str | None = None
    source: str | None = None
    tags: list[str] | None = None
    min_relevance: float | None = Field(default=None, ge=0.0, le=1.0)
    days: int | None = Field(default=None, ge=1)
    type: str | None = Field(default=None, alias="type")
    reading_status: str | None = None

    model_config = {"populate_by_name": True}


class SearchHit(BaseModel):
    source_id: str
    rrf_score: float
    title: str
    summary: str | None = None
    relevance_score: float | None = None
    entry_type: str | None = None
    tags: list[str] | None = None


class SearchResponse(BaseModel):
    query: str
    problem_shaped: bool
    channels_active: list[str]
    hits: list[SearchHit]
    total: int


class RecentHit(BaseModel):
    source_id: str
    source: str
    title: str
    ingested_at: str
    domain: str
    entry_type: str | None = None
    relevance_score: float | None = None
    summary: str | None = None


class RecentResponse(BaseModel):
    entries: list[RecentHit]
    total: int


class EntryResponse(BaseModel):
    """Full SQLite entry row including content_raw."""

    id: str
    source_id: str
    source: str
    url: str
    title: str
    content_raw: str
    published_at: datetime | None = None
    ingested_at: datetime
    domain: str
    profile_version: str
    pre_filter_batch_id: str
    pre_filter_rationale: str
    pre_filter_tier: str | None = None
    summary: str | None = None
    concepts: list[str] | None = None
    tags: list[str] | None = None
    entry_type: str | None = None
    challenge_hooks: list[str] | None = None
    enrichment_stage1_batch_id: str | None = None
    relevance_score: float | None = None
    relevance_reason: str | None = None
    value_rationale: str | None = None
    enrichment_stage2_batch_id: str | None = None
    references: list[str] | None = None
    cited_by: list[str] | None = None
    reading_status: str
    flagged_for_review: bool
    processing_state: str


class BatchEntrySummary(BaseModel):
    source_id: str
    title: str
    summary: str | None = None
    relevance_score: float | None = None
    entry_type: str | None = None
    tags: list[str] | None = None


class BatchDetailEnrichedResponse(BaseModel):
    batch: dict[str, Any]
    entries: list[BatchEntrySummary]


class UpstreamErrorResponse(BaseModel):
    error: str = "upstream_error"
    status: int


class StatBucket(BaseModel):
    label: str
    count: int


class DailyCount(BaseModel):
    date: str
    count: int
    by_source: list[StatBucket] = []


class ScrapeExceptionRow(BaseModel):
    source: str
    lag_hours: float | None = None
    discovered_today: int = 0
    in_queue: int = 0
    stale: bool = False


class StatsOverview(BaseModel):
    generated_at: datetime
    manifest_total: int
    entries_total: int
    indexed_total: int
    pre_filter_decided: int
    pre_filter_passed: int
    pre_filter_parked: int = 0
    pre_filter_proceeded: int = 0
    funnel: list[StatBucket]
    queue_depth: list[StatBucket]
    relevance_histogram: list[StatBucket]
    by_domain: list[StatBucket]
    by_source: list[StatBucket]
    by_entry_type: list[StatBucket]
    top_tags: list[StatBucket]
    reading_status: list[StatBucket]
    ingest_by_day: list[DailyCount]
    batches_total: int
    batches_by_status: list[StatBucket]
    batches_by_type: list[StatBucket]
    recent_errors: list[StatBucket]
    harvest_pool_size: int = 0
    harvest_unreleased: int = 0
    harvest_released_today: int = 0
    harvest_n_cap: int = 0
    harvest_budget_usd: float = 0.0
    harvest_projected_usd_today: float = 0.0
    harvest_sidecar_present: bool = False
    harvest_unreleased_liability_usd: float = 0.0
    harvest_tap_open: bool = False
    scrape_max_lag_hours: float = 0.0
    scrape_lag_source: str | None = None
    scrape_caught_up: bool = False
    scrape_exceptions: list[ScrapeExceptionRow] = []
    today_discovered: int = 0


class HarvestStats(BaseModel):
    """GitHub harvest liability, mill walk, and daily faucet. Modeled, not billed."""

    generated_at: datetime
    sidecar_present: bool = False
    pool_size: int = 0
    unreleased: int = 0
    unreleased_liability_usd: float = 0.0
    pool_modeled_usd: float = 0.0
    blended_github_usd: float = 0.0
    days_to_drain: int | None = None
    n_cap: int = 0
    budget_usd: float = 0.0
    paper_reserve_usd: float = 0.0
    github_budget_usd: float = 0.0
    released_today: int = 0
    github_in_queue: int = 0
    slots_remaining: int = 0
    tap_open: bool = False
    tap_killed: bool = False
    released_overshoot: bool = False
    released_fill_pct: float = 0.0
    modeled_usd_today: float = 0.0
    walk_direction: str | None = None
    floor_at: str | None = None
    harvest_until: str | None = None
    high_water: str | None = None
    cursor_updated_at: str | None = None
    unwalked_days: float = 0.0
    walked_recent_days: float = 0.0
    window_span_days: float = 0.0
    walked_pct: float = 0.0
    forecast_ready: bool = False
    forecast_complete_windows: int = 0
    forecast_incomplete_windows: int = 0
    forecast_median_rate: float = 0.0
    forecast_upper_rate: float = 0.0
    forecast_median_usd: float = 0.0
    forecast_upper_usd: float = 0.0


class ScrapeSourceRow(BaseModel):
    source: str
    last_successful_run_at: str | None = None
    updated_at: str | None = None
    lag_hours: float | None = None
    lag_fill_pct: float = 0.0
    pin_window_days: int = 0
    discovered_today: int = 0
    in_queue: int = 0
    dead: bool = False
    stale: bool = False
    note: str | None = None


class ScrapeStats(BaseModel):
    """Incremental scrape cursors, overlay window, and today's inserts."""

    generated_at: datetime
    schedule_interval_sec: int = 21600
    overlay_window_days: int | None = None
    backfill_enabled: bool = False
    max_lag_hours: float = 0.0
    lag_source: str | None = None
    caught_up: bool = False
    discovered_today: int = 0
    in_queue: int = 0
    github_released_today: int | None = None
    sources: list[ScrapeSourceRow] = []


class TodayStats(BaseModel):
    """UTC-day rollup. Cohort is discovered_at >= UTC midnight. No indexed_at."""

    generated_at: datetime
    utc_day: str = ""
    utc_midnight: str = ""
    discovered_today: int = 0
    discovered_by_source: list[StatBucket] = []
    in_queue_today: int = 0
    indexed_cohort_today: int = 0
    entries_ingested_today: int = 0
    batches_completed_today: int = 0
    batches_by_status: list[StatBucket] = []
    batches_by_type: list[StatBucket] = []
    errors_today: list[StatBucket] = []
    funnel: list[StatBucket] = []
    queue_depth: list[StatBucket] = []
    harvest_sidecar_present: bool = False
    harvest_released_today: int = 0
    harvest_modeled_usd_today: float = 0.0
    harvest_n_cap: int = 0
    harvest_tap_open: bool = False
    harvest_tap_killed: bool = False
    harvest_released_overshoot: bool = False
    harvest_released_fill_pct: float = 0.0
    scrape_caught_up: bool = False
    scrape_max_lag_hours: float = 0.0
    scrape_lag_source: str | None = None
    scrape_in_queue: int = 0
    scrape_exceptions: list[ScrapeExceptionRow] = []
    overlay_window_days: int | None = None
    schedule_interval_sec: int = 21600
