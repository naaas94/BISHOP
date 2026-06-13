"""Query embedding encoder for dense retrieval (M7 T3)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from bishop_shared.indexing_config import EMBEDDING_DIM, EMBEDDING_MODEL

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer


class _EncodeModel(Protocol):
    def encode(self, texts: list[str], *, convert_to_numpy: bool) -> object: ...


class QueryEmbeddingEncoder:
    """Encodes raw query strings (not N1 index-time concat) for LanceDB search."""

    def __init__(self, model: _EncodeModel | None = None) -> None:
        if model is not None:
            self._model = model
        else:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(EMBEDDING_MODEL)

    def encode_query(self, text: str) -> list[float]:
        vectors = self._model.encode([text], convert_to_numpy=True)
        values = vectors[0].tolist()
        if len(values) != EMBEDDING_DIM:
            raise ValueError(
                f"encoder returned dimension {len(values)}; expected {EMBEDDING_DIM}"
            )
        return values
