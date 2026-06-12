"""Wire DTOs for scraper ↔ state-worker HTTP integration."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from bishop_shared.enums import DomainEnum, SourceEnum


class ManifestIngestEntry(BaseModel):
    source_id: str
    source: SourceEnum
    url: str
    title: str
    abstract: str | None = None
    published_at: datetime | None = None
    domain: DomainEnum


class ManifestBatchResult(BaseModel):
    inserted: int
    skipped: int


class ScraperStateSnapshot(BaseModel):
    source: SourceEnum
    last_successful_run_at: datetime | None
    updated_at: datetime
