"""Unit tests for bishop_shared.bm25_tokenize (M7 T1 contract surface)."""

from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType

from bishop_shared.bm25_tokenize import tokenize_bm25

_REPO_ROOT = Path(__file__).resolve().parent.parent
_VECTOR_WRITER_ROOT = _REPO_ROOT / "services" / "vector-writer"


def _load_bm25_store_module() -> ModuleType:
    path_str = str(_VECTOR_WRITER_ROOT)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)
    from app.stores import bm25_store

    return bm25_store


def test_tokenize_matches_writer_semantics() -> None:
    """Falsifier: shared tokenize diverges from vector-writer index-time split."""
    sample = "Hybrid Retrieval FOR Sparse Graphs"
    assert tokenize_bm25(sample) == ["hybrid", "retrieval", "for", "sparse", "graphs"]

    bm25_store = _load_bm25_store_module()
    corpus_text = bm25_store._build_main_corpus_text(
        title="Title Case",
        summary="Summary TEXT",
        concepts=["Concept-A"],
        tags=["RAG"],
        challenge_hooks=["hook one"],
    )
    assert tokenize_bm25(corpus_text) == [part.lower() for part in corpus_text.split()]


def test_tokenize_collapses_internal_whitespace() -> None:
    """Falsifier: double spaces produce empty tokens unlike writer split()."""
    assert tokenize_bm25("alpha   beta") == ["alpha", "beta"]
