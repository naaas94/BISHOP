"""Unit tests for problem-shaped query detection (M7 T4 contract surface)."""

from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType

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


def _load_problem_shaped_module() -> ModuleType:
    saved = _clear_app_modules()
    path_str = str(_QUERY_API_ROOT)
    inserted = None
    if path_str not in sys.path:
        sys.path.insert(0, path_str)
        inserted = path_str
    try:
        from app.retrieval import problem_shaped  # noqa: WPS433
    finally:
        _restore_app_modules(saved, inserted)
    return problem_shaped


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("how to build a RAG pipeline", True),
        ("How Do I tune retrieval?", True),
        ("best way to shard indexes", True),
        ("what approaches exist for chunking", True),
        ("LangGraph retry loop failure", True),
        ("sparse graph retrieval tradeoff", True),
        ("LangGraph", False),
        ("papers from last 30 days tagged RAG", False),
        ("arxiv 2024 hybrid retrieval", False),
        ("", False),
        ("   ", False),
    ],
)
def test_is_problem_shaped_prefix_and_content_heuristics(
    query: str,
    expected: bool,
) -> None:
    mod = _load_problem_shaped_module()
    assert mod.is_problem_shaped(query) is expected


def test_is_problem_shaped_normalizes_case_and_whitespace() -> None:
    mod = _load_problem_shaped_module()
    assert mod.is_problem_shaped("  HOW TO deploy  ") is True
    assert mod.is_problem_shaped("  LangGraph  ") is False
