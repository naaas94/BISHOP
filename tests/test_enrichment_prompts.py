"""Unit tests for bishop_shared.enrichment_prompts (M5 T1)."""

from __future__ import annotations

from bishop_shared.enrichment_prompts import (
    build_call1_system_prompt,
    build_call1_user_message,
    build_call2_system_prompt,
    build_call2_user_message,
)
from bishop_shared.tag_taxonomy import TAG_TAXONOMY_ORDERED


def test_call1_includes_taxonomy() -> None:
    prompt = build_call1_system_prompt()
    for tag in TAG_TAXONOMY_ORDERED:
        assert tag in prompt
    assert "challenge_hooks" in prompt
    assert "entry_type" in prompt


def test_call1_user_message_shape() -> None:
    message = build_call1_user_message("My Title", "truncated body")
    assert message.startswith("Title: My Title\nContent: truncated body")


def test_call2_system_has_cache_control() -> None:
    blocks = build_call2_system_prompt("profile text here")
    assert isinstance(blocks, list)
    assert blocks[0]["cache_control"] == {"type": "ephemeral"}
    assert blocks[0]["text"] == "profile text here"
    assert blocks[0]["type"] == "text"


def test_call2_user_message_shape() -> None:
    message = build_call2_user_message("Title", "Summary text")
    assert message == "Title: Title\nSummary: Summary text"
