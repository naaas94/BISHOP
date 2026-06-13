"""Unit tests for bishop_shared.tag_taxonomy (M5 T1)."""

from __future__ import annotations

from bishop_shared.tag_taxonomy import TAG_TAXONOMY, validate_tags

# Spec §20.8 literals (grep bishop_spec_0_6.md)
SPEC_TAG_LITERALS = frozenset(
    {
        "NLP",
        "RAG",
        "agentic",
        "multi-agent",
        "LangGraph",
        "inference",
        "serving",
        "evaluation",
        "observability",
        "fine-tuning",
        "document-intelligence",
        "embeddings",
        "vector-stores",
        "graph-retrieval",
        "hybrid-retrieval",
        "prompt-engineering",
        "structured-output",
        "memory-architecture",
        "tool-use",
        "orchestration",
        "dataset",
        "benchmark",
        "survey",
        "production",
        "deployment",
        "optimization",
        "architecture",
        "safety",
        "alignment",
    }
)


def test_taxonomy_matches_spec_literals() -> None:
    assert TAG_TAXONOMY == SPEC_TAG_LITERALS
    assert len(TAG_TAXONOMY) == 29


def test_validate_tags_strips_oov() -> None:
    validated, stripped = validate_tags(["RAG", "not-a-real-tag", "embeddings", "fake"])
    assert validated == ["RAG", "embeddings"]
    assert stripped == ["not-a-real-tag", "fake"]
