"""Unit tests for query-api DuckDbReader (M7 T3)."""

from __future__ import annotations

import importlib.util
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import ModuleType

import duckdb
import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_QUERY_API_ROOT = _REPO_ROOT / "services" / "query-api"
_VECTOR_WRITER_ROOT = _REPO_ROOT / "services" / "vector-writer"


def _load_duckdb_reader_module() -> ModuleType:
    path = _QUERY_API_ROOT / "app" / "stores" / "duckdb_reader.py"
    spec = importlib.util.spec_from_file_location("query_api_duckdb_reader_under_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_duckdb_mirror_module() -> ModuleType:
    path = _VECTOR_WRITER_ROOT / "app" / "stores" / "duckdb_mirror.py"
    spec = importlib.util.spec_from_file_location("t3_duckdb_mirror_writer", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _sample_row(
    module: ModuleType,
    *,
    source_id: str,
    source: str = "arxiv",
    domain: str = "professional",
    title: str = "Hybrid Retrieval",
    ingested_at: datetime | None = None,
    relevance_score: float = 0.92,
    tags: list[str] | None = None,
    entry_type: str = "paper",
    reading_status: str = "unread",
) -> object:
    return module.EntryMirrorRow(
        source_id=source_id,
        source=source,
        url=f"https://example.test/{source_id}",
        title=title,
        published_at=datetime(2024, 1, 15, tzinfo=UTC),
        ingested_at=ingested_at or datetime(2026, 6, 13, 12, 0, tzinfo=UTC),
        domain=domain,
        entry_type=entry_type,
        relevance_score=relevance_score,
        reading_status=reading_status,
        summary="Dense and sparse search combined.",
        tags=tags or ["retrieval", "hybrid"],
        concepts=["vector search", "bm25"],
        challenge_hooks=["sparse document graphs"],
    )


def _seed_mirror(db_path: Path) -> ModuleType:
    mirror_mod = _load_duckdb_mirror_module()
    mirror = mirror_mod.DuckDbMirror(db_path)
    try:
        mirror.upsert(_sample_row(mirror_mod, source_id="arxiv:2401.00001", title="High relevance"))
        mirror.upsert(
            _sample_row(
                mirror_mod,
                source_id="arxiv:2401.00002",
                title="Low relevance",
                relevance_score=0.4,
                tags=["other"],
                source="github",
                domain="personal",
                entry_type="repo",
                reading_status="read",
                ingested_at=datetime(2026, 5, 1, tzinfo=UTC),
            )
        )
        mirror.upsert(
            _sample_row(
                mirror_mod,
                source_id="arxiv:2401.00003",
                title="Recent RAG",
                tags=["RAG"],
                ingested_at=datetime.now(tz=UTC) - timedelta(days=2),
            )
        )
    finally:
        mirror.close()
    return mirror_mod


def test_connect_uses_read_only_true(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Falsifier: DuckDB must open with read_only=True per kill criterion."""
    _seed_mirror(tmp_path / "bishop.duckdb")
    reader_mod = _load_duckdb_reader_module()
    captured: dict[str, object] = {}
    real_connect = duckdb.connect

    def _fake_connect(path: str, *, read_only: bool = False) -> duckdb.DuckDBPyConnection:
        captured["path"] = path
        captured["read_only"] = read_only
        return real_connect(path, read_only=read_only)

    monkeypatch.setattr(reader_mod.duckdb, "connect", _fake_connect)
    reader = reader_mod.DuckDbReader(tmp_path / "bishop.duckdb")
    reader.filter_source_ids(min_relevance=0.5)

    assert captured["read_only"] is True


def test_filter_source_ids_empty_when_file_missing(tmp_path: Path) -> None:
    reader_mod = _load_duckdb_reader_module()
    reader = reader_mod.DuckDbReader(tmp_path / "missing.duckdb")

    assert reader.filter_source_ids(min_relevance=0.5) == []


def test_filter_source_ids_applies_metadata_predicates(tmp_path: Path) -> None:
    db_path = tmp_path / "bishop.duckdb"
    _seed_mirror(db_path)
    reader_mod = _load_duckdb_reader_module()
    reader = reader_mod.DuckDbReader(db_path)

    assert reader.filter_source_ids(min_relevance=0.7) == ["arxiv:2401.00001", "arxiv:2401.00003"]
    assert reader.filter_source_ids(source="github") == ["arxiv:2401.00002"]
    assert reader.filter_source_ids(domain="personal") == ["arxiv:2401.00002"]
    assert reader.filter_source_ids(entry_type="paper", reading_status="unread") == [
        "arxiv:2401.00001",
        "arxiv:2401.00003",
    ]
    assert reader.filter_source_ids(tags=["RAG"]) == ["arxiv:2401.00003"]


def test_recent_returns_entries_within_days_window(tmp_path: Path) -> None:
    db_path = tmp_path / "bishop.duckdb"
    _seed_mirror(db_path)
    reader_mod = _load_duckdb_reader_module()
    reader = reader_mod.DuckDbReader(db_path)

    recent = reader.recent(days=30, source="arxiv", domain="professional")

    source_ids = [entry.source_id for entry in recent]
    assert source_ids == ["arxiv:2401.00001", "arxiv:2401.00003"]
    assert recent[0].title == "High relevance"


def test_recent_empty_when_table_missing(tmp_path: Path) -> None:
    reader_mod = _load_duckdb_reader_module()
    reader = reader_mod.DuckDbReader(tmp_path / "bishop.duckdb")

    assert reader.recent(days=7) == []


def test_fetch_hit_metadata_returns_empty_on_lock_conflict(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reader_mod = _load_duckdb_reader_module()
    reader = reader_mod.DuckDbReader(tmp_path / "bishop.duckdb")

    def _always_locked(*_args: object, **_kwargs: object) -> duckdb.DuckDBPyConnection:
        raise duckdb.IOException("Could not set lock: Conflicting lock is held")

    monkeypatch.setattr(reader_mod.duckdb, "connect", _always_locked)

    assert reader.fetch_hit_metadata(["arxiv:1"]) == {}
