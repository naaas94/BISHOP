"""DuckDB mirror write path vs concurrent reader connections (M6 T6)."""

from __future__ import annotations

import importlib.util
import sys
import threading
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType

import duckdb
import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_VECTOR_WRITER_ROOT = _REPO_ROOT / "services" / "vector-writer"


def _load_duckdb_mirror_module() -> ModuleType:
    path = _VECTOR_WRITER_ROOT / "app" / "stores" / "duckdb_mirror.py"
    spec = importlib.util.spec_from_file_location("duckdb_concurrent_mirror", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _sample_row(module: ModuleType) -> object:
    return module.EntryMirrorRow(
        source_id="arxiv:2506.00001",
        source="arxiv",
        url="https://arxiv.org/abs/2506.00001",
        title="Concurrent Read Test",
        published_at=datetime(2026, 6, 13, tzinfo=UTC),
        ingested_at=datetime(2026, 6, 13, 12, 0, tzinfo=UTC),
        domain="professional",
        entry_type="paper",
        relevance_score=0.88,
        reading_status="unread",
        summary="Mirror row for concurrent read probe.",
        tags=["duckdb"],
        concepts=["concurrency"],
        challenge_hooks=["read_only while writing"],
    )


def test_separate_connection_reads_while_mirror_holds_write(tmp_path: Path) -> None:
    """Falsifier: a second DuckDB connection must read while mirror keeps write open.

    DuckDB disallows mixing read_only and read-write on one file; M7 query-api uses
    read_only only when vector-writer has released the file between upserts.
  """
    module = _load_duckdb_mirror_module()
    db_path = tmp_path / "bishop.duckdb"
    mirror = module.DuckDbMirror(db_path)
    results: dict[str, object] = {}

    try:
        mirror.upsert(_sample_row(module))

        def _reader() -> None:
            reader = duckdb.connect(str(db_path))
            try:
                row = reader.execute(
                    "SELECT title FROM entries_mirror WHERE source_id = ?",
                    ["arxiv:2506.00001"],
                ).fetchone()
                results["title"] = row[0] if row else None
            finally:
                reader.close()

        thread = threading.Thread(target=_reader)
        thread.start()
        thread.join(timeout=2.0)
        assert not thread.is_alive()
        assert results.get("title") == "Concurrent Read Test"
    finally:
        mirror.close()


def test_read_only_connection_after_mirror_releases_write(tmp_path: Path) -> None:
    """M7 steady-state: read_only=True succeeds once vector-writer closes its connection."""
    module = _load_duckdb_mirror_module()
    db_path = tmp_path / "bishop.duckdb"
    mirror = module.DuckDbMirror(db_path)
    mirror.upsert(_sample_row(module))
    mirror.close()

    reader = duckdb.connect(str(db_path), read_only=True)
    try:
        count = reader.execute("SELECT COUNT(*) FROM entries_mirror").fetchone()
        assert count is not None and count[0] == 1
    finally:
        reader.close()
