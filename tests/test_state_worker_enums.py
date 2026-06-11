"""Unit tests for state-worker enums (spec §6.1, §20)."""

import sys
from pathlib import Path

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

SPEC_PROCESSING_STATES = (
    "DISCOVERED",
    "RELEVANCE_QUEUED",
    "RELEVANCE_PASSED",
    "RELEVANCE_REJECTED",
    "SCRAPE_QUEUED",
    "SCRAPED",
    "ENRICHMENT_STAGE1_QUEUED",
    "ENRICHMENT_STAGE1_SUBMITTED",
    "ENRICHMENT_STAGE1_COMPLETE",
    "ENRICHMENT_STAGE2_QUEUED",
    "ENRICHMENT_STAGE2_CLAIMED",
    "ENRICHMENT_STAGE2_SUBMITTED",
    "ENRICHMENT_STAGE2_COMPLETE",
    "VECTOR_WRITE_QUEUED",
    "INDEXED",
    "SCRAPE_FAILED",
    "ENRICHMENT_STAGE1_FAILED",
    "ENRICHMENT_STAGE2_FAILED",
    "VECTOR_WRITE_FAILED",
    "ESCALATION_FLAGGED",
    "PERMANENTLY_FAILED",
)


def test_processing_state_members_match_spec() -> None:
    actual = tuple(member.value for member in ProcessingState)
    assert actual == SPEC_PROCESSING_STATES
    assert len(actual) == len(set(actual))


def test_section_20_enum_members() -> None:
    assert {m.value for m in SourceEnum} == {
        "arxiv",
        "semantic_scholar",
        "huggingface",
        "paperswithcode",
        "github",
        "openreview",
        "lesswrong",
    }
    assert {m.value for m in DomainEnum} == {"professional", "personal"}
    assert {m.value for m in BatchTypeEnum} == {
        "pre_filter",
        "enrichment_stage1",
        "enrichment_stage2",
    }
    assert {m.value for m in BatchStatusEnum} == {
        "pending",
        "submitted",
        "processing",
        "complete",
        "failed",
        "batch_timed_out",
    }
    assert {m.value for m in EntryTypeEnum} == {
        "paper",
        "model",
        "dataset",
        "repo",
        "article",
        "spec",
        "idea",
        "benchmark",
        "other",
    }
    assert {m.value for m in ReadingStatusEnum} == {
        "unread",
        "reading",
        "read",
        "archived",
    }
    assert {m.value for m in OovReviewStatusEnum} == {
        "pending",
        "added_to_taxonomy",
        "rejected",
    }
