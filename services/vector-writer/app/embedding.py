"""Embedding encoder for vector-writer (M6 T2)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from bishop_shared.indexing_config import EMBEDDING_DIM, EMBEDDING_MODEL

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer


class _EncodeModel(Protocol):
    def encode(self, texts: list[str], *, convert_to_numpy: bool) -> object: ...


class EmbeddingEncoder:
    """Wraps SentenceTransformer for pinned all-MiniLM-L6-v2 embeddings."""

    def __init__(self, model: _EncodeModel | None = None) -> None:
        if model is not None:
            self._model = model
        else:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(EMBEDDING_MODEL)

    def encode(self, texts: list[str]) -> list[list[float]]:
        vectors = self._model.encode(texts, convert_to_numpy=True)
        result: list[list[float]] = []
        for vector in vectors:
            values = vector.tolist()
            if len(values) != EMBEDDING_DIM:
                raise ValueError(
                    f"encoder returned dimension {len(values)}; expected {EMBEDDING_DIM}"
                )
            result.append(values)
        return result
