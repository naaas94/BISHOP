"""Unit tests for vector-writer Bm25DualIndex (M6 T3 contract surface)."""

from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType

import pytest
from filelock import FileLock, Timeout

from bishop_shared.indexing_config import (
    BM25_CHALLENGE_HOOKS_SUBDIR,
    BM25_LOCK_NAME,
    BM25_MAIN_SUBDIR,
)

_REPO_ROOT = Path(__file__).resolve().parent.parent
_VECTOR_WRITER_ROOT = _REPO_ROOT / "services" / "vector-writer"


def _load_bm25_store_module() -> ModuleType:
    path_str = str(_VECTOR_WRITER_ROOT)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)
    from app.stores import bm25_store

    return bm25_store


@pytest.fixture
def bm25_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "bm25"

    def _root(domain: str) -> Path:
        return root / domain

    monkeypatch.setattr("bishop_shared.indexing_config.bm25_domain_root", _root)
    bm25_store = _load_bm25_store_module()
    monkeypatch.setattr(bm25_store, "bm25_domain_root", _root)
    return root


def _sample_entry() -> dict[str, object]:
    return {
        "source_id": "arxiv:2401.00001",
        "title": "Hybrid Retrieval",
        "summary": "Combines dense and sparse search.",
        "concepts": ["bm25", "embeddings"],
        "tags": ["retrieval"],
        "challenge_hooks": ["sparse document graphs", "vector index rebuild"],
    }


def test_has_document_false_until_added(bm25_root: Path) -> None:
    bm25_store = _load_bm25_store_module()
    index = bm25_store.Bm25DualIndex("professional")

    assert index.has_document("arxiv:2401.00001") is False

    entry = _sample_entry()
    index.add_main(
        str(entry["source_id"]),
        str(entry["title"]),
        str(entry["summary"]),
        list(entry["concepts"]),  # type: ignore[arg-type]
        list(entry["tags"]),  # type: ignore[arg-type]
        list(entry["challenge_hooks"]),  # type: ignore[arg-type]
    )
    index.add_challenge_hooks(
        str(entry["source_id"]),
        list(entry["challenge_hooks"]),  # type: ignore[arg-type]
    )

    assert index.has_document("arxiv:2401.00001") is True


def test_add_main_rejects_duplicate_source_id(bm25_root: Path) -> None:
    bm25_store = _load_bm25_store_module()
    index = bm25_store.Bm25DualIndex("professional")
    entry = _sample_entry()

    index.add_main(
        str(entry["source_id"]),
        str(entry["title"]),
        str(entry["summary"]),
        list(entry["concepts"]),  # type: ignore[arg-type]
        list(entry["tags"]),  # type: ignore[arg-type]
        list(entry["challenge_hooks"]),  # type: ignore[arg-type]
    )

    with pytest.raises(ValueError, match="duplicate source_id"):
        index.add_main(
            str(entry["source_id"]),
            "Other",
            "Other summary",
            [],
            [],
            [],
        )


def test_add_challenge_hooks_rejects_duplicate_source_id(bm25_root: Path) -> None:
    bm25_store = _load_bm25_store_module()
    index = bm25_store.Bm25DualIndex("professional")
    entry = _sample_entry()

    index.add_challenge_hooks(
        str(entry["source_id"]),
        list(entry["challenge_hooks"]),  # type: ignore[arg-type]
    )

    with pytest.raises(ValueError, match="duplicate source_id"):
        index.add_challenge_hooks(str(entry["source_id"]), ["duplicate hooks"])


def test_persist_reload_roundtrip(bm25_root: Path) -> None:
    bm25_store = _load_bm25_store_module()
    entry = _sample_entry()
    domain_root = bm25_root / "professional"

    writer = bm25_store.Bm25DualIndex("professional")
    writer.add_main(
        str(entry["source_id"]),
        str(entry["title"]),
        str(entry["summary"]),
        list(entry["concepts"]),  # type: ignore[arg-type]
        list(entry["tags"]),  # type: ignore[arg-type]
        list(entry["challenge_hooks"]),  # type: ignore[arg-type]
    )
    writer.add_challenge_hooks(
        str(entry["source_id"]),
        list(entry["challenge_hooks"]),  # type: ignore[arg-type]
    )
    writer.persist()

    main_path = domain_root / BM25_MAIN_SUBDIR / bm25_store.INDEX_FILENAME
    hooks_path = domain_root / BM25_CHALLENGE_HOOKS_SUBDIR / bm25_store.INDEX_FILENAME
    assert main_path.is_file()
    assert hooks_path.is_file()
    assert not any(domain_root.rglob("*.tmp"))

    reader = bm25_store.Bm25DualIndex("professional")
    assert reader.has_document("arxiv:2401.00001") is True
    assert reader._hooks.has_document("arxiv:2401.00001") is True
    assert reader._main.bm25 is not None
    assert len(reader._main.corpus) == 1
    assert reader._main.corpus[0]  # non-empty token list persisted


def test_single_lock_file_at_domain_root(bm25_root: Path) -> None:
    """Falsifier: main and challenge_hooks must share one lock at domain root."""
    bm25_store = _load_bm25_store_module()
    index = bm25_store.Bm25DualIndex("professional")
    domain_root = bm25_root / "professional"

    assert index.lock_path == domain_root / BM25_LOCK_NAME
    index.persist()

    assert not (domain_root / BM25_MAIN_SUBDIR / BM25_LOCK_NAME).exists()
    assert not (domain_root / BM25_CHALLENGE_HOOKS_SUBDIR / BM25_LOCK_NAME).exists()


def test_persist_calls_atomic_persist(
    bm25_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Falsifier: persist must delegate to bishop_shared.atomic_persist."""
    bm25_store = _load_bm25_store_module()
    calls: list[Path] = []
    real_atomic_persist = bm25_store.atomic_persist

    def track_atomic_persist(path: Path | str, serialize_fn: object) -> None:
        calls.append(Path(path))
        real_atomic_persist(path, serialize_fn)  # type: ignore[arg-type]

    monkeypatch.setattr(bm25_store, "atomic_persist", track_atomic_persist)

    index = bm25_store.Bm25DualIndex("professional")
    entry = _sample_entry()
    index.add_main(
        str(entry["source_id"]),
        str(entry["title"]),
        str(entry["summary"]),
        list(entry["concepts"]),  # type: ignore[arg-type]
        list(entry["tags"]),  # type: ignore[arg-type]
        list(entry["challenge_hooks"]),  # type: ignore[arg-type]
    )
    index.add_challenge_hooks(
        str(entry["source_id"]),
        list(entry["challenge_hooks"]),  # type: ignore[arg-type]
    )
    index.persist()

    domain_root = bm25_root / "professional"
    expected = {
        domain_root / BM25_MAIN_SUBDIR / bm25_store.INDEX_FILENAME,
        domain_root / BM25_CHALLENGE_HOOKS_SUBDIR / bm25_store.INDEX_FILENAME,
    }
    assert set(calls) == expected


def test_persist_raises_on_lock_timeout(bm25_root: Path) -> None:
    """Falsifier: lock timeout must surface as filelock.Timeout."""
    bm25_store = _load_bm25_store_module()
    index = bm25_store.Bm25DualIndex("professional", lock_timeout=0.05)
    held = FileLock(str(index.lock_path))
    held.acquire()

    try:
        with pytest.raises(Timeout, match="BM25 lock timeout"):
            index.persist()
    finally:
        held.release()
