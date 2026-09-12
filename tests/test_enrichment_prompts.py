"""Unit tests for bishop_shared.enrichment_prompts (M5 T1; blocks: prompt-caching T6)."""

from __future__ import annotations

from pathlib import Path

import pytest

import bishop_shared.rubric_assets as rubric_assets_mod
from bishop_shared.enrichment_prompts import (
    build_call1_system_prompt,
    build_call1_user_message,
    build_call2_system_prompt,
    build_call2_user_message,
)
from bishop_shared.prompt_cache import CACHE_TTL
from bishop_shared.tag_taxonomy import TAG_TAXONOMY_ORDERED

_REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def _patch_rubric_container_dir(monkeypatch: pytest.MonkeyPatch) -> None:
    """build_call1_system_prompt resolves the call1 rubric via the container
    path (/app/config/prompts, §2 row 16 — image-baked, no override param on
    this builder). Point the container dir at the real repo asset so this
    test runs outside the Docker image."""
    monkeypatch.setattr(
        rubric_assets_mod, "PROMPTS_CONTAINER_DIR", _REPO_ROOT / "config" / "prompts"
    )


def test_call1_includes_taxonomy() -> None:
    """Re-pointed at the specific schema block (blocks[0]) per T6's kill
    criterion — build_call1_system_prompt now returns a block list, not a
    plain string, so `tag in prompt` would silently check list membership
    against dicts instead of substring-in-string."""
    blocks = build_call1_system_prompt()
    schema_text = blocks[0]["text"]
    assert isinstance(schema_text, str)
    for tag in TAG_TAXONOMY_ORDERED:
        assert tag in schema_text
    assert "challenge_hooks" in schema_text
    assert "entry_type" in schema_text


def test_call1_user_message_shape() -> None:
    message = build_call1_user_message("My Title", "truncated body")
    assert message.startswith("Title: My Title\nContent: truncated body")


def test_call1_system_is_two_block_list_with_rubric_annex_last() -> None:
    """Row 10 block order for cache key B: [call1_system, call1_rubric]."""
    blocks = build_call1_system_prompt()
    assert isinstance(blocks, list)
    assert len(blocks) == 2
    for block in blocks:
        assert block["type"] == "text"
    # The rubric annex (last block) is loaded from the real committed asset —
    # assert a heading that only exists in that annex, not in the schema text.
    assert "Call 1 Extraction Rubric" in blocks[1]["text"]
    assert "Call 1 Extraction Rubric" not in blocks[0]["text"]


def test_call1_system_single_cache_control_breakpoint_on_last_block() -> None:
    """Row 10 falsifier: exactly one cache_control, and it is on the last block —
    a count-only assertion would pass even with the breakpoint on block 0."""
    blocks = build_call1_system_prompt()
    cache_control_indices = [i for i, b in enumerate(blocks) if "cache_control" in b]
    assert cache_control_indices == [len(blocks) - 1]
    assert blocks[-1]["cache_control"] == {"type": "ephemeral", "ttl": CACHE_TTL}


def test_call1_system_prompt_fresh_blocks_each_call() -> None:
    """No aliasing across calls — cached_system_blocks contract (row 1d)."""
    first = build_call1_system_prompt()
    second = build_call1_system_prompt()
    assert first == second
    assert first is not second
    assert first[-1] is not second[-1]


def test_call2_system_has_cache_control() -> None:
    blocks = build_call2_system_prompt("profile text here")
    assert isinstance(blocks, list)
    assert blocks[0]["cache_control"] == {"type": "ephemeral"}
    assert blocks[0]["text"] == "profile text here"
    assert blocks[0]["type"] == "text"


def test_call2_user_message_shape() -> None:
    message = build_call2_user_message("Title", "Summary text")
    assert message == "Title: Title\nSummary: Summary text"
