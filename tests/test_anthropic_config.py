"""Unit tests for bishop_shared.anthropic_config (M3 T1)."""

from __future__ import annotations

import pytest

from bishop_shared.anthropic_config import (
    ANTHROPIC_MODEL_ENRICHMENT,
    ANTHROPIC_MODEL_PREFILTER,
    get_anthropic_api_key,
)


def test_prefilter_model_string_pinned() -> None:
    assert ANTHROPIC_MODEL_PREFILTER == "claude-haiku-4-5-20251001"


def test_enrichment_model_alias_matches_prefilter() -> None:
    assert ANTHROPIC_MODEL_ENRICHMENT == ANTHROPIC_MODEL_PREFILTER


def test_api_key_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert get_anthropic_api_key() is None

    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-key")
    assert get_anthropic_api_key() == "sk-test-key"
