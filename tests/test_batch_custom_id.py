"""Unit tests for bishop_shared.batch_custom_id."""

from __future__ import annotations

import re

import pytest

from bishop_shared.batch_custom_id import (
    batch_custom_id_to_source_id,
    source_id_to_batch_custom_id,
)

_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


@pytest.mark.parametrize(
    "source_id",
    [
        "arxiv:2406.00001",
        "github:torvalds/linux",
        "semantic_scholar:abc123",
        "huggingface:paper/repo",
    ],
)
def test_source_id_roundtrip(source_id: str) -> None:
    custom_id = source_id_to_batch_custom_id(source_id)
    assert _PATTERN.fullmatch(custom_id)
    assert batch_custom_id_to_source_id(custom_id) == source_id


def test_arxiv_custom_id_is_not_canonical_source_id() -> None:
    custom_id = source_id_to_batch_custom_id("arxiv:2406.00001")
    assert custom_id != "arxiv:2406.00001"
    assert ":" not in custom_id
    assert "." not in custom_id
