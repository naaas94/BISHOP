"""§2 row 8 — token-floor gate (prompt-caching plan T10-bis closure).

One point-literal assertion per cache key (A pre-filter, B Call 1, C Call 2)
that the *assembled* system-block prefix — the same blocks the real gate
wires onto ``params["system"]`` — clears Claude Haiku 4.5's 4,096-token
cacheable-prefix minimum with the plan's 10% margin (4,096 * 1.10 = 4505.6,
rounded up to 4,506). Measured on the total prefix (profile/schema block +
rubric annex, plus Call 2's trailing instructions block), not the annex in
isolation, so the contract cannot go stale when a profile render changes
(§2 row 8). This is a ``cl100k_base`` proxy check (A3); the live falsifier
is G1's ``cache_creation_input_tokens > 0``.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import tiktoken

import bishop_shared.rubric_assets as rubric_assets_mod
from bishop_shared.enrichment_prompts import build_call1_system_prompt, build_call2_system_prompt
from bishop_shared.profile_renderer import load_profile, render_profile_prompt
from bishop_shared.rubric_assets import load_rubric

REPO_ROOT = Path(__file__).resolve().parent.parent

# 4,096 (Claude Haiku 4.5 minimum cacheable prefix) * 1.10 margin, per §2 row 8.
_TOKEN_FLOOR = 4506

_encoding = tiktoken.get_encoding("cl100k_base")


@pytest.fixture(autouse=True)
def _patch_rubric_container_dir(monkeypatch: pytest.MonkeyPatch) -> None:
    """build_call1_system_prompt / build_call2_system_prompt resolve rubric
    assets via the image-baked container path (/app/config/prompts, §2 row
    16). Point the container dir at the real repo asset so this test runs
    outside the Docker image — same fixture as tests/test_enrichment_prompts.py."""
    monkeypatch.setattr(rubric_assets_mod, "PROMPTS_CONTAINER_DIR", REPO_ROOT / "config" / "prompts")


def _assembled_prefix_tokens(blocks: list[dict[str, object]]) -> int:
    """Token count of the concatenated block texts — the actual bytes that
    get cached as one span, not the annex alone."""
    return sum(len(_encoding.encode(str(block["text"]))) for block in blocks)


def test_cache_key_a_prefilter_clears_token_floor() -> None:
    """Key A: [profile_render(professional_v1.2.0_soft_launch), prefilter_rubric]."""
    profile = load_profile(Path("config/profiles/professional_v1.2.0_soft_launch.yaml"))
    profile_prompt = render_profile_prompt(profile)
    rubric_body = load_rubric(REPO_ROOT / "config" / "prompts" / "prefilter_rubric_v1.md").body

    from bishop_shared.prompt_cache import cached_system_blocks

    blocks = cached_system_blocks(profile_prompt, rubric_body)
    measured = _assembled_prefix_tokens(blocks)
    margin = measured - _TOKEN_FLOOR
    print(f"cache key A measured={measured} floor={_TOKEN_FLOOR} margin={margin}")

    assert measured >= _TOKEN_FLOOR


def test_cache_key_b_call1_clears_token_floor() -> None:
    """Key B: [call1_system(schema/taxonomy), call1_rubric] via build_call1_system_prompt()."""
    blocks = build_call1_system_prompt()
    measured = _assembled_prefix_tokens(blocks)
    margin = measured - _TOKEN_FLOOR
    print(f"cache key B measured={measured} floor={_TOKEN_FLOOR} margin={margin}")

    assert measured >= _TOKEN_FLOOR


def test_cache_key_c_call2_clears_token_floor() -> None:
    """Key C: [profile_render(professional_v1.0.0, include_output=False),
    call2_rubric, call2_instructions] via build_call2_system_prompt()."""
    profile = load_profile(Path("config/profiles/professional_v1.0.0.yaml"))
    profile_prompt = render_profile_prompt(profile, include_output=False)
    rubric_body = load_rubric(REPO_ROOT / "config" / "prompts" / "call2_rubric_v1.md").body

    blocks = build_call2_system_prompt(profile_prompt, rubric_body)
    measured = _assembled_prefix_tokens(blocks)
    margin = measured - _TOKEN_FLOOR
    print(f"cache key C measured={measured} floor={_TOKEN_FLOOR} margin={margin}")

    assert measured >= _TOKEN_FLOOR
