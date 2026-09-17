## Completion Brief

- **Subtask ID · Status:** T10-bis · **complete**

- **Files changed:** `tests/test_prompt_cache_token_floor.py` (new), `.dev/llm-models-and-cache.md`, `.dev/caching_strategy.md`, `.dev/plans/prompt-caching/plan.md` (§8 back-fill only), `.dev/plans/prompt-caching/artifacts/T10-closure-report.md` (new), `CHANGELOG.MD`. `tests/test_prompt_cache.py` verified only, not edited. All six are an exact match to the declared Files-to-touch (`git diff --stat` from parent `8211a2b` to `HEAD` confirms no other path touched).

- **Tests run + result:** In-tree and in a detached worktree at the closure SHA — identical both ways: `pytest tests/ -m "not heavy"` → 87 failed, 794 passed, 3 skipped, 1 deselected, 14 errors (the +3 over T7-bis's 791 baseline are this subtask's own new token-floor tests; failed/error counts unchanged, pre-existing per T1-bis/T6/T7-bis/T9-bis). `tests/test_prompt_cache.py::test_no_inline_cache_control_literals` (row 9) → 1 passed, both in-tree and in the worktree. `tests/test_prompt_cache.py` + `tests/test_prompt_cache_token_floor.py` full set → 11 passed.

- **Commit SHA:** `370c0cd3a29a39f85904068c0fe5955a7cdb8032` (substantive work) + `21c8e3d` (follow-up fixing a stale SHA self-reference left by the required `--amend`, since a commit can't embed its own final hash — no code/test content changed in the second commit).

- **Changelog entry location:** `CHANGELOG.MD`, `## prompt-caching — 2026-09-12` section, T10-bis bullet appended after T7-bis's.

- **Decision log path:** n/a — tier `standard`, not `architectural`.

- **Kill-criterion evidence:**
 - Detached-worktree full suite: identical to in-tree (above) — did not fire.
 - Row-9 isolated test: green in-tree and in worktree — did not fire.
 - Row-20 frozen-path check (`git log 26b78b6..HEAD` over all 13 paths, re-baselined range): empty, re-confirmed at final HEAD — did not fire.
 - Declared-scope sweep (`git diff --stat b919fdb..HEAD`, unchanged range): raw diff is large (121 files) but decomposes with **zero residual** into three legitimate categories — the pre-plan commit `26b78b6` (same root cause row 20 already found, predates the plan's own opening commit), the orchestrator's own plan-authoring artifacts, and the union of the 10 landed subtasks' own declared Files-to-touch, verified by an explicit PowerShell set-difference, not an assertion — did not fire as a new violation.
 - No production edits during verification: this subtask's Files-to-touch contains zero production source paths; confirmed by `git status --porcelain` showing only the declared six.
 - No strategy §18 spec checkbox ticked: confirmed — only Wiring/Scale-ops boxes edited, `### Spec` subsection untouched.

- **Summary:** T10-bis re-ran T10's full closeout DoD from the row-20 re-baselined range, adding a dedicated token-floor test that measures each gate's real assembled system-block prefix and confirms all three cache keys clear Haiku 4.5's floor with real margin (A: 5,057, B: 4,886, C: 4,809 vs. 4,506). Row 9 and row 16 both re-verified green, and — critically — the declared-scope sweep's alarming 121-file raw diff was shown, via explicit set-difference rather than hand-waving, to be fully explained by the same already-adjudicated pre-plan commit plus orchestrator bookkeeping, so no new §7 amendment was needed. Docs (`.dev/llm-models-and-cache.md`, `.dev/caching_strategy.md`) and `plan.md` §8 (completion snapshot, per-row §2 evidence, §5 disposition, audit remediation cross-link) are back-filled, with one honestly named gap: `A5, A6, C1–C10 (excluding C11/C12), C13` in §8.4 are marked `unresolved — outside T10-bis's permitted reading scope` rather than fabricated, since their defining text lives in `plan.md` §5 and this subtask's dispatch restricted reading to §8. This closes the prompt-caching plan's last executable node ahead of gate G1, which remains an operator-run live verification outside this subtask's scope.
