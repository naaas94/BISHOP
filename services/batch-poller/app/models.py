"""Wire and domain models for batch-poller HTTP clients."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


PRE_FILTER_BATCH_TYPE = "pre_filter"
ENRICHMENT_STAGE1_BATCH_TYPE = "enrichment_stage1"
ENRICHMENT_STAGE2_BATCH_TYPE = "enrichment_stage2"
TRACKED_BATCH_TYPES = frozenset(
    {
        PRE_FILTER_BATCH_TYPE,
        ENRICHMENT_STAGE1_BATCH_TYPE,
        ENRICHMENT_STAGE2_BATCH_TYPE,
    },
)


class BatchRecordWire(BaseModel):
    batch_id: str
    batch_type: str
    domain: str
    profile_version: str
    profile_render_hash: str
    status: str
    created_at: datetime
    submitted_at: datetime | None = None
    completed_at: datetime | None = None
    entry_count: int
    passed_count: int = 0
    failed_count: int = 0
    source_ids: list[str] = Field(default_factory=list)
    external_batch_id: str | None = None


class BatchesListResponse(BaseModel):
    batches: list[BatchRecordWire]


class PreFilterResultEntryWire(BaseModel):
    source_id: str
    decision: int
    pre_filter_rationale: str


class PreFilterResultsRequest(BaseModel):
    batch_id: str
    profile_version: str
    entries: list[PreFilterResultEntryWire]


class PreFilterResultsResponse(BaseModel):
    updated: int
    passed: int
    rejected: int


class BatchPatchRequest(BaseModel):
    status: str
    passed_count: int | None = None
    failed_count: int | None = None
    completed_at: datetime | None = None


class BatchTimeoutResponse(BaseModel):
    batch_id: str
    status: str
    entries_reset: int


class AnthropicBatchResultItem(BaseModel):
    custom_id: str
    text: str | None = None
    errored: bool = False


class ParsedPreFilterDecision(BaseModel):
    source_id: str
    decision: int
    pre_filter_rationale: str
    parse_failed: bool = False


class EnrichmentStage1ResultEntryWire(BaseModel):
    source_id: str
    success: bool
    summary: str | None = None
    concepts: list[str] | None = None
    tags: list[str] | None = None
    entry_type: str | None = None
    challenge_hooks: list[str] | None = None
    oov_tags_stripped: list[str] | None = None
    error_message: str | None = None


class EnrichmentStage1ResultsRequest(BaseModel):
    batch_id: str
    entries: list[EnrichmentStage1ResultEntryWire]


class EnrichmentStage2ResultEntryWire(BaseModel):
    source_id: str
    success: bool
    relevance_score: float | None = None
    relevance_reason: str | None = None
    value_rationale: str | None = None
    error_message: str | None = None


class EnrichmentStage2ResultsRequest(BaseModel):
    batch_id: str
    entries: list[EnrichmentStage2ResultEntryWire]
