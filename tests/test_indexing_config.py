"""Unit tests for bishop_shared.indexing_config (M6 T1 contract surface)."""

from pathlib import Path

from bishop_shared.constants import BISHOP_VOLUME_MOUNTS
from bishop_shared.indexing_config import (
    BM25_CHALLENGE_HOOKS_SUBDIR,
    BM25_LOCK_NAME,
    BM25_MAIN_SUBDIR,
    DUCKDB_PATH,
    EMBEDDING_DIM,
    EMBEDDING_MODEL,
    LANCEDB_DIR,
    LANCEDB_TABLE_NAME,
    bm25_domain_root,
    build_embed_text,
)


def _mount_path(host_suffix: str) -> str:
    return next(m for m in BISHOP_VOLUME_MOUNTS if m.host_suffix == host_suffix).container_path


def test_embedding_model_pinned() -> None:
    assert EMBEDDING_MODEL == "sentence-transformers/all-MiniLM-L6-v2"


def test_embedding_dim() -> None:
    assert EMBEDDING_DIM == 384


def test_build_embed_text_n1() -> None:
    title = "Hybrid Retrieval"
    summary = "Dense and sparse search combined."
    hooks = ["sparse document graphs", "vector index rebuild"]
    expected = (
        "Hybrid Retrieval\n"
        "Dense and sparse search combined.\n"
        "sparse document graphs vector index rebuild"
    )
    assert build_embed_text(title, summary, hooks) == expected


def test_build_embed_text_none_hooks() -> None:
    """Falsifier: None challenge_hooks must not raise and must join as empty."""
    assert build_embed_text("t", "s", None) == "t\ns\n"


def test_store_paths_match_constants() -> None:
    assert LANCEDB_DIR == _mount_path("lancedb")
    assert LANCEDB_TABLE_NAME == "entries"
    assert DUCKDB_PATH == f"{_mount_path('duckdb')}/bishop.duckdb"
    assert bm25_domain_root("professional") == Path(_mount_path("bm25")) / "professional"
    assert BM25_MAIN_SUBDIR == "main"
    assert BM25_CHALLENGE_HOOKS_SUBDIR == "challenge_hooks"
    assert BM25_LOCK_NAME == ".bm25_write.lock"
