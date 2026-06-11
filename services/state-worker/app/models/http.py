"""HTTP wire models for state-worker §9.1 REST API."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.enums import EntryTypeEnum, ProcessingState, SourceEnum
from app.models.domain import BatchRecord, Entry, ErrorLog, ManifestEntry


# --- Documented §9.1 request/response shapes ---


class ManifestBatchEntryWire(BaseModel):
    source_id: str
    source: SourceEnum
    url: str
    title: str
    abstract: str | None = None
    published_at: datetime | None = None
    domain: str


class ManifestBatchRequest(BaseModel):
    entries: list[ManifestBatchEntryWire]


class ManifestBatchResponse(BaseModel):
    inserted: int
    skipped: int


class ContentPostRequest(BaseModel):
    source_id: str
    content_raw: str


class ContentPostResponse(BaseModel):
    entry_id: str
    processing_state: ProcessingState


class EnrichmentStage1EntryWire(BaseModel):
    source_id: str
    success: bool
    summary: str | None = None
    concepts: list[str] | None = None
    tags: list[str] | None = None
    entry_type: EntryTypeEnum | None = None
    challenge_hooks: list[str] | None = None
    error_message: str | None = None


class EnrichmentStage1ResultsRequest(BaseModel):
    batch_id: str
    entries: list[EnrichmentStage1EntryWire]


class EnrichmentStage2EntryWire(BaseModel):
    source_id: str
    success: bool
    relevance_score: float | None = None
    relevance_reason: str | None = None
    value_rationale: str | None = None
    error_message: str | None = None


class EnrichmentStage2ResultsRequest(BaseModel):
    batch_id: str
    entries: list[EnrichmentStage2EntryWire]


class IndexedPostRequest(BaseModel):
    source_id: str


class FailedPostRequest(BaseModel):
    source_id: str
    state_at_failure: ProcessingState
    error_class: str
    http_status: int | None = None
    message: str
    is_retriable: bool


class PollResponse(BaseModel):
    entries: list[dict[str, Any]]
    claimed_count: int
    transitioned_to: str | None


class ScraperStateResponse(BaseModel):
    source: SourceEnum
    last_successful_run_at: datetime | None
    updated_at: datetime


class ScraperStateUpdateRequest(BaseModel):
    timestamp: datetime


# --- Derived wire models (undocumented §9.1 bodies — see T1 decision log) ---


class PreFilterResultEntryWire(BaseModel):
    """Derived from §5.2 steps 8–9: per-entry pre-filter decision payload."""

    source_id: str
    decision: int = Field(description="0 = reject, 1 = pass")
    pre_filter_rationale: str


class PreFilterResultsRequest(BaseModel):
    batch_id: str
    profile_version: str
    entries: list[PreFilterResultEntryWire]


class PreFilterResultsResponse(BaseModel):
    updated: int
    passed: int
    rejected: int


class RetryPostRequest(BaseModel):
    """Derived from §14.2 manual retry action."""

    source_id: str


class RetryPostResponse(BaseModel):
    source_id: str
    processing_state: ProcessingState


class BatchesListResponse(BaseModel):
    """Derived from §9.1 GET /batches startup scan — list of in-flight BatchRecords."""

    batches: list[BatchRecord]


class BatchDetailResponse(BaseModel):
    """Derived from §9.1 GET /batches/{batch_id} — single BatchRecord."""

    batch: BatchRecord


class EscalationEntryWire(BaseModel):
    """Derived from §14.2 escalation panel row."""

    source_id: str
    title: str
    source: SourceEnum
    url: str
    processing_state: ProcessingState
    error_log: list[ErrorLog]


class EscalationsResponse(BaseModel):
    entries: list[EscalationEntryWire]


# --- Typed poll entry payloads (for router serialization) ---


class ManifestPollResponse(PollResponse):
    entries: list[ManifestEntry]


class EntryPollResponse(PollResponse):
    entries: list[Entry]
