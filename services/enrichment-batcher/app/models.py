"""Wire DTOs for enrichment-batcher HTTP and batch assembly."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel

from bishop_shared.enums import DomainEnum, SourceEnum

ENRICHMENT_STAGE1_BATCH_TYPE = "enrichment_stage1"


class EntryPollEntry(BaseModel):
    source_id: str
    source: SourceEnum
    url: str
    title: str
    content_raw: str
    published_at: datetime | None = None
    ingested_at: datetime | None = None
    domain: DomainEnum
    profile_version: str
    processing_state: str | None = None


class EntryPollResponse(BaseModel):
    entries: list[EntryPollEntry]
    claimed_count: int
    transitioned_to: str | None = None


class BatchRegisterRequest(BaseModel):
    batch_id: str
    batch_type: Literal["enrichment_stage1"] = ENRICHMENT_STAGE1_BATCH_TYPE
    domain: DomainEnum
    profile_version: str
    profile_render_hash: str
    source_ids: list[str]
    external_batch_id: str | None = None
    entry_count: int


class BatchRegisterResponse(BaseModel):
    batch_id: str
    status: str


class Stage1BatchEntry(BaseModel):
    """One Anthropic batch request row — custom_id must equal source_id."""

    source_id: str
    source: SourceEnum
    title: str
    truncated_content: str


class AnthropicBatchSubmitResult(BaseModel):
    external_batch_id: str
    request_payload: list[dict[str, Any]]
