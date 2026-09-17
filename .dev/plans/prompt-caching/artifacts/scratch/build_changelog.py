import subprocess
from pathlib import Path

base = subprocess.run(
    ["git", "show", "HEAD:CHANGELOG.MD"],
    capture_output=True,
    cwd=".",
).stdout.decode("utf-8")

header = "## prompt-caching — 2026-09-12\n"
assert base.count(header) == 1

bullet = (
    "- T4 (author `call2_rubric_v1.md`, cache key C): Added "
    "`config/prompts/call2_rubric_v1.md` — a stamped, hash-verified rubric "
    "annex governing enrichment Call 2's continuous `relevance_score` float "
    "(0.0-1.0), not gate 1's binary decision: five score bands with worked "
    "criteria, anchor-weight scoring guidance, fifteen worked examples "
    "spanning core-exemplar through excluded-class-missed-at-gate-1, "
    "`value_rationale`/`relevance_reason` field-distinction guidance, and a "
    "common-miscalibration-traps list (hype inflation, author-prestige and "
    "length-as-depth substitution, binary bleed-through). The annex never "
    "reintroduces a `{\"decision\": 0 or 1}` output contract (guarded by a "
    "dedicated test). Measured against the `include_output=False` profile "
    "render T7 will actually use for key C (348 tokens), not the "
    "`include_output=True` render (383 tokens) — using the wrong variant "
    "would have understated the true margin. Key C's total prefix (profile "
    "348 + annex 4,379 + Call 2 instructions 82 = 4,809 measured "
    "`cl100k_base` tokens) clears the 4,506-token floor with a 303-token "
    "margin, real content only, no padding. Extended "
    "`tests/test_rubric_assets.py` with four tests against the real "
    "committed asset: hash round-trip, front-matter schema, the mutation-"
    "checked gate-1-decision-contract guard, and the key-C token-floor "
    "claim. See `.dev/decision-logs/prompt-caching/T4-call2-rubric.md`.\n"
    "\n"
)

new_section = header + "\n" + bullet
final = base.replace(header + "\n", new_section, 1)

Path(".dev/scratch/prompt-caching/changelog_mine_only.md").write_text(
    final, encoding="utf-8", newline="\n"
)
print("wrote changelog_mine_only.md, length", len(final))
