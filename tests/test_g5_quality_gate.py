"""G5 embedding quality gate — fixture (CI) and optional live probe (M6 T6)."""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from types import ModuleType

import pytest

from bishop_shared.indexing_config import EMBEDDING_DIM, LANCEDB_TABLE_NAME

_REPO_ROOT = Path(__file__).resolve().parent.parent
_VECTOR_WRITER_ROOT = _REPO_ROOT / "services" / "vector-writer"
_FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "g5_quality_gate.py"


def _load_g5_fixture_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("g5_quality_gate_fixture", _FIXTURE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_g5_fixture = _load_g5_fixture_module()
G5_FIXTURE_ENTRIES = _g5_fixture.G5_FIXTURE_ENTRIES
G5_FIXTURE_QUERIES = _g5_fixture.G5_FIXTURE_QUERIES
fixture_embed_text = _g5_fixture.fixture_embed_text
fixture_vector_keys = _g5_fixture.fixture_vector_keys


def _load_lancedb_store_module() -> ModuleType:
    path = _VECTOR_WRITER_ROOT / "app" / "stores" / "lancedb_store.py"
    spec = importlib.util.spec_from_file_location("g5_lancedb_store", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _unit_vector(dim: int) -> list[float]:
    vector = [0.0] * EMBEDDING_DIM
    vector[dim % EMBEDDING_DIM] = 1.0
    return vector


class FixtureEmbeddingEncoder:
    """Deterministic encoder: fixture keys map to orthogonal unit vectors."""

    def __init__(self) -> None:
        self._keys = fixture_vector_keys()

    def encode(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            if text not in self._keys:
                raise KeyError(f"unregistered fixture text: {text!r}")
            vectors.append(_unit_vector(self._keys[text]))
        return vectors


def _index_fixture_corpus(tmp_path: Path) -> tuple[ModuleType, FixtureEmbeddingEncoder]:
    store_mod = _load_lancedb_store_module()
    store = store_mod.LanceDbStore(tmp_path)
    encoder = FixtureEmbeddingEncoder()

    for entry in G5_FIXTURE_ENTRIES:
        embed_text = fixture_embed_text(entry)
        vector = encoder.encode([embed_text])[0]
        row = store_mod.LanceRow(
            source_id=str(entry["source_id"]),
            vector=vector,
            title=str(entry["title"]),
            summary=str(entry["summary"]),
            domain="professional",
            tags=list(entry["tags"]),  # type: ignore[arg-type]
            challenge_hooks=list(entry["challenge_hooks"]),  # type: ignore[arg-type]
            relevance_score=0.9,
        )
        assert store.write(row) is True

    return store_mod, encoder


def _top_source_id(store_mod: ModuleType, store: object, query_vector: list[float]) -> str:
    table = store._db.open_table(LANCEDB_TABLE_NAME)  # type: ignore[attr-defined]
    hits = table.search(query_vector).limit(1).to_list()
    assert hits, "expected at least one LanceDB hit"
    return str(hits[0]["source_id"])


def test_g5_fixture_queries_count() -> None:
    assert len(G5_FIXTURE_QUERIES) >= 3


def test_g5_quality_gate_fixture(tmp_path: Path) -> None:
    """CI gate: mocked vectors rank expected source_id top-1 for each G5 query."""
    store_mod, encoder = _index_fixture_corpus(tmp_path)
    store = store_mod.LanceDbStore(tmp_path)

    for query, expected_source_id in G5_FIXTURE_QUERIES:
        query_vector = encoder.encode([query])[0]
        top_id = _top_source_id(store_mod, store, query_vector)
        assert top_id == expected_source_id, f"query={query!r}"


@pytest.mark.heavy
def test_g5_quality_gate_live(tmp_path: Path) -> None:
    """Manual pre-M7 gate: real SentenceTransformer when BISHOP_G5_LIVE=1."""
    if os.environ.get("BISHOP_G5_LIVE") != "1":
        pytest.skip("set BISHOP_G5_LIVE=1 to run live embedding quality gate")

    worker_str = str(_VECTOR_WRITER_ROOT)
    if worker_str not in sys.path:
        sys.path.insert(0, worker_str)
    from app.embedding import EmbeddingEncoder  # noqa: WPS433

    store_mod = _load_lancedb_store_module()
    store = store_mod.LanceDbStore(tmp_path)
    encoder = EmbeddingEncoder()

    for entry in G5_FIXTURE_ENTRIES:
        embed_text = fixture_embed_text(entry)
        vector = encoder.encode([embed_text])[0]
        row = store_mod.LanceRow(
            source_id=str(entry["source_id"]),
            vector=vector,
            title=str(entry["title"]),
            summary=str(entry["summary"]),
            domain="professional",
            tags=list(entry["tags"]),  # type: ignore[arg-type]
            challenge_hooks=list(entry["challenge_hooks"]),  # type: ignore[arg-type]
            relevance_score=0.9,
        )
        store.write(row)

    for query, expected_source_id in G5_FIXTURE_QUERIES:
        query_vector = encoder.encode([query])[0]
        top_id = _top_source_id(store_mod, store, query_vector)
        assert top_id == expected_source_id, f"live query={query!r}"
