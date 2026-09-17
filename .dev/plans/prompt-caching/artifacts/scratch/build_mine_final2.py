"""Build final content: new HEAD (includes T3's committed test) + T4's own
header/import edit + T4's own test block, where the T4 block text is
extracted verbatim from the live working file (already validated to run
correctly), not retyped."""
import subprocess
from pathlib import Path

head = subprocess.run(
    ["git", "show", "HEAD:tests/test_rubric_assets.py"],
    capture_output=True,
    cwd=".",
).stdout.decode("utf-8")

live = Path("tests/test_rubric_assets.py").read_text(encoding="utf-8")

# Extract T4's own block verbatim from the live file (bounded by known markers).
t4_start_marker = "\n# --- T4: config/prompts/call2_rubric_v1.md"
t2_start_marker = "\n# --- T2: config/prompts/prefilter_rubric_v1.md"
i_start = live.index(t4_start_marker)
i_end = live.index(t2_start_marker)
t4_block = live[i_start:i_end]
t4_block = t4_block.rstrip("\n") + "\n"
print("t4_block length:", len(t4_block))
print("t4_block head:", repr(t4_block[:60]))
print("t4_block tail:", repr(t4_block[-60:]))

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

final = step1.rstrip("\n") + "\n" + "\n" + t4_block

Path(".dev/scratch/prompt-caching/mine_final2.py").write_text(final, encoding="utf-8", newline="\n")
print("wrote mine_final2.py, length", len(final))
