"""Unit tests for RRF fusion (M7 T4 contract surface)."""

from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType

import pytest

from bishop_shared.query_config import RRF_K

_REPO_ROOT = Path(__file__).resolve().parent.parent
_QUERY_API_ROOT = _REPO_ROOT / "services" / "query-api"

# Frozen rank lists for deterministic RRF assertions (k=60).
FROZEN_LIST_A = ["doc-a", "doc-b", "doc-c"]
FROZEN_LIST_B = ["doc-b", "doc-a"]
FROZEN_LIST_C = ["doc-c", "doc-a"]


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


def _load_rrf_module() -> ModuleType:
    saved = _clear_app_modules()
    path_str = str(_QUERY_API_ROOT)
    inserted = None
    if path_str not in sys.path:
        sys.path.insert(0, path_str)
        inserted = path_str
    try:
        from app.retrieval import rrf  # noqa: WPS433
    finally:
        _restore_app_modules(saved, inserted)
    return rrf


def _expected_rrf_score(source_id: str, rank_lists: list[list[str]], k: int) -> float:
    total = 0.0
    for ranked in rank_lists:
        if source_id in ranked:
            rank = ranked.index(source_id) + 1
            total += 1.0 / (k + rank)
    return total


def test_rrf_fuse_frozen_two_channel_fixture() -> None:
    mod = _load_rrf_module()
    rank_lists = [FROZEN_LIST_A, FROZEN_LIST_B]
    fused = mod.rrf_fuse(rank_lists, k=RRF_K)

    expected_scores = {
        source_id: _expected_rrf_score(source_id, rank_lists, RRF_K)
        for source_id in ("doc-a", "doc-b", "doc-c")
    }
    assert fused == sorted(expected_scores.items(), key=lambda item: item[1], reverse=True)


def test_rrf_fuse_defaults_to_shared_rrf_k() -> None:
    mod = _load_rrf_module()
    rank_lists = [FROZEN_LIST_A, FROZEN_LIST_B]
    assert mod.rrf_fuse(rank_lists) == mod.rrf_fuse(rank_lists, k=RRF_K)


def test_rrf_fuse_inactive_third_channel_matches_two_channel() -> None:
    mod = _load_rrf_module()
    two_channel = mod.rrf_fuse([FROZEN_LIST_A, FROZEN_LIST_B], k=RRF_K)
    three_channel_empty = mod.rrf_fuse([FROZEN_LIST_A, FROZEN_LIST_B, []], k=RRF_K)
    assert two_channel == three_channel_empty


def test_rrf_fuse_third_channel_changes_problem_shaped_fusion() -> None:
    mod = _load_rrf_module()
    two_channel = mod.rrf_fuse([FROZEN_LIST_A, FROZEN_LIST_B], k=RRF_K)
    three_channel = mod.rrf_fuse([FROZEN_LIST_A, FROZEN_LIST_B, FROZEN_LIST_C], k=RRF_K)
    assert two_channel != three_channel
    assert three_channel[0][0] == "doc-a"


def test_rrf_fuse_duplicate_source_id_in_one_list_double_counts() -> None:
    mod = _load_rrf_module()
    duplicated = ["doc-a", "doc-a", "doc-b"]
    fused = mod.rrf_fuse([duplicated], k=RRF_K)
    doc_a_score = next(score for source_id, score in fused if source_id == "doc-a")
    doc_b_score = next(score for source_id, score in fused if source_id == "doc-b")
    assert doc_a_score == pytest.approx((1.0 / 61) + (1.0 / 62))
    assert doc_b_score == pytest.approx(1.0 / 63)
