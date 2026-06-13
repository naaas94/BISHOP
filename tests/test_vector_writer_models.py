"""Unit tests for vector-writer EntryPollRow models (M6 T5 contract surface)."""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType

from bishop_shared.enums import DomainEnum, SourceEnum

_REPO_ROOT = Path(__file__).resolve().parent.parent
_VECTOR_WRITER_ROOT = _REPO_ROOT / "services" / "vector-writer"


def _load_models_module() -> ModuleType:
    saved_app_modules = {
        name: module
        for name, module in sys.modules.items()
        if name == "app" or name.startswith("app.")
    }
    for name in saved_app_modules:
        del sys.modules[name]

    path_str = str(_VECTOR_WRITER_ROOT)
    inserted = False
    if path_str not in sys.path:
        sys.path.insert(0, path_str)
        inserted = True

    try:
        import app.models as models_mod  # noqa: WPS433
    finally:
        for name in list(sys.modules):
            if name == "app" or name.startswith("app."):
                del sys.modules[name]
        sys.modules.update(saved_app_modules)
        if inserted:
            sys.path.remove(path_str)

    return models_mod


def test_entry_poll_row_parses_poll_json_without_content_raw() -> None:
    models = _load_models_module()
    payload = {
        "id": "entry-uuid-1",
        "source_id": "arxiv:2401.00001",
        "source": "arxiv",
        "url": "https://arxiv.org/abs/2401.00001",
        "title": "Hybrid Retrieval",
        "published_at": "2024-01-15T00:00:00+00:00",
        "ingested_at": "2024-01-16T12:00:00+00:00",
        "domain": "professional",
        "profile_version": "1.0.0",
        "pre_filter_batch_id": "batch-1",
        "pre_filter_rationale": "Relevant",
        "summary": "Dense and sparse search combined.",
        "concepts": ["vector search"],
        "tags": ["retrieval"],
        "challenge_hooks": ["sparse document graphs"],
        "relevance_score": 0.92,
        "reading_status": "unread",
        "processing_state": "VECTOR_WRITE_QUEUED",
    }
    row = models.EntryPollRow.model_validate(payload)
    assert row.source_id == "arxiv:2401.00001"
    assert row.summary == "Dense and sparse search combined."
    assert "content_raw" not in payload


def test_entry_poll_row_round_trip() -> None:
    models = _load_models_module()
    row = models.EntryPollRow(
        source_id="arxiv:2401.00001",
        source=SourceEnum.ARXIV,
        url="https://arxiv.org/abs/2401.00001",
        title="Hybrid Retrieval",
        published_at=datetime(2024, 1, 15, tzinfo=UTC),
        ingested_at=datetime(2024, 1, 16, 12, 0, tzinfo=UTC),
        domain=DomainEnum.PROFESSIONAL,
        profile_version="1.0.0",
        pre_filter_batch_id="batch-1",
        pre_filter_rationale="Relevant",
        summary="Dense and sparse search combined.",
        concepts=["vector search"],
        tags=["retrieval"],
        challenge_hooks=["sparse document graphs"],
        relevance_score=0.92,
        processing_state="VECTOR_WRITE_QUEUED",
    )
    restored = models.EntryPollRow.model_validate(row.model_dump(mode="json"))
    assert restored.source_id == row.source_id
    assert restored.challenge_hooks == row.challenge_hooks
