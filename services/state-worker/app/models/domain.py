"""Domain Pydantic models mirroring spec §7 SQLite tables."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.enums import (
    BatchStatusEnum,
    BatchTypeEnum,
    DomainEnum,
    EntryTypeEnum,
    OovReviewStatusEnum,
    ProcessingState,
    ReadingStatusEnum,
    SourceEnum,
)

JSON_LIST_FIELDS = frozenset(
    {
        "concepts",
        "tags",
        "challenge_hooks",
        "references",
        "cited_by",
        "top_entries",
        "source_ids",
    }
)


def encode_json_list_fields(row: dict[str, Any]) -> dict[str, Any]:
    """Serialize list[str] columns to JSON text for SQLite writes."""
    encoded = dict(row)
    for key in JSON_LIST_FIELDS:
        if key in encoded and encoded[key] is not None and not isinstance(encoded[key], str):
            encoded[key] = json.dumps(encoded[key])
    return encoded


def decode_json_list_fields(row: dict[str, Any]) -> dict[str, Any]:
    """Deserialize JSON text columns to list[str] on read."""
    decoded = dict(row)
    for key in JSON_LIST_FIELDS:
        value = decoded.get(key)
        if value is not None and isinstance(value, str):
            decoded[key] = json.loads(value)
    return decoded


class ManifestEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    source_id: str
    source: SourceEnum
    url: str
    title: str
    abstract: str | None = None
    published_at: datetime | None = None
    discovered_at: datetime
    domain: DomainEnum
    profile_version: str | None = None
    pre_filter_batch_id: str | None = None
    relevance_decision: int | None = None
    pre_filter_rationale: str | None = None
    processing_state: ProcessingState
    retry_count: int = 0
    next_retry_at: datetime | None = None

    @field_validator("relevance_decision")
    @classmethod
    def relevance_decision_binary(cls, value: int | None) -> int | None:
        if value is not None and value not in (0, 1):
            raise ValueError("relevance_decision must be 0 or 1")
        return value

    def to_db_row(self) -> dict[str, Any]:
        row = self.model_dump(mode="python")
        row["source"] = self.source.value
        row["domain"] = self.domain.value
        row["processing_state"] = self.processing_state.value
        for key in ("published_at", "discovered_at", "next_retry_at"):
            if row[key] is not None:
                row[key] = row[key].isoformat()
        return row

    @classmethod
    def from_db_row(cls, row: dict[str, Any]) -> ManifestEntry:
        return cls.model_validate(row)


class Entry(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    source_id: str
    source: SourceEnum
    url: str
    title: str
    content_raw: str
    published_at: datetime | None = None
    ingested_at: datetime
    domain: DomainEnum
    profile_version: str
    pre_filter_batch_id: str
    pre_filter_rationale: str
    summary: str | None = None
    concepts: list[str] | None = None
    tags: list[str] | None = None
    entry_type: EntryTypeEnum | None = None
    challenge_hooks: list[str] | None = None
    enrichment_stage1_batch_id: str | None = None
    relevance_score: float | None = None
    relevance_reason: str | None = None
    value_rationale: str | None = None
    enrichment_stage2_batch_id: str | None = None
    references: list[str] | None = None
    cited_by: list[str] | None = None
    reading_status: ReadingStatusEnum = ReadingStatusEnum.UNREAD
    flagged_for_review: bool = False
    processing_state: ProcessingState

    def to_db_row(self) -> dict[str, Any]:
        row = self.model_dump(mode="python")
        row["source"] = self.source.value
        row["domain"] = self.domain.value
        row["entry_type"] = self.entry_type.value if self.entry_type else None
        row["reading_status"] = self.reading_status.value
        row["processing_state"] = self.processing_state.value
        row["flagged_for_review"] = int(self.flagged_for_review)
        for key in ("published_at", "ingested_at"):
            if row[key] is not None:
                row[key] = row[key].isoformat()
        return encode_json_list_fields(row)

    @classmethod
    def from_db_row(cls, row: dict[str, Any]) -> Entry:
        normalized = decode_json_list_fields(dict(row))
        if isinstance(normalized.get("flagged_for_review"), int):
            normalized["flagged_for_review"] = bool(normalized["flagged_for_review"])
        return cls.model_validate(normalized)


class BatchRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    batch_id: str
    batch_type: BatchTypeEnum
    domain: DomainEnum
    profile_version: str
    profile_render_hash: str
    status: BatchStatusEnum
    created_at: datetime
    submitted_at: datetime | None = None
    completed_at: datetime | None = None
    entry_count: int
    passed_count: int
    failed_count: int
    top_entries: list[str] = Field(default_factory=list)
    source_ids: list[str] = Field(default_factory=list)
    external_batch_id: str | None = None

    def to_db_row(self) -> dict[str, Any]:
        row = self.model_dump(mode="python")
        row["batch_type"] = self.batch_type.value
        row["domain"] = self.domain.value
        row["status"] = self.status.value
        for key in ("created_at", "submitted_at", "completed_at"):
            if row[key] is not None:
                row[key] = row[key].isoformat()
        return encode_json_list_fields(row)

    @classmethod
    def from_db_row(cls, row: dict[str, Any]) -> BatchRecord:
        return cls.model_validate(decode_json_list_fields(dict(row)))


class ErrorLog(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    source_id: str
    attempt_number: int
    state_at_failure: ProcessingState
    error_class: str
    http_status: int | None = None
    message: str
    is_retriable: bool
    timestamp: datetime
    next_retry_at: datetime | None = None

    def to_db_row(self) -> dict[str, Any]:
        row = self.model_dump(mode="python")
        row["state_at_failure"] = self.state_at_failure.value
        row["is_retriable"] = int(self.is_retriable)
        for key in ("timestamp", "next_retry_at"):
            if row[key] is not None:
                row[key] = row[key].isoformat()
        return row

    @classmethod
    def from_db_row(cls, row: dict[str, Any]) -> ErrorLog:
        normalized = dict(row)
        if isinstance(normalized.get("is_retriable"), int):
            normalized["is_retriable"] = bool(normalized["is_retriable"])
        return cls.model_validate(normalized)


class OovTagsLog(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    source_id: str
    tag_value: str
    entry_type: EntryTypeEnum
    enrichment_batch_id: str
    timestamp: datetime
    review_status: OovReviewStatusEnum

    def to_db_row(self) -> dict[str, Any]:
        row = self.model_dump(mode="python")
        row["entry_type"] = self.entry_type.value
        row["review_status"] = self.review_status.value
        row["timestamp"] = self.timestamp.isoformat()
        return row

    @classmethod
    def from_db_row(cls, row: dict[str, Any]) -> OovTagsLog:
        return cls.model_validate(row)


class ScraperState(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    source: SourceEnum
    last_successful_run_at: datetime | None = None
    updated_at: datetime

    def to_db_row(self) -> dict[str, Any]:
        row = self.model_dump(mode="python")
        row["source"] = self.source.value
        for key in ("last_successful_run_at", "updated_at"):
            if row[key] is not None:
                row[key] = row[key].isoformat()
        return row

    @classmethod
    def from_db_row(cls, row: dict[str, Any]) -> ScraperState:
        return cls.model_validate(row)
