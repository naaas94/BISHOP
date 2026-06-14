"""Unit tests for query-api search orchestrator (M7 T4 contract surface)."""

from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType
from typing import Literal
from unittest.mock import MagicMock

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_QUERY_API_ROOT = _REPO_ROOT / "services" / "query-api"


def _clear_app_modules() -> dict[str, ModuleType]:
    saved = {
        name: module
        for name, module in sys.modules.items()
        if name == "app" or name.startswith("app.")
    }
    for name in saved:
        del sys.modules[name]
    return saved


def _restore_app_modules(saved: dict[str, ModuleType], inserted_path: str | None) -> None:
    for name in list(sys.modules):
        if name == "app" or name.startswith("app."):
            del sys.modules[name]
    sys.modules.update(saved)
    if inserted_path is not None:
        sys.path.remove(inserted_path)


def _load_search_module() -> ModuleType:
    saved = _clear_app_modules()
    path_str = str(_QUERY_API_ROOT)
    inserted = None
    if path_str not in sys.path:
        sys.path.insert(0, path_str)
        inserted = path_str
    try:
        from app.retrieval import search  # noqa: WPS433
    finally:
        _restore_app_modules(saved, inserted)
    return search


def _make_bm25_mock(
    *,
    main: list[tuple[str, float]],
    hooks: list[tuple[str, float]],
) -> MagicMock:
    bm25 = MagicMock()

    def _search(
        query: str,
        k: int,
        *,
        channel: Literal["main", "challenge_hooks"] = "main",
    ) -> list[tuple[str, float]]:
        del query, k
        return list(main if channel == "main" else hooks)

    bm25.search.side_effect = _search
    return bm25


def test_run_search_standard_query_omits_hooks_channel() -> None:
    search_mod = _load_search_module()
    bm25 = _make_bm25_mock(
        main=[("arxiv:1", 1.0), ("arxiv:2", 0.5)],
        hooks=[("arxiv:9", 9.0)],
    )
    dense = MagicMock()
    dense.search.return_value = [("arxiv:2", 0.9), ("arxiv:1", 0.8)]
    metadata = MagicMock()
    encoder = MagicMock()
    encoder.encode_query.return_value = [0.1] * 384

    result = search_mod.run_search(
        query="LangGraph",
        bm25=bm25,
        dense=dense,
        metadata=metadata,
        encoder=encoder,
    )

    assert result.problem_shaped is False
    assert result.channels_active == ["bm25_main", "dense"]
    bm25.search.assert_called_once_with("LangGraph", 20, channel="main")
    dense.search.assert_called_once()
    metadata.filter_source_ids.assert_not_called()
    assert {hit[0] for hit in result.hits[:2]} == {"arxiv:1", "arxiv:2"}


def test_run_search_problem_shaped_activates_hooks_channel() -> None:
    search_mod = _load_search_module()
    bm25 = _make_bm25_mock(
        main=[("arxiv:1", 1.0)],
        hooks=[("arxiv:hooks", 5.0)],
    )
    dense = MagicMock()
    dense.search.return_value = [("arxiv:1", 0.9)]
    metadata = MagicMock()
    encoder = MagicMock()
    encoder.encode_query.return_value = [0.1] * 384

    result = search_mod.run_search(
        query="how to handle retrieval failure",
        bm25=bm25,
        dense=dense,
        metadata=metadata,
        encoder=encoder,
    )

    assert result.problem_shaped is True
    assert result.channels_active == ["bm25_main", "dense", "bm25_hooks"]
    assert bm25.search.call_count == 2
    bm25.search.assert_any_call(
        "how to handle retrieval failure",
        20,
        channel="main",
    )
    bm25.search.assert_any_call(
        "how to handle retrieval failure",
        20,
        channel="challenge_hooks",
    )


def test_run_search_inactive_hooks_same_scores_as_two_channel() -> None:
    search_mod = _load_search_module()
    main_hits = [("arxiv:1", 1.0), ("arxiv:2", 0.5)]
    dense_hits = [("arxiv:2", 0.9), ("arxiv:1", 0.8)]

    bm25_standard = _make_bm25_mock(main=main_hits, hooks=[("arxiv:9", 9.0)])
    dense = MagicMock()
    dense.search.return_value = dense_hits
    metadata = MagicMock()
    encoder = MagicMock()
    encoder.encode_query.return_value = [0.1] * 384

    standard = search_mod.run_search(
        query="LangGraph",
        bm25=bm25_standard,
        dense=dense,
        metadata=metadata,
        encoder=encoder,
    )

    bm25_problem = _make_bm25_mock(main=main_hits, hooks=[])
    problem_shaped = search_mod.run_search(
        query="how to handle retrieval failure",
        bm25=bm25_problem,
        dense=dense,
        metadata=metadata,
        encoder=encoder,
    )

    assert standard.hits == problem_shaped.hits


def test_run_search_metadata_pre_filter_empty_returns_no_hits() -> None:
    search_mod = _load_search_module()
    bm25 = _make_bm25_mock(main=[("arxiv:1", 1.0)], hooks=[])
    dense = MagicMock()
    metadata = MagicMock()
    metadata.filter_source_ids.return_value = []
    encoder = MagicMock()

    result = search_mod.run_search(
        query="LangGraph",
        bm25=bm25,
        dense=dense,
        metadata=metadata,
        encoder=encoder,
        min_relevance=0.9,
    )

    assert result.hits == []
    bm25.search.assert_not_called()
    dense.search.assert_not_called()
    encoder.encode_query.assert_not_called()
    metadata.filter_source_ids.assert_called_once_with(
        domain=None,
        source=None,
        tags=None,
        min_relevance=0.9,
        days=None,
        entry_type=None,
        reading_status=None,
    )


def test_run_search_metadata_pre_filter_restricts_channel_candidates() -> None:
    search_mod = _load_search_module()
    bm25 = _make_bm25_mock(
        main=[("arxiv:1", 1.0), ("arxiv:2", 0.5)],
        hooks=[],
    )
    dense = MagicMock()
    dense.search.return_value = [("arxiv:2", 0.9), ("arxiv:3", 0.8)]
    metadata = MagicMock()
    metadata.filter_source_ids.return_value = ["arxiv:2"]
    encoder = MagicMock()
    encoder.encode_query.return_value = [0.1] * 384

    result = search_mod.run_search(
        query="LangGraph",
        bm25=bm25,
        dense=dense,
        metadata=metadata,
        encoder=encoder,
        days=30,
    )

    assert result.hits == [("arxiv:2", pytest.approx(1.0 / (60 + 1) + 1.0 / (60 + 1)))]
    metadata.filter_source_ids.assert_called_once()


def test_run_search_skips_metadata_pre_filter_on_duckdb_lock() -> None:
    search_mod = _load_search_module()
    DuckDbLockUnavailableError = search_mod.DuckDbLockUnavailableError

    bm25 = _make_bm25_mock(main=[("arxiv:1", 1.0)], hooks=[])
    dense = MagicMock()
    dense.search.return_value = [("arxiv:1", 0.9)]
    metadata = MagicMock()
    metadata.filter_source_ids.side_effect = DuckDbLockUnavailableError("Conflicting lock")
    encoder = MagicMock()
    encoder.encode_query.return_value = [0.1] * 384

    result = search_mod.run_search(
        query="LangGraph",
        bm25=bm25,
        dense=dense,
        metadata=metadata,
        encoder=encoder,
        min_relevance=0.5,
    )

    assert result.hits
    bm25.search.assert_called_once()
    dense.search.assert_called_once()
