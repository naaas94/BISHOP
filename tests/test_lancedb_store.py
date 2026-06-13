"""Unit tests for vector-writer LanceDbStore (M6 T2)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

from bishop_shared.indexing_config import EMBEDDING_DIM, LANCEDB_TABLE_NAME

_REPO_ROOT = Path(__file__).resolve().parent.parent
_VECTOR_WRITER_ROOT = _REPO_ROOT / "services" / "vector-writer"


def _load_lancedb_store_module() -> ModuleType:
    path = _VECTOR_WRITER_ROOT / "app" / "stores" / "lancedb_store.py"
    spec = importlib.util.spec_from_file_location("vector_writer_lancedb_store_under_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _sample_vector(seed: float = 0.1) -> list[float]:
    return [seed + (index * 0.001) for index in range(EMBEDDING_DIM)]


def _sample_row(source_id: str, *, seed: float = 0.1) -> object:
    store_mod = _load_lancedb_store_module()
    return store_mod.LanceRow(
        source_id=source_id,
        vector=_sample_vector(seed),
        title=f"Title for {source_id}",
        summary=f"Summary for {source_id}",
        domain="professional",
        tags=["tag-a"],
        challenge_hooks=["hook-a"],
        relevance_score=0.85,
    )


def test_write_persists_row_and_exists_by_source_id(tmp_path: Path) -> None:
    store_mod = _load_lancedb_store_module()
    store = store_mod.LanceDbStore(tmp_path)
    row = _sample_row("entry-001")

    assert store.exists("entry-001") is False
    assert store.write(row) is True
    assert store.exists("entry-001") is True

    table = store._db.open_table(LANCEDB_TABLE_NAME)
    records = table.search().where("source_id = 'entry-001'").limit(1).to_list()
    assert len(records) == 1
    assert records[0]["source_id"] == "entry-001"
    assert len(records[0]["vector"]) == EMBEDDING_DIM


def test_write_skips_duplicate_source_id(tmp_path: Path) -> None:
    """Falsifier: idempotent re-write must not create a second LanceDB row."""
    store_mod = _load_lancedb_store_module()
    store = store_mod.LanceDbStore(tmp_path)
    row = _sample_row("entry-dup")

    assert store.write(row) is True
    assert store.write(row) is False

    table = store._db.open_table(LANCEDB_TABLE_NAME)
    records = table.search().where("source_id = 'entry-dup'").limit(1).to_list()
    assert len(records) == 1


def test_exists_uses_source_id_not_title(tmp_path: Path) -> None:
    """Falsifier: idempotency key must be source_id, not title or other fields."""
    store_mod = _load_lancedb_store_module()
    store = store_mod.LanceDbStore(tmp_path)
    row = _sample_row("unique-source-id")

    store.write(row)

    assert store.exists("unique-source-id") is True
    assert store.exists("Title for unique-source-id") is False


def test_write_rejects_vector_dimension_mismatch(tmp_path: Path) -> None:
    """Falsifier: write must reject vectors whose length != EMBEDDING_DIM."""
    store_mod = _load_lancedb_store_module()
    store = store_mod.LanceDbStore(tmp_path)
    bad_row = store_mod.LanceRow(
        source_id="bad-dim",
        vector=[0.1, 0.2, 0.3],
        title="t",
        summary="s",
        domain="professional",
        tags=[],
        challenge_hooks=[],
        relevance_score=None,
    )

    with pytest.raises(ValueError, match="EMBEDDING_DIM"):
        store.write(bad_row)

    assert store.exists("bad-dim") is False
