"""Wire DTOs for content-scraper ↔ state-worker HTTP integration."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from bishop_shared.enums import DomainEnum, SourceEnum

SCRAPE_QUEUED_STATE = "SCRAPE_QUEUED"


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


class ContentPostRequest(BaseModel):
    source_id: str
    content_raw: str


class ContentPostResponse(BaseModel):
    entry_id: str
    processing_state: str


class FailedPostRequest(BaseModel):
    source_id: str
    state_at_failure: Literal["SCRAPE_QUEUED"]
    error_class: str
    http_status: int | None = None
    message: str
    is_retriable: bool
