"""Call 1 content truncation per spec §13.1 (tiktoken cl100k_base, 4k ceiling)."""

from __future__ import annotations

import re

import tiktoken

from bishop_shared.enrichment_config import ENRICHMENT_TRUNCATION_MAX_TOKENS

_ENCODING = tiktoken.get_encoding("cl100k_base")

_PAPER_SOURCES = frozenset({"arxiv", "openreview", "semantic_scholar"})
_ARTICLE_SOURCES = frozenset({"lesswrong", "paperswithcode"})
_STRUCTURE_LINE_RE = re.compile(r"^(\s*[-*]\s+\S+|^\S+/?\s*$)", re.MULTILINE)
_ABSTRACT_SPLIT_RE = re.compile(r"\n\s*Abstract\s*:?\s*\n", re.IGNORECASE)


def _count_tokens(text: str) -> int:
    return len(_ENCODING.encode(text))


def _truncate_to_tokens(text: str, max_tokens: int) -> str:
    if max_tokens <= 0:
        return ""
    tokens = _ENCODING.encode(text)
    if len(tokens) <= max_tokens:
        return text
    return _ENCODING.decode(tokens[:max_tokens])


def _clamp_to_ceiling(text: str) -> str:
    return _truncate_to_tokens(text, ENRICHMENT_TRUNCATION_MAX_TOKENS)


def _split_paper_abstract_body(content: str) -> tuple[str, str]:
    match = _ABSTRACT_SPLIT_RE.search(content)
    if match:
        abstract = content[: match.start()].strip()
        body = content[match.end() :].strip()
        if not abstract:
            abstract = body.split("\n\n", 1)[0].strip() if body else ""
        return abstract, body
    parts = content.split("\n\n", 1)
    if len(parts) == 2:
        return parts[0].strip(), parts[1].strip()
    return content.strip(), ""


def _paper_strategy(content: str) -> str:
    abstract, body = _split_paper_abstract_body(content)
    body_truncated = _truncate_to_tokens(body, 2000)
    if abstract and body_truncated:
        return f"{abstract}\n\n{body_truncated}"
    if abstract:
        return abstract
    return body_truncated


def _github_strategy(content: str) -> str:
    if _count_tokens(content) <= ENRICHMENT_TRUNCATION_MAX_TOKENS:
        return content
    header = _truncate_to_tokens(content, 500)
    structure_lines = [
        line.strip()
        for line in content.splitlines()
        if _STRUCTURE_LINE_RE.match(line.strip())
    ]
    structure = "\n".join(structure_lines[:200])
    if structure:
        return f"{header}\n\n{structure}"
    return header


def _extract_yaml_frontmatter(content: str) -> tuple[str, str]:
    if not content.startswith("---"):
        return "", content
    end = content.find("\n---", 3)
    if end == -1:
        return "", content
    yaml_block = content[3:end].strip()
    remainder = content[end + 4 :].lstrip("\n")
    return yaml_block, remainder


def _huggingface_model_strategy(content: str) -> str:
    yaml_block, remainder = _extract_yaml_frontmatter(content)
    remainder_truncated = _truncate_to_tokens(remainder, 2000)
    if yaml_block and remainder_truncated:
        return f"---\n{yaml_block}\n---\n\n{remainder_truncated}"
    if yaml_block:
        return f"---\n{yaml_block}\n---"
    return remainder_truncated


def _beginning_end_strategy(content: str) -> str:
    tokens = _ENCODING.encode(content)
    if len(tokens) <= ENRICHMENT_TRUNCATION_MAX_TOKENS:
        return content
    beginning = _ENCODING.decode(tokens[:2500])
    ending = _ENCODING.decode(tokens[-500:])
    return f"{beginning}\n\n[... truncated ...]\n\n{ending}"


def truncate_content_for_call1(
    source: str,
    title: str,
    content_raw: str,
    *,
    entry_type_hint: str | None = None,
) -> str:
    """Apply per-source truncation strategy, then clamp to the 4k token ceiling."""
    _ = title  # reserved for future source-specific heuristics
    source_norm = source.lower().strip()

    if source_norm in _PAPER_SOURCES:
        candidate = _paper_strategy(content_raw)
    elif source_norm == "github":
        candidate = _github_strategy(content_raw)
    elif source_norm == "huggingface" and entry_type_hint == "model":
        candidate = _huggingface_model_strategy(content_raw)
    elif source_norm == "huggingface" or source_norm in _ARTICLE_SOURCES:
        candidate = _beginning_end_strategy(content_raw)
    else:
        candidate = _beginning_end_strategy(content_raw)

    return _clamp_to_ceiling(candidate)
