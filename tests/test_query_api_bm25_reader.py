"""Unit tests for query-api Bm25QueryIndex (M7 T2 contract surface)."""

from __future__ import annotations

import asyncio
import logging
import pickle
import sys
from pathlib import Path
from types import ModuleType

import pytest

from bishop_shared.bm25_tokenize import tokenize_bm25
from bishop_shared.indexing_config import (
    BM25_CHALLENGE_HOOKS_SUBDIR,
    BM25_MAIN_SUBDIR,
)

_REPO_ROOT = Path(__file__).resolve().parent.parent
_QUERY_API_ROOT = _REPO_ROOT / "services" / "query-api"
_VECTOR_WRITER_ROOT = _REPO_ROOT / "services" / "vector-writer"


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


def _load_bm25_reader_module() -> ModuleType:
    saved = _clear_app_modules()
    path_str = str(_QUERY_API_ROOT)
    inserted = None
    if path_str not in sys.path:
        sys.path.insert(0, path_str)
        inserted = path_str
    try:
        from app.stores import bm25_reader  # noqa: WPS433
    finally:
        _restore_app_modules(saved, inserted)
    return bm25_reader


def _load_bm25_store_module() -> ModuleType:
    saved = _clear_app_modules()
    path_str = str(_VECTOR_WRITER_ROOT)
    inserted = None
    if path_str not in sys.path:
        sys.path.insert(0, path_str)
        inserted = path_str
    try:
        from app.stores import bm25_store  # noqa: WPS433
    finally:
        _restore_app_modules(saved, inserted)
    return bm25_store


@pytest.fixture
def bm25_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "bm25"

    def _root(domain: str) -> Path:
        return root / domain

    monkeypatch.setattr("bishop_shared.indexing_config.bm25_domain_root", _root)
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


def _persist_writer_indices(bm25_root: Path, domain: str = "professional") -> None:
    bm25_store = _load_bm25_store_module()
    entry = _sample_entry()
    writer = bm25_store.Bm25DualIndex(domain)
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


def test_load_search_main_from_writer_pickle(bm25_root: Path) -> None:
    bm25_reader = _load_bm25_reader_module()
    _persist_writer_indices(bm25_root)
    index = bm25_reader.Bm25QueryIndex("professional")
    index.load()

    hits = index.search("hybrid retrieval sparse", k=5)
    assert hits
    assert hits[0][0] == "arxiv:2401.00001"
    assert isinstance(hits[0][1], float)


def test_load_search_challenge_hooks_channel(bm25_root: Path) -> None:
    """Falsifier: hooks index loaded from main subdir or vice versa."""
    bm25_reader = _load_bm25_reader_module()
    _persist_writer_indices(bm25_root)
    index = bm25_reader.Bm25QueryIndex("professional")
    index.load()

    hooks_hits = index.search("sparse document graphs", k=5, channel="challenge_hooks")
    assert hooks_hits
    assert hooks_hits[0][0] == "arxiv:2401.00001"

    main_hits = index.search("vector index rebuild", k=5, channel="main")
    assert main_hits
    assert main_hits[0][0] == "arxiv:2401.00001"


def test_indices_use_correct_subdirs(bm25_root: Path) -> None:
    bm25_reader = _load_bm25_reader_module()
    _persist_writer_indices(bm25_root)
    domain_root = bm25_root / "professional"
    index = bm25_reader.Bm25QueryIndex("professional")

    assert index.main_path == domain_root / BM25_MAIN_SUBDIR / bm25_reader.INDEX_FILENAME
    assert index.hooks_path == domain_root / BM25_CHALLENGE_HOOKS_SUBDIR / bm25_reader.INDEX_FILENAME
    assert index.main_path.is_file()
    assert index.hooks_path.is_file()


def test_reload_cow_swaps_object_identity_without_in_place_mutation(
    bm25_root: Path,
) -> None:
    """Falsifier: reload mutates corpus on the live index object visible to readers."""
    bm25_reader = _load_bm25_reader_module()
    _persist_writer_indices(bm25_root)
    index = bm25_reader.Bm25QueryIndex("professional")
    index.load()

    before_main = index._main  # noqa: SLF001
    before_corpus_len = len(before_main.corpus)

    bm25_store = _load_bm25_store_module()
    writer = bm25_store.Bm25DualIndex("professional")
    writer.add_main(
        "arxiv:2401.00002",
        "Graph Neural Networks",
        "Learning on sparse graphs.",
        ["gnn"],
        ["graphs"],
        ["graph sparsity"],
    )
    writer.persist()

    index.reload_cow()
    after_main = index._main  # noqa: SLF001

    assert before_main is not after_main
    assert len(before_main.corpus) == before_corpus_len
    new_hits = index.search("graph neural", k=5)
    source_ids = {source_id for source_id, _ in new_hits}
    assert "arxiv:2401.00002" in source_ids


def test_reload_cow_keeps_old_index_on_corrupt_pickle(
    bm25_root: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    bm25_reader = _load_bm25_reader_module()
    _persist_writer_indices(bm25_root)
    index = bm25_reader.Bm25QueryIndex("professional")
    index.load()
    before_hits = index.search("hybrid retrieval", k=1)

    index.main_path.write_bytes(b"not-a-valid-pickle")
    probe_logger = logging.getLogger("test.bm25_reader.reload_fail")
    with caplog.at_level(logging.WARNING, logger=probe_logger.name):
        index.reload_cow(probe_logger)

    assert index.search("hybrid retrieval", k=1) == before_hits
    warn_records = [record for record in caplog.records if record.levelno == logging.WARNING]
    assert len(warn_records) == 1
    assert warn_records[0].event == "bm25_reload_failed"  # type: ignore[attr-defined]


def test_rejects_invalid_pickle_schema(bm25_root: Path) -> None:
    bm25_reader = _load_bm25_reader_module()
    domain_root = bm25_root / "professional"
    main_dir = domain_root / BM25_MAIN_SUBDIR
    main_dir.mkdir(parents=True)
    main_path = main_dir / bm25_reader.INDEX_FILENAME
    with main_path.open("wb") as handle:
        pickle.dump({"corpus": [], "ids": []}, handle)

    index = bm25_reader.Bm25QueryIndex("professional")
    with pytest.raises(ValueError, match="corpus \\+ source_ids"):
        index.load()


def test_search_empty_when_index_missing(bm25_root: Path) -> None:
    bm25_reader = _load_bm25_reader_module()
    index = bm25_reader.Bm25QueryIndex("professional")
    index.load()
    assert index.search("anything", k=5) == []


@pytest.mark.asyncio
async def test_background_reload_invokes_reload_cow(
    bm25_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bm25_reader = _load_bm25_reader_module()
    _persist_writer_indices(bm25_root)
    index = bm25_reader.Bm25QueryIndex("professional")
    index.load()

    calls = 0
    original_reload = index.reload_cow

    def tracked_reload(log: logging.Logger | None = None) -> None:
        nonlocal calls
        calls += 1
        original_reload(log)

    monkeypatch.setattr(index, "reload_cow", tracked_reload)
    probe_logger = logging.getLogger("test.bm25_reader.background")
    index.start_background_reload(probe_logger, interval_sec=0.01)
    await asyncio.sleep(0.05)
    await index.stop_background_reload()
    assert calls >= 1


def test_tokenize_bm25_used_for_search(bm25_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Falsifier: search bypasses shared tokenize_bm25 and drifts from writer ranks."""
    bm25_reader = _load_bm25_reader_module()
    _persist_writer_indices(bm25_root)
    index = bm25_reader.Bm25QueryIndex("professional")
    index.load()

    seen: list[str] = []

    def capture_tokenize(text: str) -> list[str]:
        seen.append(text)
        return text.lower().split()

    monkeypatch.setattr(bm25_reader, "tokenize_bm25", capture_tokenize)
    index.search("Hybrid Retrieval", k=1)
    assert seen == ["Hybrid Retrieval"]
