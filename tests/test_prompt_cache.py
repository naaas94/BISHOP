"""Unit tests for bishop_shared.prompt_cache (prompt-caching plan T1)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

from bishop_shared.prompt_cache import CACHE_TTL, cached_system_blocks

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_n_inputs_produce_n_blocks() -> None:
    blocks = cached_system_blocks("a", "b", "c")
    assert len(blocks) == 3
    assert [block["text"] for block in blocks] == ["a", "b", "c"]


def test_cache_control_on_last_block_only() -> None:
    blocks = cached_system_blocks("first", "second", "third")
    assert "cache_control" not in blocks[0]
    assert "cache_control" not in blocks[1]
    assert "cache_control" in blocks[2]


def test_cache_control_shape_exact() -> None:
    blocks = cached_system_blocks("only")
    assert blocks[-1]["cache_control"] == {"type": "ephemeral", "ttl": "1h"}
    assert CACHE_TTL == "1h"


def test_two_calls_are_equal_but_not_aliased() -> None:
    blocks1 = cached_system_blocks("x", "y")
    blocks2 = cached_system_blocks("x", "y")
    assert blocks1 == blocks2
    assert blocks1 is not blocks2
    for b1, b2 in zip(blocks1, blocks2):
        assert b1 is not b2
    assert blocks1[-1]["cache_control"] is not blocks2[-1]["cache_control"]

    # Mutating one call's blocks must not affect the other — proves no
    # shared/module-level dict backs either the block or its cache_control.
    blocks1[-1]["cache_control"]["ttl"] = "5m"  # type: ignore[index]
    assert blocks2[-1]["cache_control"] == {"type": "ephemeral", "ttl": "1h"}


def test_empty_input_raises_value_error() -> None:
    with pytest.raises(ValueError, match="at least one"):
        cached_system_blocks()


def test_sdk_supports_1h_ttl() -> None:
    """Row 1a falsifier: an anthropic<0.100 install rejects or silently drops
    ttl="1h", so all three cache keys would write 5-minute entries repeatedly
    and never realize the 1h benefit (A1)."""
    from anthropic.types.cache_control_ephemeral_param import CacheControlEphemeralParam

    assert "ttl" in CacheControlEphemeralParam.__annotations__


_CACHE_CONTROL_LITERAL = re.compile(r'"cache_control"\s*:|\'cache_control\'\s*:')


def test_no_inline_cache_control_literals() -> None:
    """Row 9: bishop_shared/prompt_cache.py is the single emitter — no other
    module under bishop_shared/** or services/** may construct a
    cache_control dict literal directly."""
    search_roots = [REPO_ROOT / "bishop_shared", REPO_ROOT / "services"]
    offenders: list[str] = []
    for root in search_roots:
        for path in root.rglob("*.py"):
            if path.resolve() == (REPO_ROOT / "bishop_shared" / "prompt_cache.py").resolve():
                continue
            text = path.read_text(encoding="utf-8")
            if _CACHE_CONTROL_LITERAL.search(text):
                offenders.append(str(path.relative_to(REPO_ROOT)))
    assert offenders == []


def test_no_prompts_bind_mount() -> None:
    """Row 16: config/prompts is image-baked only. A compose mount targeting
    /app/config/prompts would mask the baked rubrics with an empty host dir
    and abort all three gates with no repo-visible cause (A7)."""
    compose_path = REPO_ROOT / "docker-compose.yml"
    compose = yaml.safe_load(compose_path.read_text(encoding="utf-8"))
    offenders: list[str] = []
    for service_name, service in compose.get("services", {}).items():
        for volume in service.get("volumes", []) or []:
            if isinstance(volume, str):
                target = volume.split(":")[1] if ":" in volume else volume
            elif isinstance(volume, dict):
                target = volume.get("target", "")
            else:
                continue
            if target.rstrip("/") == "/app/config/prompts":
                offenders.append(service_name)
    assert offenders == []
