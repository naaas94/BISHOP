"""Unit tests for state-worker domain Pydantic models (spec §7)."""

import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_STATE_WORKER_ROOT = _REPO_ROOT / "services" / "state-worker"

for path in (_STATE_WORKER_ROOT, _REPO_ROOT):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

from app.enums import (  # noqa: E402
    BatchStatusEnum,
    BatchTypeEnum,
    DomainEnum,
    EntryTypeEnum,
    OovReviewStatusEnum,
    ProcessingState,
    ReadingStatusEnum,
    SourceEnum,
)
from app.models.domain import (  # noqa: E402
    BatchRecord,
    Entry,
    ErrorLog,
    ManifestEntry,
    OovTagsLog,
    ScraperState,
)

_NOW = datetime(2026, 6, 11, 12, 0, 0, tzinfo=UTC)


def test_manifest_entry_round_trip() -> None:
    original = ManifestEntry(
        source_id="arxiv:2301.00001",
        source=SourceEnum.ARXIV,
        url="https://arxiv.org/abs/2301.00001",
        title="Test Paper",
        abstract="An abstract",
        published_at=_NOW,
        discovered_at=_NOW,
        domain=DomainEnum.PROFESSIONAL,
        processing_state=ProcessingState.DISCOVERED,
    )
    row = original.to_db_row()
    restored = ManifestEntry.from_db_row(
        {
            **row,
            "published_at": _NOW,
            "discovered_at": _NOW,
        }
    )
    assert restored == original


def test_entry_round_trip() -> None:
    original = Entry(
        id="entry-uuid-1",
        source_id="arxiv:2301.00001",
        source=SourceEnum.ARXIV,
        url="https://arxiv.org/abs/2301.00001",
        title="Test Paper",
        content_raw="Full text body",
        published_at=_NOW,
        ingested_at=_NOW,
        domain=DomainEnum.PROFESSIONAL,
        profile_version="1.0.0",
        pre_filter_batch_id="batch-uuid-1",
        pre_filter_rationale="Relevant to RAG research",
        summary="A dense summary",
        concepts=["RAG", "embeddings"],
        tags=["hybrid-retrieval"],
        entry_type=EntryTypeEnum.PAPER,
        challenge_hooks=["reduce latency in dense retrieval"],
        processing_state=ProcessingState.SCRAPED,
        reading_status=ReadingStatusEnum.UNREAD,
        flagged_for_review=False,
    )
    row = original.to_db_row()
    assert isinstance(row["concepts"], str)
    assert isinstance(row["tags"], str)
    restored = Entry.from_db_row(
        {
            **row,
            "published_at": _NOW,
            "ingested_at": _NOW,
            "flagged_for_review": 0,
        }
    )
    assert restored == original


def test_batch_record_round_trip() -> None:
    original = BatchRecord(
        batch_id="batch-uuid-1",
        batch_type=BatchTypeEnum.PRE_FILTER,
        domain=DomainEnum.PROFESSIONAL,
        profile_version="1.0.0",
        profile_render_hash="abc123",
        status=BatchStatusEnum.SUBMITTED,
        created_at=_NOW,
        entry_count=10,
        passed_count=0,
        failed_count=0,
        top_entries=["entry-1", "entry-2"],
    )
    row = original.to_db_row()
    assert isinstance(row["top_entries"], str)
    restored = BatchRecord.from_db_row({**row, "created_at": _NOW})
    assert restored == original


def test_error_log_round_trip() -> None:
    original = ErrorLog(
        id="err-uuid-1",
        source_id="arxiv:2301.00001",
        attempt_number=1,
        state_at_failure=ProcessingState.SCRAPE_FAILED,
        error_class="httpx.TimeoutException",
        http_status=None,
        message="Connection timed out",
        is_retriable=True,
        timestamp=_NOW,
    )
    row = original.to_db_row()
    restored = ErrorLog.from_db_row({**row, "timestamp": _NOW, "is_retriable": 1})
    assert restored == original


def test_oov_tags_log_round_trip() -> None:
    original = OovTagsLog(
        id="oov-uuid-1",
        source_id="entry-uuid-1",
        tag_value="novel-tag",
        entry_type=EntryTypeEnum.PAPER,
        enrichment_batch_id="batch-uuid-2",
        timestamp=_NOW,
        review_status=OovReviewStatusEnum.PENDING,
    )
    row = original.to_db_row()
    restored = OovTagsLog.from_db_row({**row, "timestamp": _NOW})
    assert restored == original


def test_scraper_state_round_trip() -> None:
    original = ScraperState(
        source=SourceEnum.ARXIV,
        last_successful_run_at=_NOW,
        updated_at=_NOW,
    )
    row = original.to_db_row()
    restored = ScraperState.from_db_row(
        {**row, "last_successful_run_at": _NOW, "updated_at": _NOW}
    )
    assert restored == original


def test_entry_rejects_invalid_json_list_column() -> None:
    """Falsifier: corrupt JSON text in a list column must not silently become a string."""
    with pytest.raises(Exception):
        Entry.from_db_row(
            {
                "id": "entry-uuid-1",
                "source_id": "arxiv:2301.00001",
                "source": "arxiv",
                "url": "https://example.com",
                "title": "T",
                "content_raw": "body",
                "ingested_at": _NOW,
                "domain": "professional",
                "profile_version": "1.0.0",
                "pre_filter_batch_id": "b",
                "pre_filter_rationale": "r",
                "concepts": "not-valid-json",
                "reading_status": "unread",
                "flagged_for_review": 0,
                "processing_state": "SCRAPED",
            }
        )
