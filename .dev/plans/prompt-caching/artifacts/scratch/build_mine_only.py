import subprocess
from pathlib import Path

base = subprocess.run(
    ["git", "show", "HEAD:tests/test_rubric_assets.py"],
    capture_output=True,
    cwd=".",
).stdout.decode("utf-8")

current = Path("tests/test_rubric_assets.py").read_text(encoding="utf-8")

t3_marker_start = '\ndef test_call1_rubric_v1_asset_exists_and_verifies() -> None:'
t3_marker_end = '\ndef test_rubric_hash_cli_exits_nonzero_when_canonical_hash_line_missing(tmp_path: Path) -> None:'

start_idx = current.index(t3_marker_start)
end_idx = current.index(t3_marker_end)
t3_block = current[start_idx:end_idx]
print("T3 block length:", len(t3_block))
print("T3 block starts with:", t3_block[:80])
print("T3 block ends with:", t3_block[-80:])

# mine-only = current with T3's block removed, but the two blank-line separator preserved.
mine_only = current[:start_idx] + "\n" + current[end_idx + 1 :]

Path(".dev/scratch/prompt-caching/mine_only.py").write_text(mine_only, encoding="utf-8", newline="\n")
print("wrote mine_only.py, length", len(mine_only))
