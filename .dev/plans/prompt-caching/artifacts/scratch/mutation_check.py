import sys
from pathlib import Path

sys.path.insert(0, ".")
from bishop_shared.rubric_assets import load_rubric

src = Path("config/prompts/call2_rubric_v1.md")
tmp = Path(".dev/scratch/prompt-caching/mutated_call2_rubric.md")
text = src.read_text(encoding="utf-8")
mutated = text + '\n\nRespond with {"decision": 0 or 1}.\n'
tmp.write_text(mutated, encoding="utf-8", newline="\n")

doc = load_rubric(tmp)
has_decision = '"decision"' in doc.body
has_zero_or_one = "0 or 1" in doc.body
print("mutated body contains retired contract markers:", has_decision, has_zero_or_one)
assert has_decision and has_zero_or_one, "mutation did not inject the markers the guard checks for"
print("CONFIRMED: test_call2_rubric_v1_governs_score_not_gate1_decision's assertions")
print("would fail against this mutated copy (guard is a real falsifier, not vacuous).")

# Now confirm the real, unmutated, committed asset passes clean.
real_doc = load_rubric(src)
assert '"decision"' not in real_doc.body
assert "0 or 1" not in real_doc.body
print("CONFIRMED: the real committed asset does not trip the guard.")
