"""Unit tests for query-api QueryEmbeddingEncoder (M7 T3)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import numpy as np
import pytest

from bishop_shared.indexing_config import EMBEDDING_DIM, EMBEDDING_MODEL, build_embed_text

_REPO_ROOT = Path(__file__).resolve().parent.parent
_QUERY_API_ROOT = _REPO_ROOT / "services" / "query-api"


def _load_embedding_module() -> ModuleType:
    path = _QUERY_API_ROOT / "app" / "embedding.py"
    spec = importlib.util.spec_from_file_location("query_api_embedding_under_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class _FakeModel:
    def __init__(self, dim: int = EMBEDDING_DIM) -> None:
        self._dim = dim
        self.calls: list[list[str]] = []

    def encode(self, texts: list[str], *, convert_to_numpy: bool) -> np.ndarray:
        self.calls.append(list(texts))
        return np.full((len(texts), self._dim), 0.42, dtype=np.float32)


def test_encode_query_returns_384_dim_vector() -> None:
    embedding = _load_embedding_module()
    fake = _FakeModel()
    encoder = embedding.QueryEmbeddingEncoder(model=fake)

    vector = encoder.encode_query("sparse graph retrieval")

    assert fake.calls == [["sparse graph retrieval"]]
    assert len(vector) == EMBEDDING_DIM
    assert vector[0] == pytest.approx(0.42)


def test_encode_query_uses_raw_query_not_n1_concat() -> None:
    """Falsifier: query encoder must not apply index-time N1 title/summary/hooks concat."""
    embedding = _load_embedding_module()
    fake = _FakeModel()
    encoder = embedding.QueryEmbeddingEncoder(model=fake)
    raw_query = "how do I handle sparse retrieval"
    n1_text = build_embed_text("ignored title", "ignored summary", ["ignored hook"])

    encoder.encode_query(raw_query)

    assert fake.calls == [[raw_query]]
    assert fake.calls != [[n1_text]]


def test_encode_query_rejects_wrong_dimension_from_model() -> None:
    embedding = _load_embedding_module()
    encoder = embedding.QueryEmbeddingEncoder(model=_FakeModel(dim=128))

    with pytest.raises(ValueError, match="expected 384"):
        encoder.encode_query("only-one")


def test_embedding_model_matches_indexing_config() -> None:
    assert EMBEDDING_MODEL == "sentence-transformers/all-MiniLM-L6-v2"
