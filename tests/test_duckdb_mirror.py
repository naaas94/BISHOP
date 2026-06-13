"""Unit tests for DuckDbMirror (M6 T4 contract surface)."""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType

import duckdb
import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_VECTOR_WRITER_ROOT = _REPO_ROOT / "services" / "vector-writer"


def _load_duckdb_mirror_module() -> ModuleType:
    path = _VECTOR_WRITER_ROOT / "app" / "stores" / "duckdb_mirror.py"
    module_name = "duckdb_mirror_under_test"
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _sample_row(module: ModuleType, *, title: str = "Hybrid Retrieval") -> object:
    return module.EntryMirrorRow(
        source_id="arxiv:2401.00001",
        source="arxiv",
        url="https://arxiv.org/abs/2401.00001",
        title=title,
        published_at=datetime(2024, 1, 15, tzinfo=UTC),
        ingested_at=datetime(2024, 1, 16, 12, 0, tzinfo=UTC),
        domain="professional",
        entry_type="paper",
        relevance_score=0.92,
        reading_status="unread",
        summary="Dense and sparse search combined.",
        tags=["retrieval", "hybrid"],
        concepts=["vector search", "bm25"],
        challenge_hooks=["sparse document graphs"],
    )


def _fetch_row(db_path: Path, source_id: str) -> tuple:
    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        row = conn.execute(
            "SELECT source_id, title, tags, concepts, challenge_hooks FROM entries_mirror WHERE source_id = ?",
            [source_id],
        ).fetchone()
        assert row is not None
        return row
    finally:
        conn.close()


def test_entries_mirror_table_name_and_ddl(tmp_path: Path) -> None:
    module = _load_duckdb_mirror_module()
    assert module.TABLE_NAME == "entries_mirror"

    db_path = tmp_path / "bishop.duckdb"
    mirror = module.DuckDbMirror(db_path)
    try:
        tables = {
            row[0]
            for row in mirror._conn.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'"
            ).fetchall()
        }
        assert tables == {"entries_mirror"}
    finally:
        mirror.close()


def test_upsert_inserts_metadata_row(tmp_path: Path) -> None:
    module = _load_duckdb_mirror_module()
    db_path = tmp_path / "bishop.duckdb"
    mirror = module.DuckDbMirror(db_path)
    try:
        mirror.upsert(_sample_row(module))
    finally:
        mirror.close()

    source_id, title, tags, concepts, challenge_hooks = _fetch_row(db_path, "arxiv:2401.00001")
    assert source_id == "arxiv:2401.00001"
    assert title == "Hybrid Retrieval"
    assert json.loads(tags) == ["retrieval", "hybrid"]
    assert json.loads(concepts) == ["vector search", "bm25"]
    assert json.loads(challenge_hooks) == ["sparse document graphs"]


def test_upsert_uses_insert_or_replace_semantics(tmp_path: Path) -> None:
    """Falsifier: second upsert for same source_id must replace, not duplicate."""
    module = _load_duckdb_mirror_module()
    db_path = tmp_path / "bishop.duckdb"
    mirror = module.DuckDbMirror(db_path)
    try:
        mirror.upsert(_sample_row(module, title="Original Title"))
        mirror.upsert(_sample_row(module, title="Replaced Title"))
    finally:
        mirror.close()

    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        count = conn.execute("SELECT COUNT(*) FROM entries_mirror").fetchone()[0]
        title = conn.execute(
            "SELECT title FROM entries_mirror WHERE source_id = ?",
            ["arxiv:2401.00001"],
        ).fetchone()[0]
    finally:
        conn.close()

    assert count == 1
    assert title == "Replaced Title"


def test_upsert_json_columns_round_trip_null_and_empty(tmp_path: Path) -> None:
    """Falsifier: NULL JSON columns must not coerce to empty arrays on read."""
    module = _load_duckdb_mirror_module()
    db_path = tmp_path / "bishop.duckdb"
    mirror = module.DuckDbMirror(db_path)
    row = module.EntryMirrorRow(
        source_id="arxiv:2401.00002",
        source="arxiv",
        url="https://arxiv.org/abs/2401.00002",
        title="Null JSON columns",
        published_at=None,
        ingested_at=datetime(2024, 1, 16, tzinfo=UTC),
        domain="professional",
        entry_type=None,
        relevance_score=None,
        reading_status="unread",
        summary=None,
        tags=None,
        concepts=[],
        challenge_hooks=None,
    )
    try:
        mirror.upsert(row)
    finally:
        mirror.close()

    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        fetched = conn.execute(
            "SELECT tags, concepts, challenge_hooks FROM entries_mirror WHERE source_id = ?",
            ["arxiv:2401.00002"],
        ).fetchone()
    finally:
        conn.close()

    assert fetched is not None
    tags, concepts, challenge_hooks = fetched
    assert tags is None
    assert json.loads(concepts) == []
    assert challenge_hooks is None


def test_duckdb_path_default_matches_indexing_config(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_duckdb_mirror_module()
    from bishop_shared.indexing_config import DUCKDB_PATH

    assert module.DUCKDB_PATH == DUCKDB_PATH
