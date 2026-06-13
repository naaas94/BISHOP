"""Controlled tag taxonomy and OOV validation (spec §20.8)."""

from __future__ import annotations

# Spec §20.8 — MVP scaffold literals; order preserved for prompt injection.
TAG_TAXONOMY: frozenset[str] = frozenset(
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

TAG_TAXONOMY_ORDERED: tuple[str, ...] = (
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
)


def validate_tags(tags: list[str]) -> tuple[list[str], list[str]]:
    """Return (validated in-order tags, stripped OOV tags)."""
    validated: list[str] = []
    stripped: list[str] = []
    for tag in tags:
        if tag in TAG_TAXONOMY:
            validated.append(tag)
        else:
            stripped.append(tag)
    return validated, stripped
