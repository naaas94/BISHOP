"""Wire DTOs for pre-filter-worker HTTP and batch assembly."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel

from bishop_shared.enums import DomainEnum, SourceEnum


class ManifestPollEntry(BaseModel):
    source_id: str
    source: SourceEnum
    url: str
    title: str
    abstract: str | None = None
    published_at: datetime | None = None
    discovered_at: datetime | None = None
    domain: DomainEnum
    processing_state: str | None = None


class ManifestPollResponse(BaseModel):
    entries: list[ManifestPollEntry]
    claimed_count: int
    transitioned_to: str | None = None


class BatchRegisterRequest(BaseModel):
    batch_id: str
    batch_type: Literal["pre_filter"] = "pre_filter"
    domain: DomainEnum
    profile_version: str
    profile_render_hash: str
    source_ids: list[str]
    external_batch_id: str | None = None
    entry_count: int


class BatchRegisterResponse(BaseModel):
    batch_id: str
    status: str


class PreFilterBatchEntry(BaseModel):
    """One Anthropic batch request row — custom_id must equal source_id."""

    source_id: str
    title: str
    abstract: str | None = None

    def user_message(self) -> str:
        body = self.abstract or ""
        return f"{self.title}\n{body}"


class AnthropicBatchSubmitResult(BaseModel):
    external_batch_id: str
    request_payload: list[dict[str, Any]]
