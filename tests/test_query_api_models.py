"""Unit tests for query-api pydantic models (M7 T5)."""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_QUERY_API_ROOT = _REPO_ROOT / "services" / "query-api"


def _load_models():
    path_str = str(_QUERY_API_ROOT)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)
    from app import models  # noqa: WPS433

    return models


def test_search_hit_round_trip() -> None:
    models = _load_models()
    hit = models.SearchHit(
        source_id="arxiv:2401.00001",
        rrf_score=0.032,
        title="Test Paper",
        summary="A summary",
        relevance_score=0.85,
        entry_type="paper",
        tags=["RAG"],
    )
    payload = hit.model_dump()
    assert payload["source_id"] == "arxiv:2401.00001"
    assert payload["rrf_score"] == 0.032
    assert payload["tags"] == ["RAG"]


def test_search_response_shape() -> None:
    models = _load_models()
    response = models.SearchResponse(
        query="transformer attention",
        problem_shaped=False,
        channels_active=["bm25_main", "dense"],
        hits=[],
        total=0,
    )
    data = response.model_dump()
    assert data["query"] == "transformer attention"
    assert data["problem_shaped"] is False
    assert data["channels_active"] == ["bm25_main", "dense"]
    assert data["total"] == 0


def test_search_request_accepts_type_alias() -> None:
    models = _load_models()
    request = models.SearchRequest.model_validate(
        {"q": "query", "type": "paper"},
    )
    assert request.type == "paper"
