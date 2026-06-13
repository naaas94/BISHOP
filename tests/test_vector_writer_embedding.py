"""Unit tests for vector-writer EmbeddingEncoder (M6 T2)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import numpy as np
import pytest

from bishop_shared.indexing_config import EMBEDDING_DIM

_REPO_ROOT = Path(__file__).resolve().parent.parent
_VECTOR_WRITER_ROOT = _REPO_ROOT / "services" / "vector-writer"


def _load_embedding_module() -> ModuleType:
    path = _VECTOR_WRITER_ROOT / "app" / "embedding.py"
    spec = importlib.util.spec_from_file_location("vector_writer_embedding_under_test", path)
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
        rows = []
        for index, _text in enumerate(texts):
            rows.append(np.full(self._dim, float(index + 1), dtype=np.float32))
        return np.stack(rows)


def test_encode_returns_list_of_384_dim_vectors() -> None:
    embedding = _load_embedding_module()
    fake = _FakeModel()
    encoder = embedding.EmbeddingEncoder(model=fake)

    vectors = encoder.encode(["alpha", "beta"])

    assert fake.calls == [["alpha", "beta"]]
    assert len(vectors) == 2
    assert all(len(vector) == EMBEDDING_DIM for vector in vectors)
    assert vectors[0][0] == pytest.approx(1.0)


def test_encode_rejects_wrong_dimension_from_model() -> None:
    """Falsifier: encoder must reject vectors whose length != EMBEDDING_DIM."""
    embedding = _load_embedding_module()
    encoder = embedding.EmbeddingEncoder(model=_FakeModel(dim=128))

    with pytest.raises(ValueError, match="expected 384"):
        encoder.encode(["only-one"])
