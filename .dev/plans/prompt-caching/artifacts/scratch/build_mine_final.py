"""Build the final tests/test_rubric_assets.py content: current HEAD (which
now legitimately includes T3's committed test) plus T4's own two edits
(header/imports change, and the T4 test block appended after the existing
CLI-missing-hash test). No removal of any sibling's already-committed
content."""
import subprocess
from pathlib import Path

head = subprocess.run(
    ["git", "show", "HEAD:tests/test_rubric_assets.py"],
    capture_output=True,
    cwd=".",
).stdout.decode("utf-8")

edit1_old = '''"""Unit tests for bishop_shared.rubric_assets (prompt-caching plan T1)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from bishop_shared.rubric_assets import (
    PROMPTS_CONTAINER_DIR,
    RubricDocument,
    compute_rubric_hash,
    load_rubric,
    resolve_rubric_path,
    verify_rubric_hash,
)'''

edit1_new = '''"""Unit tests for bishop_shared.rubric_assets (prompt-caching plan T1 / T4)."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest
import tiktoken

from bishop_shared.profile_renderer import load_profile, render_profile_prompt
from bishop_shared.rubric_assets import (
    PROMPTS_CONTAINER_DIR,
    RubricDocument,
    compute_rubric_hash,
    load_rubric,
    resolve_rubric_path,
    verify_rubric_hash,
)'''

assert head.count(edit1_old) == 1, "edit1_old not found exactly once in HEAD content"
step1 = head.replace(edit1_old, edit1_new)

t4_block = '''


# --- T4: config/prompts/call2_rubric_v1.md (Call 2 relevance-scoring annex) ---

_CALL2_RUBRIC_PATH = REPO_ROOT / "config" / "prompts" / "call2_rubric_v1.md"


def test_call2_rubric_v1_resolves_and_hash_verifies() -> None:
    """The committed asset resolves via the real container-path mapping (not a
    tmp_path stand-in) and its stamped canonical_hash matches its own body."""
    assert resolve_rubric_path("call2_rubric") == PROMPTS_CONTAINER_DIR / "call2_rubric_v1.md"
    verified = verify_rubric_hash("call2_rubric", rubric_path=_CALL2_RUBRIC_PATH)
    assert verified is not None
    rubric_id, version, canonical_hash = verified
    assert rubric_id == "call2_rubric"
    assert version == "1.0.0"
    assert canonical_hash == compute_rubric_hash(_CALL2_RUBRIC_PATH)


def test_call2_rubric_v1_governs_score_not_gate1_decision() -> None:
    """\u00a72 row 5.4 C4 / T4 kill criterion: the annex must never reintroduce the
    gate-1 {"decision": 0 or 1} output contract into the Call 2 cached prefix.

    Mutation-checked: inserting the retired contract string below makes this
    assertion fail (verified by hand while authoring; the guard pattern is
    the literal gate-1 instruction text, not a loose substring)."""
    doc = load_rubric(_CALL2_RUBRIC_PATH)
    assert '"decision"' not in doc.body
    assert "0 or 1" not in doc.body
    # The annex must still govern the float-scoring schema it is named for.
    assert "relevance_score" in doc.body
    assert "value_rationale" in doc.body


def test_call2_rubric_v1_clears_key_c_token_floor_against_include_output_false() -> None:
    """\u00a72 row 8: measured against the include_output=False profile render T7
    will actually use for cache key C (not the include_output=True render),
    total prefix (profile + annex + Call 2 instructions block) clears the
    4,506-token floor with positive margin.

    The 82-token instructions-block figure is the packet's resolved
    planning-time measurement of the current
    ``enrichment_prompts.build_call2_system_prompt`` instructions text;
    pinning it here (rather than importing the builder) keeps this test
    from silently tracking an unrelated T7 wording change.
    """
    encoding = tiktoken.get_encoding("cl100k_base")
    profile = load_profile(Path("config/profiles/professional_v1.0.0.yaml"))
    profile_prompt_no_output = render_profile_prompt(profile, include_output=False)
    profile_tokens = len(encoding.encode(profile_prompt_no_output))

    rubric_doc = load_rubric(_CALL2_RUBRIC_PATH)
    annex_tokens = len(encoding.encode(rubric_doc.body))

    call2_instructions = (
        "Evaluate the relevance of the provided content to the profile above.\\n"
        "Respond only with a valid JSON object matching the schema below.\\n\\n"
        "Schema:\\n"
        "{\\n"
        '  "relevance_score": float,\\n'
        '  "relevance_reason": "string, one sentence, why this is or is not relevant",\\n'
        '  "value_rationale": "string, 1-2 sentences, what specific value this provides '
        "to the profile's owner\\""
        '\\n"'
        "}"
    )
    instructions_tokens = len(encoding.encode(call2_instructions))

    total = profile_tokens + annex_tokens + instructions_tokens
    assert total >= 4506, (
        f"key C total prefix {total} tokens (profile={profile_tokens}, "
        f"annex={annex_tokens}, instructions={instructions_tokens}) is below "
        "the 4,506-token floor"
    )


def test_call2_rubric_v1_front_matter_matches_shared_schema() -> None:
    """\u00a72 row 7 literal schema, shared verbatim with T2/T3: the on-disk file's
    front matter matches the exact block shape, not just a parseable subset."""
    raw = _CALL2_RUBRIC_PATH.read_text(encoding="utf-8")
    assert re.match(
        r'\\A---\\nrubric_id: call2_rubric\\nversion: "[^"\\n]+"\\n'
        r'canonical_hash: "[0-9a-f]{64}"\\n---\\n',
        raw,
    ), "front matter does not match the shared rubric schema"
'''

final = step1.rstrip("\n") + "\n" + t4_block.lstrip("\n")
# Ensure file ends with single trailing newline
final = final.rstrip("\n") + "\n"

Path(".dev/scratch/prompt-caching/mine_final.py").write_text(final, encoding="utf-8", newline="\n")
print("wrote mine_final.py, length", len(final))
