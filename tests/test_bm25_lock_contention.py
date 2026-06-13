"""BM25 domain lock contention under simulated concurrent writers (M6 T6)."""

from __future__ import annotations

import sys
import threading
from pathlib import Path
from types import ModuleType

import pytest
from filelock import FileLock, Timeout

from bishop_shared.indexing_config import BM25_LOCK_NAME

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


def test_concurrent_bm25_acquire_blocks_second_writer(bm25_root: Path) -> None:
    """Falsifier: two writers contending for domain lock must not corrupt the index."""
    bm25_store = _load_bm25_store_module()
    domain_root = bm25_root / "professional"
    lock_path = domain_root / BM25_LOCK_NAME
    domain_root.mkdir(parents=True)

    holder = FileLock(str(lock_path))
    holder.acquire()
    results: dict[str, str] = {}

    def _blocked_add() -> None:
        index = bm25_store.Bm25DualIndex("professional", lock_timeout=0.1)
        try:
            index.add_main(
                "arxiv:2506.00002",
                "Second Writer",
                "Should block until lock released.",
                ["contention"],
                ["test"],
                ["hook"],
            )
            results["writer"] = "acquired"
        except Timeout:
            results["writer"] = "timeout"

    thread = threading.Thread(target=_blocked_add)
    thread.start()
    thread.join(timeout=2.0)
    assert not thread.is_alive()
    assert results.get("writer") == "timeout"

    holder.release()

    index = bm25_store.Bm25DualIndex("professional")
    index.add_main(
        "arxiv:2506.00001",
        "First Writer",
        "Writes after external lock released.",
        ["contention"],
        ["test"],
        ["hook"],
    )
    index.persist()
    assert index.has_document("arxiv:2506.00001") is True
