"""Wire and domain models for batch-poller HTTP clients."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


PRE_FILTER_BATCH_TYPE = "pre_filter"


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
