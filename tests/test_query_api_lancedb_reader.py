"""Unit tests for query-api LanceDbSearcher (M7 T3)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

from bishop_shared.indexing_config import EMBEDDING_DIM, LANCEDB_TABLE_NAME

_REPO_ROOT = Path(__file__).resolve().parent.parent
_QUERY_API_ROOT = _REPO_ROOT / "services" / "query-api"
_VECTOR_WRITER_ROOT = _REPO_ROOT / "services" / "vector-writer"


def _load_lancedb_reader_module() -> ModuleType:
    path = _QUERY_API_ROOT / "app" / "stores" / "lancedb_reader.py"
    spec = importlib.util.spec_from_file_location("query_api_lancedb_reader_under_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_lancedb_store_module() -> ModuleType:
    path = _VECTOR_WRITER_ROOT / "app" / "stores" / "lancedb_store.py"
    spec = importlib.util.spec_from_file_location("t3_lancedb_store_writer", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _unit_vector(dim: int) -> list[float]:
    vector = [0.0] * EMBEDDING_DIM
    vector[dim % EMBEDDING_DIM] = 1.0
    return vector


def _seed_rows(tmp_path: Path) -> ModuleType:
    store_mod = _load_lancedb_store_module()
    store = store_mod.LanceDbStore(tmp_path)

    rows = [
        ("arxiv:2506.00001", _unit_vector(0), "professional", "Alpha"),
        ("arxiv:2506.00002", _unit_vector(1), "professional", "Beta"),
        ("arxiv:2506.00003", _unit_vector(2), "personal", "Gamma"),
    ]
    for source_id, vector, domain, title in rows:
        row = store_mod.LanceRow(
            source_id=source_id,
            vector=vector,
            title=title,
            summary=f"Summary for {title}",
            domain=domain,
            tags=["tag-a"],
            challenge_hooks=["hook-a"],
            relevance_score=0.9,
        )
        assert store.write(row) is True

    return store_mod


def test_search_returns_empty_when_table_missing(tmp_path: Path) -> None:
    reader_mod = _load_lancedb_reader_module()
    searcher = reader_mod.LanceDbSearcher(tmp_path)

    hits = searcher.search(_unit_vector(0), k=5)

    assert hits == []


def test_search_cosine_top_k_orders_by_similarity(tmp_path: Path) -> None:
    _seed_rows(tmp_path)
    reader_mod = _load_lancedb_reader_module()
    searcher = reader_mod.LanceDbSearcher(tmp_path)

    hits = searcher.search(_unit_vector(1), k=2)

    assert len(hits) == 2
    assert hits[0][0] == "arxiv:2506.00002"
    assert hits[0][1] > hits[1][1]


def test_search_filters_by_domain(tmp_path: Path) -> None:
    _seed_rows(tmp_path)
    reader_mod = _load_lancedb_reader_module()
    searcher = reader_mod.LanceDbSearcher(tmp_path)

    hits = searcher.search(_unit_vector(2), k=5, domain="personal")

    assert [source_id for source_id, _score in hits] == ["arxiv:2506.00003"]


def test_search_rejects_vector_dimension_mismatch(tmp_path: Path) -> None:
    """Falsifier: search must reject vectors whose length != EMBEDDING_DIM."""
    _seed_rows(tmp_path)
    reader_mod = _load_lancedb_reader_module()
    searcher = reader_mod.LanceDbSearcher(tmp_path)

    with pytest.raises(ValueError, match="EMBEDDING_DIM"):
        searcher.search([0.1, 0.2, 0.3], k=1)


def test_search_uses_entries_table_name(tmp_path: Path) -> None:
    _seed_rows(tmp_path)
    reader_mod = _load_lancedb_reader_module()
    searcher = reader_mod.LanceDbSearcher(tmp_path)

    table = searcher._db.open_table(LANCEDB_TABLE_NAME)
    assert table.count_rows() == 3
