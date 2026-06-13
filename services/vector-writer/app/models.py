"""Wire DTOs for vector-writer ↔ state-worker HTTP integration."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from bishop_shared.enums import DomainEnum, SourceEnum

from app.config import VECTOR_WRITE_POLL_STATE


class EntryPollRow(BaseModel):
    """Poll JSON entry row — content_raw is omitted at VECTOR_WRITE_QUEUED."""

    source_id: str
    source: SourceEnum
    url: str
    title: str
    published_at: datetime | None = None
    ingested_at: datetime
    domain: DomainEnum
    profile_version: str
    pre_filter_batch_id: str
    pre_filter_rationale: str
    summary: str | None = None
    concepts: list[str] | None = None
    tags: list[str] | None = None
    entry_type: str | None = None
    challenge_hooks: list[str] | None = None
    relevance_score: float | None = None
    reading_status: str = "unread"
    processing_state: str | None = None


class EntryPollResponse(BaseModel):
    entries: list[EntryPollRow]
    claimed_count: int
    transitioned_to: str | None = None


class IndexedPostRequest(BaseModel):
    source_id: str


class FailedPostRequest(BaseModel):
    source_id: str
    state_at_failure: Literal["VECTOR_WRITE_QUEUED"] = VECTOR_WRITE_POLL_STATE
    error_class: str
    http_status: int | None = None
    message: str
    is_retriable: bool
