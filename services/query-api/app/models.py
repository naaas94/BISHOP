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


class StatsOverview(BaseModel):
    generated_at: datetime
    manifest_total: int
    entries_total: int
    indexed_total: int
    pre_filter_decided: int
    pre_filter_passed: int
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
