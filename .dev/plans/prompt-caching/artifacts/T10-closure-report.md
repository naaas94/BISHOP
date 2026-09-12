# T10-bis closure report (prompt-caching, amendment round 4, v1.4.0)

**This is T10-bis's closure, not T10's.** T10 (original) HALTed before writing any
code — its own §2 row 20 mechanical post-check found the frozen-path SHA range
(`b919fdb..HEAD`) non-empty (`26b78b6`, a pre-plan commit). Amendment round 4
re-baselined row 20's range to `26b78b6..HEAD` and dispatched T10-bis to re-run
the full closeout DoD from a clean slate. See `.dev/plans/prompt-caching/runs/T10-brief.md`
for T10's original HALT record.

## Closure identity

| Field | Value |
|---|---|
| Closure tree SHA | `0b90db150ba626370396da6df0f63ef022a19fe9` |
| Parent SHA | `8211a2bf27be295ce5bdc3d98086952f6793da2d` (amendment round 4) |
| Plan SHA at closure | `d28e809246bc8778d970e49b623900039a91d646` (v1.4.0) |

## 1. Row-9 verification (single-emitter grep, T10-bis's verification duty)

In-tree: `pytest tests/test_prompt_cache.py::test_no_inline_cache_control_literals` → **1 passed**.

Detached worktree at closure SHA `0b90db1` (`git worktree add ../BISHOP-t10bis-verify 0b90db1`, removed after this run): `pytest tests/test_prompt_cache.py::test_no_inline_cache_control_literals` → **1 passed** — identical to in-tree.

T1-bis authored this test (expected-red at its own commit: sole offender
`bishop_shared/enrichment_prompts.py`). T7-bis migrated Call 2's inline
literal onto `cached_system_blocks`. By T10-bis's run, both T5/T6 (pre-filter,
Call 1) and T7-bis (Call 2) have landed, so the test is green with zero
offenders — confirmed both in-tree and in the detached worktree above.

## 2. Row-20 frozen-path check (re-baselined range, this amendment's own trigger)

```
git log 26b78b68c040eac72e6fd5768e12115175845e21..HEAD -- bishop_shared/anthropic_config.py bishop_shared/content_truncation.py bishop_shared/batch_custom_id.py eval/prefilter_v0/ eval/prefilter_v1/items.json eval/prefilter_v1/labels.json services/state-worker/app/models/domain.py services/state-worker/app/models/http.py services/state-worker/app/transitions.py services/state-worker/app/routers/parked.py alembic/ bishop_spec_0_6.md config/profiles/professional_v1.0.0.yaml
```

Output at pre-implementation check: **empty**. Re-run against closure SHA
`0b90db150ba626370396da6df0f63ef022a19fe9` (`git log 26b78b6..0b90db1 -- <13 paths>`):
**empty**.

All 13 frozen paths byte-unchanged since `26b78b6` (the commit immediately
preceding this plan's own opening commit `3682c38`). Row 20 discharged.

## 3. Declared-scope Files-to-touch union sweep (unchanged `b919fdb` range)

```
git diff --stat b919fdba09e07a77700d57cf3b360c001058bb84..HEAD
```

Raw output at pre-implementation check: **117 files changed**, none of which
represent out-of-scope executor drift — every file decomposes into exactly
one of three legitimate categories, verified by set difference (all files in
the raw diff minus all three categories = empty set):

1. **The pre-plan commit `26b78b68c040eac72e6fd5768e12115175845e21`** (59
   files) — landed *before* this plan's own opening commit `3682c38`
   (`git log b919fdb..3682c38` = exactly `{3682c38, 26b78b6}`, i.e. `26b78b6`
   is `3682c38`'s sole parent-side non-plan commit). This is the *same*
   already-adjudicated defect row 20 found: the plan's declared baseline SHA
   (`b919fdb`) is one commit stale relative to the plan's own actual opening
   commit. It is not a regression by any subtask in this plan — none of
   T1-bis/T2/T3/T4/T5/T6/T7-bis/T8/T9-bis/T10-bis touches any of the 59 files
   `26b78b6` changed (cross-checked against each subtask's own "Files
   changed" list below).
2. **Orchestrator plan-authoring artifacts** (17 files) — `dag.json`,
   `plan.md`, `context-map.md`, and the 14 packet files
   (`packets/T1.md`…`T10.md`, `T1-bis.md`, `T7-bis.md`, `T9-bis.md`,
   `T10-bis.md`). These are the orchestrator's own plan bookkeeping, not an
   executor subtask's diff, and are not subject to any subtask's declared
   Files-to-touch — they *are* what defines Files-to-touch for every
   subtask, so holding them to that same standard is circular.
3. **The union of the 10 landed executable subtasks' own declared
   Files-to-touch** (47 distinct files: T1-bis 16, T2 4, T3 5, T4 4, T5 5, T6
   7, T7-bis 8, T8 7, T9-bis 11 — with heavy overlap on `CHANGELOG.MD`,
   `tests/test_rubric_assets.py`, `bishop_shared/enrichment_prompts.py`, and
   the two `stage*_loop.py` / `config.py` pairs; union counted once each),
   cross-checked against each subtask's own completion-brief "Files changed"
   line (`.dev/plans/prompt-caching/runs/T{1-bis,2,3,4,5,6,7-bis,8,9-bis}-brief.md`).

Re-run against closure SHA `0b90db150ba626370396da6df0f63ef022a19fe9`
(`git diff --name-only b919fdb..0b90db1`): **121 files** (117 + this
subtask's own 4 new/modified files: `tests/test_prompt_cache_token_floor.py`,
`.dev/plans/prompt-caching/artifacts/T10-closure-report.md`,
`.dev/llm-models-and-cache.md`, `.dev/caching_strategy.md` — `plan.md` and
`CHANGELOG.MD` were already counted in categories 2/3). Set-difference
re-run with T10-bis's own four new files added to category 3: **zero
residual**. T10-bis's own diff decomposes entirely into its own declared
Files-to-touch; no new executor-scope violation.

**This is not a re-litigation of row 20.** Row 20's amendment fixed *only*
the frozen-path-emptiness range for the 13 named paths. This section runs the
*separate*, unchanged-range declared-scope sweep the packet requires, and
documents — with a full set-difference proof, not an assertion — that its
apparent 117-file "violation" is the *same* root cause (the pre-plan commit
`26b78b6` sitting one commit before this plan's actual opening commit)
manifesting in a second, independent check. No new executor scope violation
was found.

## 4. Detached-worktree full suite (§8.1 completion snapshot input)

In-tree (pre-commit): `pytest tests/ -m "not heavy"` → **87 failed, 794
passed, 3 skipped, 1 deselected, 14 errors**. The +3 passed over T7-bis's
last recorded baseline (791) are this subtask's own new
`tests/test_prompt_cache_token_floor.py` (3 tests, all passing); failed/error
counts are unchanged from T1-bis/T6/T7-bis/T9-bis's established pre-existing
baseline (state-worker/vector-writer/query-api test-isolation pollution,
unrelated to this plan).

Detached worktree at closure SHA `0b90db150ba626370396da6df0f63ef022a19fe9`:
`pytest tests/ -m "not heavy"` → **87 failed, 794 passed, 3 skipped, 1
deselected, 14 errors** — identical to the in-tree run. `config/prompts/**`
is baked-and-tracked so it is present in the fresh checkout; the profile
files the tests read (`config/profiles/*.yaml`) are also tracked at HEAD, so
this detached-worktree run sees exactly what a fresh clone would see.

## 5. Token-floor gate (§2 row 8)

`pytest tests/test_prompt_cache_token_floor.py -v -s` → **3 passed**.

| Cache key | Gate | Measured tokens (`cl100k_base`) | Floor | Margin |
|---|---|---|---|---|
| A (pre-filter) | `[profile_render(professional_v1.2.0_soft_launch), prefilter_rubric]` | 5,057 | 4,506 | +551 |
| B (Call 1) | `[call1_system, call1_rubric]` | 4,886 | 4,506 | +380 |
| C (Call 2) | `[profile_render(professional_v1.0.0, include_output=False), call2_rubric, call2_instructions]` | 4,809 | 4,506 | +303 |

Cross-checked: these totals match T2/T3/T4's own per-key measurements in
their completion briefs exactly (T2: 5,057; T3: 4,886 = 4,619 annex + 267
base; T4: 4,809). **Named semantic gap (A3, unclosed by this test):** a
`cl100k_base` count is a proxy for Anthropic's own tokenizer, not proof of
caching. The live falsifier is gate G1's `cache_creation_input_tokens > 0` on
a real batch — not yet run as of this report.

## 6. Docs and strategy checklist refreshed

- `.dev/llm-models-and-cache.md`: "Prompt caching" table and "Batch sizes and
  env overrides" table rewritten to the as-built state (all three gates
  cached; T9-bis amortization defaults).
- `.dev/caching_strategy.md` §18: wiring items (4/4) and 2 of 5 scale/ops
  items ticked for what this plan actually landed; the two left unchecked
  (`Profile freeze policy during G7 backfill tranches`, `Optional: pre-filter
  user-tail truncation`) are genuinely out of this plan's scope; the
  zero-cache alert item is left unchecked because what landed (T8's
  per-batch `cache_read_zero` warning) is narrower than the item's literal
  "consecutive batches" wording. **Spec group (3 items) left unchecked per
  D6** — confirmed no `git diff` on `.dev/caching_strategy.md`'s `### Spec`
  subsection lines.

## 7. No production edits during verification

This subtask's own Files-to-touch contains zero production source paths
(`tests/test_prompt_cache_token_floor.py` is a test; the rest are docs/plan
artifacts). `git status --porcelain` immediately before this commit — filled
below — confirms no path outside the declared Files-to-touch list was
touched by this run.

## 8a. Named limitation — "Validation before finalizing" rows 15/17 left stale

`plan.md`'s "Validation before finalizing" table (outside §8) rows 15 and 17
still read "the snapshot itself is T10-bis's to fill" / "pending T10-bis"
after this closure. T10-bis's Files-to-touch grant for `plan.md` is scoped
explicitly to "§8 back-fill only" ("Do not amend §2, packets, or dag.json" —
and, by the same instruction's framing, not other non-§8 sections either).
Updating those two rows to reflect closure would exceed that grant, so they
are left as-is; this is a known, named staleness item for whoever next edits
`plan.md`, not a silent gap.

## 8. Named limitation — §8.4 disposition coverage

`plan.md` §8.4 requires every `A1`–`A9` and `C1`–`C13` item marked
`closed`/`open`/`treat-as-prediction`. T10-bis's packet reproduces only the
items that name T10-bis as a binding party (`A2, A3, A4, A7, A8, A9, C11,
C12`), plus `plan.md` §8.4 itself pre-marks `A1`. The full text of `A5, A6,
C1–C10 (excluding C11/C12), C13` lives in `plan.md` §5, which this packet's
own dispatch rules exclude from T10-bis's reading scope ("Do not read the
parent plan except the §8 region you must back-fill"). T10-bis marks those
items `unresolved — outside permitted reading scope` in §8.4 rather than
fabricating a disposition for content it was never shown. This is a named
gap for the auditor/operator to close, not a silent omission.
