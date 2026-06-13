"""Unit tests for bishop_shared enrichment truncation (M5 T1)."""

from __future__ import annotations

import tiktoken

from bishop_shared.content_truncation import _clamp_to_ceiling, truncate_content_for_call1
from bishop_shared.enrichment_config import ENRICHMENT_TRUNCATION_MAX_TOKENS

_ENCODING = tiktoken.get_encoding("cl100k_base")


def _token_count(text: str) -> int:
    return len(_ENCODING.encode(text))


def test_max_tokens_constant() -> None:
    assert ENRICHMENT_TRUNCATION_MAX_TOKENS == 4000


def test_paper_strategy_abstract_plus_body_clamped() -> None:
    abstract = "Abstract\n\nWe study retrieval latency under sparse graphs."
    body = "Introduction\n\n" + ("token " * 5000)
    content = f"Title line\n\n{abstract}\n\n{body}"
    truncated = truncate_content_for_call1("arxiv", "Paper Title", content)
    assert "retrieval latency" in truncated
    assert _token_count(truncated) <= ENRICHMENT_TRUNCATION_MAX_TOKENS


def test_clamp_fixture_exactly_4000_tokens() -> None:
    """Kill-criterion falsifier: oversized corpus clamps to exactly 4000 tokens."""
    oversized = "word " * 6000
    truncated = _clamp_to_ceiling(oversized)
    assert _token_count(truncated) == ENRICHMENT_TRUNCATION_MAX_TOKENS


def test_default_strategy_beginning_end_clamped() -> None:
    filler = "word " * 6000
    content = f"LEDE CLAIMS HERE. {filler} CONCLUSION CLAIMS HERE."
    truncated = truncate_content_for_call1("lesswrong", "Article", content)
    assert "LEDE CLAIMS HERE" in truncated
    assert "CONCLUSION CLAIMS HERE" in truncated
    assert _token_count(truncated) <= ENRICHMENT_TRUNCATION_MAX_TOKENS


def test_short_content_unchanged_under_ceiling() -> None:
    content = "Short readme for a tiny repo."
    truncated = truncate_content_for_call1("github", "Repo", content)
    assert truncated == content


def test_github_over_ceiling_uses_header_and_structure() -> None:
    prose = "README intro " * 800
    structure = "\n".join(["- src/", "- tests/", "- README.md"])
    content = f"{prose}\n\nProject layout:\n{structure}"
    truncated = truncate_content_for_call1("github", "Repo", content)
    assert "- src/" in truncated
    assert _token_count(truncated) <= ENRICHMENT_TRUNCATION_MAX_TOKENS
