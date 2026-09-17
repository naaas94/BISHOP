"""Extract T4-only content directly from the live file's own section markers,
avoiding hand-transcription. T3's block sits between two known markers; T2's
block is appended after T4's own '# --- T4:' ... '# --- T2:' delimited region."""
from pathlib import Path

current = Path("tests/test_rubric_assets.py").read_text(encoding="utf-8")

t3_start = "\ndef test_call1_rubric_v1_asset_exists_and_verifies() -> None:"
t3_end = "\ndef test_rubric_hash_cli_exits_nonzero_when_canonical_hash_line_missing(tmp_path: Path) -> None:"
t4_marker = "\n# --- T4: config/prompts/call2_rubric_v1.md"
t2_marker = "\n# --- T2: config/prompts/prefilter_rubric_v1.md"

i_t3_start = current.index(t3_start)
i_t3_end = current.index(t3_end)
i_t4 = current.index(t4_marker)
i_t2 = current.index(t2_marker)

assert i_t3_start < i_t3_end < i_t4 < i_t2, "marker ordering assumption violated"

part_a = current[:i_t3_start]          # header through end of test_one_character_body_edit_changes_hash
part_b = current[i_t3_end:i_t4]        # test_rubric_hash_cli_exits_nonzero_... function, unchanged
part_c = current[i_t4:i_t2]            # my own T4 block, verbatim from the live file

mine_only = part_a + "\n" + part_b + part_c

Path(".dev/scratch/prompt-caching/mine_only_v3.py").write_text(mine_only, encoding="utf-8", newline="\n")
print("wrote mine_only_v3.py, length", len(mine_only))
print("--- tail 400 chars ---")
print(mine_only[-400:])
