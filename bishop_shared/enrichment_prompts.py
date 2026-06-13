"""Enrichment Call 1/2 prompt builders (spec Appendix A)."""

from __future__ import annotations

from bishop_shared.tag_taxonomy import TAG_TAXONOMY_ORDERED

_ENTRY_TYPES = (
    "paper",
    "model",
    "dataset",
    "repo",
    "article",
    "spec",
    "idea",
    "benchmark",
    "other",
)


def _format_taxonomy_list() -> str:
    return ", ".join(TAG_TAXONOMY_ORDERED)


def build_call1_system_prompt() -> str:
    """Appendix A Call 1 system prompt with injected taxonomy."""
    taxonomy = _format_taxonomy_list()
    entry_types = "|".join(_ENTRY_TYPES)
    return f"""You are a technical content analyst. Extract structured metadata from the provided content.
Respond only with a valid JSON object matching the schema below. No preamble, no explanation.

Schema:
{{
  "summary": "string, 200-300 characters, dense technical summary",
  "concepts": ["string", ...],
  "tags": ["string", ...],
  "entry_type": "one of: {entry_types}",
  "challenge_hooks": ["string", ...]
}}

Tags: ONLY use tags from this exact list: [{taxonomy}]
Do not invent or use tags outside this list.
Any tags not in the provided list will be stripped by the parser and logged for taxonomy review.

challenge_hooks: 2-4 problem framings this content addresses, written as problems a practitioner would search for.
concepts: 5-8 key technical concepts."""


def build_call1_user_message(title: str, truncated_content: str) -> str:
    return f"Title: {title}\nContent: {truncated_content}"


def build_call2_system_prompt(profile_prompt: str) -> list[dict[str, object]]:
    """Return Anthropic system content blocks with ephemeral cache_control on profile."""
    instructions = (
        "Evaluate the relevance of the provided content to the profile above.\n"
        "Respond only with a valid JSON object matching the schema below.\n\n"
        "Schema:\n"
        "{\n"
        '  "relevance_score": float,\n'
        '  "relevance_reason": "string, one sentence, why this is or is not relevant",\n'
        '  "value_rationale": "string, 1-2 sentences, what specific value this provides '
        "to the profile's owner\"\n"
        "}"
    )
    return [
        {
            "type": "text",
            "text": profile_prompt,
            "cache_control": {"type": "ephemeral"},
        },
        {
            "type": "text",
            "text": instructions,
        },
    ]


def build_call2_user_message(title: str, summary: str) -> str:
    return f"Title: {title}\nSummary: {summary}"
