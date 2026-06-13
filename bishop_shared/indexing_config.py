"""Indexing pipeline constants and embed-text builder (spec §5.6, §8.4)."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

from bishop_shared.constants import BISHOP_VOLUME_MOUNTS

EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_DIM = 384

_LANCEDB_MOUNT = next(m for m in BISHOP_VOLUME_MOUNTS if m.host_suffix == "lancedb").container_path
_DUCKDB_MOUNT = next(m for m in BISHOP_VOLUME_MOUNTS if m.host_suffix == "duckdb").container_path
_BM25_MOUNT = next(m for m in BISHOP_VOLUME_MOUNTS if m.host_suffix == "bm25").container_path

LANCEDB_DIR = _LANCEDB_MOUNT
LANCEDB_TABLE_NAME = "entries"

DUCKDB_FILENAME = "bishop.duckdb"
DUCKDB_PATH = f"{_DUCKDB_MOUNT}/{DUCKDB_FILENAME}"

BM25_MAIN_SUBDIR = "main"
BM25_CHALLENGE_HOOKS_SUBDIR = "challenge_hooks"
BM25_LOCK_NAME = ".bm25_write.lock"


def bm25_domain_root(domain: str) -> Path:
    """Per-domain BM25 index root under the bm25 volume mount."""
    return Path(_BM25_MOUNT) / domain


def build_embed_text(
    title: str,
    summary: str,
    challenge_hooks: Sequence[str] | None,
) -> str:
    """Pinned N1 embedding text: title, summary, space-joined challenge_hooks."""
    return f"{title}\n{summary}\n{' '.join(challenge_hooks or [])}"
