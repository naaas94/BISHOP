"""Shared BM25 tokenization for index write and query read paths (M7 T1)."""


def tokenize_bm25(text: str) -> list[str]:
    """Lowercase whitespace split — must match vector-writer index-time tokenization."""
    return text.lower().split()
