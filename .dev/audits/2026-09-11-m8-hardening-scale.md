# Audit — m8-hardening-scale

**Audit date:** 2026-09-11 · **Audit document revision: 2** — supersedes revision 1 (2026-09-10) for provenance, findings status, and verdict. Revision 1 remains on disk unmodified as historical record at `.dev/audits/2026-09-10-m8-hardening-scale.md`.
**Auditor skill:** auditor-review v1.0 · **Fan-out policy:** operating-posture v0.4
**Plan audited:** `.dev/plans/m8-hardening-scale/plan.md` v1.5 (`run_status: amended`, "Amendment-complete, audit-pending")
**HEAD at audit:** `9983927a0804fdb8a4e00da5a9cb5aeb39aa051f` — confirmed via `git rev-parse HEAD`. Working tree at audit time carries only doc/scratch dirty paths (`.dev/quality/g6-enrichment-template.md` uncommitted fill, `.dev/audit-*.diff`, `.dev/sqlite.md`, `AGENTS.md`, `thoughts.md`, `.cursor/`) — **no code path is dirty**. This matches plan §8.1's disclosed scope exactly.
**Charter binding:** `.dev/bishop_program_charter.md` v0.1.0 — Milestone M8 (L492–540)

## Audit metadata

- **Re-audit of:** `.dev/audits/2026-09-10-m8-hardening-scale.md` revision 1, verdict `fail`, `audit_status: blocked` on F1 (major), F2 (critical), F3 (major), F4 (major).
- **Context map:** `.dev/plans/m8-hardening-scale/context-map.md`, scout SHA `48098900eb546cbac9fcb22e7f5180536255007e` (unchanged since rev 1), readiness verdict at planning time **CONDITIONAL**.
- **Focus areas chosen (Phase 4):** (1) **Integration seams** (mandatory — C1–C5 + §5.4 tuples), (2) **Regression surface** (this is where rev 1's only critical finding, F2, hid — the exact failure mode the skill's Phase 2 rationale warns about), (3) **Contract compliance / typed-surface admission** (F1, F3, F4 were all typed-surface / gate-completeness / naming-literal gaps — the milestone's actual recurring risk pattern, now the subject of four targeted remediation packets).
- **Operating-posture disclosure:** Phase 0/0.5/2 mechanical reads, greps, and one full-suite run were dispatched to a Composer 2.5-fast subagent (background). This auditor did not block on it and independently ran the equivalent commands directly (`verify-m8.sh` on the live worktree, all eight prior milestone verify scripts, and every test file the audit's own omission-free checklist required that no verify script names) — the same judgment-adjacent posture rev 1 disclosed, for the same reason: reconciling per-service `app`-package collision isolation against a naive `pytest tests/` invocation is interpretive, not purely mechanical. Severity, intent-drift-vs-coverage-gap classification, and the verdict below are entirely this agent's own.
- **Omission-free artifact checklist (re-audit discipline)** — every surface that contributed to rev 1's `fail` was reopened and reviewed this revision:

| Surface | Reviewed |
|---|---|
| `plan.md` v1.5 (full: §0, §1, §2, §3, §4 all subtasks incl. T9–T12/T10-bis, §5, §6, §7, §8.1–8.6) | ✅ |
| Rev-1 audit `.dev/audits/2026-09-10-m8-hardening-scale.md` (full) | ✅ — read in full before Phase 1 |
| Packets T1, T1-bis, T2–T8, T8-bis, T9, T10, T10-bis, T11, T12 | ✅ present-in-HEAD (`git ls-files`); T9/T10-bis/T11/T12 content cross-checked against §4 subtask specs (identical — packets are verbatim extracts) |
| `dag.json` (`plan_version: "1.5"`) | ✅ present-in-HEAD |
| `runs/ledger.md`, `runs/execution-summary.md`, all 13 `runs/*-brief.md` | ✅ present-in-HEAD |
| Decision logs: T1-adapter-foundation, T4-openreview-lesswrong, T5-state-worker-ops, T8-backfill-enable | ✅ read in full (T8-backfill-enable re-checked for order-sensitive staleness against T9/T11/T12's later edits — none found, see Phase 3) |
| `CHANGELOG.MD` (T9/T10-bis/T11/T12 bullets) | ✅ |
| G6 enrichment template `.dev/quality/g6-enrichment-template.md` | ✅ — unchanged since rev 1 |
| Charter `.dev/bishop_program_charter.md` M8 slice | ✅ |
| M7 handoff `.dev/plans/m7-read-path/handoff.md` | ✅ |
| Context map `.dev/plans/m8-hardening-scale/context-map.md` (full, incl. §Coupling surfaces, §Ambiguity flags, §Prior reasoning) | ✅ |
| Code: `registry.py`, `huggingface.py`, `config.py` (scraper), `verify-m8.sh`, `test_verify_m8.py`, `test_scraper_adapters.py`, `test_scraper_adapters_huggingface.py`, `docker-compose.yml`, `test_compose.py`, `transitions.py`, `entries.py` (state-worker + query-api), `search.py`, `loop.py`, `ui/main.py`, `adapter_resolver.py` | ✅ read directly at HEAD |
| Full test suite (750 collected tests) + `verify-m8.sh` + all 8 prior milestone verify scripts | ✅ executed directly (see Phase 2) |

---

## §Provenance log (Phase 0.5)

- **Context map SHA vs HEAD:** still **diverged** — scout SHA `4809890` (2026-06-13) vs HEAD `9983927` (2026-09-11), unchanged from rev 1. Filed as `context-map-stale` (major, per skill exception list) but **downgraded in practice, consistent with rev 1's own disposition**: the divergence is the intended work product of executing the plan (registry.py, adapters/*, config.py, docker-compose.yml, scripts/verify-m8.sh, tests/test_scraper_adapters.py all changed exactly per the map's own `rationale` column), and plan §8.2 now formally records this as **Deferred**, follow-up ID `m8-context-map-refresh`, rather than leaving it an unstated gap the way rev 1 found it. Status vs rev 1: **open, but now disclosed with a named follow-up** (see Finding status table below) — not blocking, same reasoning rev 1 applied.
- **Working-tree state:** dirty, confined to `.dev/quality/g6-enrichment-template.md` (uncommitted fill, unchanged since rev 1 — same disclosed gap), `.dev/audit-*.diff`, `.dev/sqlite.md`, `AGENTS.md`, `thoughts.md`, `.cursor/`. All are planning/reporting/doc artifacts, none in §File map `direct` scope. No `dirty-state caveat` needed on any code finding below.
- **Scout grep coverage:** unchanged from rev 1 — §Coupling surfaces (C1–C5) still records prose tuples with no literal grep patterns attached. `scout-incomplete` (minor, process feedback) — **open, unchanged**.
- **Plan-artifact provenance** (`git show HEAD:<path>` for every plan-declared artifact, re-run independently rather than trusted from plan §8.2's own claim table):

| Artifact class | Status |
|---|---|
| `plan.md`, all packets (T1…T12, T1-bis, T8-bis, T10-bis) | present-in-HEAD |
| `dag.json` | present-in-HEAD — **resolved from rev 1's on-disk-only** |
| `runs/ledger.md`, `runs/execution-summary.md`, all 13 briefs | present-in-HEAD — **resolved from rev 1's on-disk-only** |
| Decision logs (4) | present-in-HEAD (already tracked at rev 1) |
| `CHANGELOG.MD`, G6 template, charter, M7 handoff, context-map | present-in-HEAD |
| Rev-1 audit file itself | present-in-HEAD (ceremony-tracked — was untracked at rev 1) |

  `artifact-not-in-HEAD` (rev 1, major): **resolved**. The closure-ceremony commit range confirmed by `git merge-base --is-ancestor` — `e42207556c10924033aa72dff50ffbf6c2332352` (closure/verify SHA) and `9983927a0804fdb8a4e00da5a9cb5aeb39aa051f` (audit HEAD) both contain the full plan tree, and all four remediation SHAs (`be024148e02ffbb77d37632e6760b2b0e758ec4d` T9, `ba2ad79ca2390b010811563786be8485e86b0164` T12, `f4a793b183c2f636e47e7ebc52c46c2b55beec97` T11, `9f183675d6a713d76c3f822dcabb813f012d5c4d` T10-bis) are verified ancestors of HEAD (`git merge-base --is-ancestor <sha> HEAD` → exit 0 for all five, independently re-run this revision, not trusted from plan §8.1's own claim).

---

## Context chain completeness

All context-chain artifacts named in the task brief and the skill's required-input list were locatable and reviewed — see the omission-free checklist above. Nothing was invented in place of a missing artifact. Phase 0 (cold read) was performed fresh against current HEAD, discarding rev 1's cold-read findings per re-audit discipline; rev 1's cold read is reconciled only in Phase 1 below.

---

## §Cold-read log (Phase 0 — discarded rev-1 cold read; fresh pass against HEAD `9983927`)

Reasoning from `git log`, `git show` diffs, live code reads, and direct pytest/`verify-m8.sh` execution only — no plan prose beyond §2, no decision logs, no CHANGELOG, no briefs consulted before pinning this list:

1. `services/scraper/app/adapters/registry.py` lists 7 adapter classes (`ArxivAdapter`, `GitHubAdapter`, `HuggingFaceAdapter`, `LessWrongAdapter`, `OpenReviewAdapter`, `PapersWithCodeAdapter`, `SemanticScholarAdapter`). `tests/test_scraper_adapters.py` now has `test_registry_contains_all_expected_adapters` asserting membership by `SourceEnum`, not the M2-era `len==1` assertion. Ran it directly: **passes**. → suspected: rev-1 F2 closed.
2. `services/scraper/app/config.py` now defines `HUGGINGFACE_TOKEN = _optional_str_from_env("HUGGINGFACE_TOKEN")`, same shape as `GITHUB_TOKEN`/`SEMANTIC_SCHOLAR_API_KEY`. `services/scraper/app/adapters/huggingface.py` imports it (`from app.config import HUGGINGFACE_TOKEN`) and `_auth_headers()` reads the imported constant, not `os.environ.get`. → suspected: rev-1 F1 closed.
3. `scripts/verify-m8.sh` now runs `tests/test_state_worker_reading_status.py`, `tests/test_state_worker_permanent_fail.py`, `tests/test_query_api_routes_entry_actions.py`, `tests/test_ui_escalations.py`, `tests/test_ui_explorer.py`, `tests/test_scraper_adapters.py`, and its own `tests/test_verify_m8.py`. `tests/test_verify_m8.py` has matching per-module tuple assertions (`STATE_WORKER_TEST_MODULES`, `QUERY_UI_TEST_MODULES`, `GATE_SELF_TEST_MODULES`). Ran the script directly: **exit 0**, 135 passed / 1 skipped. → suspected: rev-1 F3 closed.
4. `docker-compose.yml` scraper/ui tags are `bishop/scraper:m8` / `bishop/ui:m8`; `tests/test_compose.py`'s `milestone_tags` dict matches. T8-bis's three `BISHOP_BACKFILL_*` env keys plus `GITHUB_TOKEN`/`SEMANTIC_SCHOLAR_API_KEY`/`HUGGINGFACE_TOKEN` are still present on the scraper block, byte-identical values. → suspected: rev-1 F4 closed.
5. `tests/test_scraper_adapters_huggingface.py::test_fetch_manifest_sends_huggingface_token_header` now uses `monkeypatch.setattr(hf, "HUGGINGFACE_TOKEN", ...)`, mirroring the GitHub adapter's pattern — no post-import `setenv` remains. → consistent with T10-bis's own kill criterion.
6. `HuggingFaceAdapter.fetch_content()` also calls `_auth_headers()` on the README GET, but **neither** `test_fetch_content_reads_readme_or_falls_back` nor `test_fetch_content_falls_back_when_readme_missing` asserts an `Authorization` header on that request (only `fetch_manifest`'s header is asserted). → suspected minor coverage-gap — **this is the exact item T10-bis's own CHANGELOG entry disclosed as deferred** ("`fetch_content` README Authorization header is not separately asserted; landing gate = m8-hardening-scale auditor-review"), not a surprise finding.
7. `services/query-api/app/routers/entries.py` still hardcodes `READING_STATUS_VALUES = frozenset({...})` instead of importing `ReadingStatusEnum`. Values still match `services/state-worker/app/enums.py`. → same minor observation as rev 1 (F5), unchanged.
8. `services/scraper/app/loop.py::compute_backfill_chunk_starts` still produces overlapping, not disjoint, windows (no `until` param on `SourceAdapter`). Same as rev 1 (F6), unchanged, still disclosed in-code and in the T8-backfill-enable decision log.
9. Naive `python -m pytest -q tests/` still produces the same class of mass false failure (78 failed / 656 passed / 3 skipped / 13 errors this run, vs rev 1's 79/649/3/13 — the +6 delta matches the 6 new/changed test functions T9–T12 landed). Same `app`-package `sys.modules` collision artifact rev 1 documented and routed around; reproduced and re-verified this revision under per-milestone/per-service isolation (see Phase 2) — every isolated grouping passes with zero failures/errors.

---

## Phase 2 — Test execution (full suite, run before all other Phase 2 checks)

**Working-tree SHA confirmation:** `git rev-parse HEAD` = `9983927a0804fdb8a4e00da5a9cb5aeb39aa051f`, matching the task's declared HEAD. `git status --porcelain` shows only doc/scratch paths dirty (listed above) — no code path. `verify-m8.sh` was run directly against this working tree (not a detached worktree) because the tree's code is identical to the ceremony's own detached-worktree run at `e422075` (`e422075` and `9983927` differ only by the doc-only ceremony commit that fills §8.1's SHA/count bytes — confirmed via `git diff e422075 9983927 --stat`, code paths absent from that diff).

**Command(s) used:**

1. `"C:\Program Files\Git\bin\bash.exe" scripts/verify-m8.sh` (no env overrides — `BISHOP_G6_MANUAL`, `BISHOP_G5_LIVE`, `BISHOP_LESSWRONG_PROBE_LIVE` all unset) — the declared M8 gate, run exactly as shipped.
2. Every prior-milestone gate script (`scripts/verify-{g2,g3,m2,m3,m4,m5,m6,m7}.sh`) — replicating rev 1's per-milestone subprocess-isolation strategy, since the repo's own `app`-package collision hazard (confirmed again this revision, see cold-read item 9) makes a single `pytest tests/` invocation unusable as evidence. `verify-g1.sh` skipped (live Docker/compose integration gate, infra-dependent, same as rev 1).
3. Every test file that rev 1 identified as covered by **no** verify script (re-derived independently this revision via `comm` on `ls tests/test_*.py` vs `grep` over `scripts/verify-*.sh`, not copied from rev 1's list), run in service-grouped batches to preserve isolation: scraper-adjacent (`test_scraper_arxiv_adapter.py`, `test_scraper_rate_limit.py`, `test_scraper_config_shared.py`, `test_scraper_failure_envelope.py`, `test_scraper_models.py`, `test_scraper_client.py`, `test_index_policy.py`); prefilter/batch-poller/content-scraper (13 files); state-worker ungated (14 files); verify self-tests (`test_verify_g1.py`, `test_verify_g2.py`, `test_verify_m2.py`); `test_compose.py`.
4. `python -m pytest tests/ --collect-only -q` for the authoritative total count.
5. `python -m pytest -q tests/` (naive, single invocation) — run once to reconfirm the documented collision artifact still reproduces identically in class (not to use as pass/fail evidence).

**Unique test count (`pytest tests/ --collect-only -q`):** **750 tests** (rev 1: 744 — the +6 delta is T9's new `test_registry_lists_all_expected_sources` plus rewritten `test_registry_contains_all_expected_adapters`, T10-bis's two new config tests, T11's extended `test_verify_m8.py` assertions, and T12 — reconciled against the CHANGELOG bullets, not asserted blind).

**Results, by isolated slice — all zero failures / zero errors:**

```
verify-m8.sh (M8 gate, live worktree):     passed=135  failed=0  skipped=1  errors=0  exit=0
verify-g2.sh:                              passed=38   failed=0
verify-g3.sh:                              passed=9    failed=0   (live G3 probe ran; API key present)
verify-m2.sh:                              passed=131  failed=0  skipped=1
verify-m3.sh:                              passed=87   failed=0
verify-m4.sh:                              passed=42   failed=0
verify-m5.sh:                              passed=83   failed=0
verify-m6.sh:                              passed=77   failed=0  deselected=1 (heavy/live G5, opt-in)
verify-m7.sh:                              passed=100  failed=0
scraper-adjacent (ungated):                passed=58   failed=0
prefilter/batch-poller/content-scraper:    passed=73   failed=0
state-worker ungated:                      passed=74   failed=0
verify self-tests (g1/g2/m2):              passed=15   failed=0
test_compose.py (isolated):                passed=26   failed=0
```

No failing test was found anywhere in the suite under proper isolation. **This is the single most significant delta from revision 1**, whose only critical finding (F2) was exactly a full-suite failure (`assert 7 == 1` in `test_registry_contains_only_arxiv`). That test is now `test_registry_contains_all_expected_adapters` and passes.

**Naive single-invocation reconfirmation (not used as pass/fail evidence, recorded for completeness):** `python -m pytest -q tests/` → `78 failed, 656 passed, 3 skipped, 13 errors` — same `app`-package `sys.modules` collision class rev 1 documented (module identity collisions across services sharing the `app` package name), reproduced this revision to confirm it is still an isolation artifact and not a new regression: every one of the 78 "failed" tests belongs to a service (`vector-writer`, `state-worker`) whose isolated slice above passed cleanly.

**Mandatory Phase-2 clause:** no finding filed here — the full suite passes under the isolation strategy the repository's own verify scripts establish and rev 1 already validated as the correct evidentiary standard for this codebase.

---

## Findings table

| ID | Severity | Type | Phase | Subtask | Description | Status vs rev 1 |
|---|---|---|---|---|---|---|
| F1 | major | contract-violation | 2/0 | T10-bis | `HUGGINGFACE_TOKEN` typed-surface admission | **resolved** |
| F2 | critical | contract-violation | 2 | T9 | stale registry regression test | **resolved** |
| F3 | major | process-violation | 2 | T11 | `verify-m8.sh` gate-completeness gap | **resolved** |
| F4 | major | contract-violation | 2 | T12 | compose image tags unmet | **resolved** |
| F5 | minor | observation | 2 | T6 (unchanged) | query-api hardcodes reading-status literals | **open, unchanged** |
| F6 | observation | intent-drift (absorbed) | 3 | T8-bis (unchanged) | backfill chunk windows overlap, not disjoint | **open, unchanged** |
| F7 | observation | process (disclosed) | 3 | T8-bis (unchanged) | architecture folder refresh partial | **open, unchanged** |
| F8 | observation | absorbed (charter-waived) | 0/3 | T7/owner (unchanged) | G6 Call 1 hook quality debt, 3/10 kept rejects | **open, unchanged (waiver still in force)** |
| PF1 | major (downgraded in practice) | context-map-stale | 0.5 | orchestrator (unchanged) | scout SHA `4809890` still diverged from HEAD | **open, now formally disclosed** (plan §8.2 Deferred, follow-up `m8-context-map-refresh`) |
| PF2 | minor | scout-incomplete | 0.5 | orchestrator (unchanged) | §Coupling surfaces has no literal grep patterns | **open, unchanged** |
| PF3 | major | artifact-not-in-HEAD | 0.5 | orchestrator (unchanged) | rev-1: dag.json/packets/runs on-disk-only | **resolved** — all present-in-HEAD, closure SHAs verified ancestors |
| F9 (new) | minor | coverage-gap | 5 | T10-bis (disclosed) | `HuggingFaceAdapter.fetch_content`'s `Authorization` header not independently asserted | **new this revision — disclosed at landing, not a surprise** |

---

## Detailed findings

### F1, F2, F3, F4 — resolved (re-verified against current HEAD, not narrative claim)

**F2 (was critical)** — `tests/test_scraper_adapters.py::test_registry_contains_all_expected_adapters` (T9, `be02414`) replaces the stale `test_registry_contains_only_arxiv`. Reads live `registry.ADAPTER_REGISTRY`, asserts `registry_sources == expected_sources` (all 7 `SourceEnum` values) plus explicit per-class membership. Ran standalone: **passes**. `tests/test_scraper_loop.py::test_registry_lists_all_expected_sources` (the previously-never-written positive-coverage test) also exists and passes. `services/scraper/app/adapters/registry.py` is byte-unchanged by T9 (confirmed — T9's kill criterion forbade touching it; `git show be02414 --stat` shows only the two test files + CHANGELOG). The adjacent `test_source_adapter_contract` (T9's own kill criterion protected it) is present and passing.

**F1 (was major)** — `services/scraper/app/config.py:HUGGINGFACE_TOKEN = _optional_str_from_env("HUGGINGFACE_TOKEN")` (T10-bis, `9f18367`), identical shape to `GITHUB_TOKEN`/`SEMANTIC_SCHOLAR_API_KEY`. `services/scraper/app/adapters/huggingface.py` imports it (`from app.config import HUGGINGFACE_TOKEN`) and `_auth_headers()` reads the imported name, not `os.environ`. `tests/test_scraper_config.py::test_huggingface_token_from_env` and `test_huggingface_token_default_none` both exist and pass (verified via the isolated scraper-adjacent slice above). `tests/test_scraper_adapters_huggingface.py::test_fetch_manifest_sends_huggingface_token_header` uses `monkeypatch.setattr(hf, "HUGGINGFACE_TOKEN", ...)` post-`_load_hf_stack()` — the exact fix the T10 HALT required (post-import `setenv` against a module-level import binding is a no-op; `setattr` on the loaded module object is not). Both config tests and the header test pass.

**F3 (was major)** — `scripts/verify-m8.sh` (T11, `f4a793b`) now runs `tests/test_state_worker_reading_status.py`, `tests/test_state_worker_permanent_fail.py`, `tests/test_query_api_routes_entry_actions.py`, `tests/test_ui_escalations.py`, `tests/test_ui_explorer.py`, `tests/test_scraper_adapters.py`, and `tests/test_verify_m8.py` itself. `tests/test_verify_m8.py` was extended with `STATE_WORKER_TEST_MODULES`, `QUERY_UI_TEST_MODULES`, `GATE_SELF_TEST_MODULES` tuples that are asserted present in the script's literal text — so the gate's own completeness is now pytest-enforced, closing the exact "script text vs self-test" drift class the finding named. `test_does_not_export_g6_manual_flag` still passes (`BISHOP_G6_MANUAL=1` does not appear in the script). Ran `verify-m8.sh` directly: **exit 0**, 135 passed / 1 skipped (the LessWrong live probe, opt-in).

**F4 (was major)** — `docker-compose.yml` scraper image is `bishop/scraper:m8`, ui image is `bishop/ui:m8` (T12, `ba2ad79`). `tests/test_compose.py::test_image_tags_use_milestone_convention`'s `milestone_tags` dict has matching `"scraper": "m8"`, `"ui": "m8"` entries. `git show ba2ad79` confirms the diff touches only these two tag lines plus the matching test-fixture lines — no other service's tag or `milestone_tags` entry changed. T8-bis's three `BISHOP_BACKFILL_*` env keys and the three token env keys on the scraper block are present, byte-identical to their T8-bis-landed values (confirmed by direct read of `docker-compose.yml` lines 28–35). `tests/test_compose.py` passes in full isolation (26/26).

All four are re-verified against live code and passing tests at current HEAD, not against packet self-report, decision-log narrative, or CHANGELOG claim alone — per re-audit discipline.

### F9 (new, minor) — `fetch_content`'s Authorization header not independently asserted

**Expected:** per the skill's typed-surface admission check, a contract surface's tests should exercise the surface at every call-site that uses it, not just one.
**Found:** `HuggingFaceAdapter._auth_headers()` is called from both `fetch_manifest()` (line 179) and `fetch_content()` (line 221). Only the `fetch_manifest` call-site has a header-asserting test (`test_fetch_manifest_sends_huggingface_token_header`). The two `fetch_content` tests (`test_fetch_content_reads_readme_or_falls_back`, `test_fetch_content_falls_back_when_readme_missing`) exercise the README-fetch/fallback logic but never inspect the request's `Authorization` header.
**Disclosure:** this is not a surprise — T10-bis's own CHANGELOG entry names it explicitly: *"Deferred: `fetch_content` README Authorization header is not separately asserted; landing gate = m8-hardening-scale auditor-review — observable: header capture on the README GET in `tests/test_scraper_adapters_huggingface.py`."* This is precisely the item the task brief flagged for this auditor to judge rather than implement.
**Judgment:** `_auth_headers()` is a single, shared, already-tested function — the risk is narrow (a future refactor that special-cased `fetch_content`'s headers would not be caught here) but real (it is exactly the kind of per-call-site gap that produced the original F1). Filed as `coverage-gap`, **minor**, not major: the shared-function structure means the header-construction logic itself is fully covered; only the second call-site's *use* of that function is unasserted, and `fetch_content`'s own request-handler test fixtures already capture `request.headers` in the sibling test — extending it would be a small, low-risk addition. Not blocking. Recommend as a follow-up (does not require a new amendment subtask; could be picked up incidentally next time `tests/test_scraper_adapters_huggingface.py` is touched).

### PF1 — `context-map-stale` (major, downgraded in practice) — open, unchanged, now disclosed

Scout SHA `48098900eb546cbac9fcb22e7f5180536255007e` (2026-06-13) is still the pin; HEAD is `9983927` (2026-09-11). Every `direct`-classified §File map row has diverged — this is the expected, intended outcome of executing the plan (same conclusion rev 1 reached). **What changed this revision:** plan §8.2 now explicitly names this as **Deferred**, follow-up ID `m8-context-map-refresh`, rather than the auditor being the only party to note it. Per skill's severity-calibration heuristic, `context-map-stale` is an explicit exception that stays `major` even though documentation-only — but consistent with rev 1's own disposition (and the fact that this divergence is the plan's designed outcome, not an unplanned drift), this auditor treats it as **non-blocking**, reported rather than corrected, per the skill's explicit instruction that "staleness is reported, not corrected; re-exploration is an orchestrator decision." This is disclosed as a judgment call, not a silent downgrade.

### PF3 — `artifact-not-in-HEAD` (major) — resolved

Rev 1 filed this against `dag.json`, all `packets/T1-bis.md`/`T8-bis.md`, and the entire `runs/` tree being on-disk-only/untracked. This revision independently re-ran `git show HEAD:<path>` for every one (not trusted from plan §8.2's own claim table) and confirmed all are `present-in-HEAD`. The ceremony commit range (`e422075` → `9983927`) and all four remediation SHAs are independently confirmed ancestors of HEAD via `git merge-base --is-ancestor`.

---

## Phase 1 — Intent traceability

- **Task statement → plan → code:** T9–T12/T10-bis's scopes map 1:1 to rev-1's F1–F4 (each closes exactly one named finding, no scope creep). Charter non-goals respected — no §23/§24 item touched; no `Mark Resolved` action added; `enrichment_prompts.py` and `professional_v1.0.0.yaml` untouched (confirmed via `git show` on all four remediation commits — none touch those paths).
- **Construction ≠ completion check:** `HUGGINGFACE_TOKEN` is not just declared — traced the call path: `config.py` defines it → `huggingface.py` imports and reads it in both `_auth_headers()` call-sites → `fetch_manifest`'s call-site is asserted by a passing test that reads the actual HTTP request header sent by `_auth_headers()`'s live invocation (not a unit test of `_auth_headers()` in isolation). This is a genuine fulfilled-scope path, not a construction-only symbol. Same check for `ADAPTER_REGISTRY`'s test coverage: `test_registry_contains_all_expected_adapters` reads the live module attribute via `_load_adapters_stack()`, not a mock.
- **Files-to-touch discipline:** each of T9/T10-bis/T11/T12's kill criteria explicitly forbade touching files outside its own grant (verified via `git show --stat` on all four commits — each touches exactly its declared Files-to-touch list plus `CHANGELOG.MD`).
- **Packet → plan §4 consistency:** `packets/T9.md`, `T10-bis.md`, `T11.md`, `T12.md` (read in full) are verbatim extracts of plan §4's corresponding subtask blocks — no drift between packet and plan text this revision (unlike rev 1, which found no drift here either).
- **§5.4 hidden couplings for T9–T12** (the four new tuples plan v1.4/v1.5 added): all four ("T9's fix must land before T11 gates the file," "HUGGINGFACE_TOKEN + adapter switch same commit," "HF header test setattr not setenv," "compose tag + test_compose.py together," "verify-m8.sh text ≡ test_verify_m8.py module set") are **confirmed held** — re-verified independently in Phase 2/Detailed findings above, not taken from plan §8.4's own disposition table.

No intent-drift findings this revision beyond the pre-existing, unchanged F6 (absorbed, disclosed since rev 1).

---

## Phase 2 — Contract compliance

Beyond the mandatory test-execution clause above (all green):

- **Typed-surface admission (`HUGGINGFACE_TOKEN`):** all three legs verified — (a) typed declaration on `config.py` ✅, (b) parse path traced, not shadowed by any `getattr(..., default)` or unknown-key filter (it's a direct module-level assignment, no filtering layer exists in this codebase's config pattern) ✅, (c) round-trip test exists and passes (`test_huggingface_token_from_env`, `test_huggingface_token_default_none`, plus the live-header-assertion test) ✅.
- **Literal-string parity:** `bishop/scraper:m8` / `bishop/ui:m8` (compose) match plan §2's Naming contract byte-for-byte. `scripts/verify-m8.sh`'s newly-added module path strings (`tests/test_state_worker_reading_status.py` etc.) match plan §2's Tests row and `tests/test_verify_m8.py`'s own assertion strings byte-for-byte (checked both files side by side).
- **Error envelope:** unchanged from rev 1 — `PATCH /entries/{source_id}/reading-status` (404/409/422), `POST /entries/permanent-fail` (404/409), query-api 502 `upstream_error` — all still implemented as declared, re-read directly in `transitions.py` and `entries.py` (both services) this revision, not assumed from rev 1.
- **Naming / Logging:** no changes to these surfaces since rev 1 outside the T12 tag bump (covered above).
- **CLI surface:** unchanged — no new CLI subcommands, `verify-m8.sh` remains the sole M8 gate string, wrapper scripts (`run-g5-quality-gate.sh`, `run-g6-prefilter-replay.sh`, `run-g6-enrichment-sampling.sh`) unchanged, retired v1.0 G6 paths still absent (`test_does_not_rebuild_retired_v1_g6_scaffold` passes).

No new contract-violation findings this revision beyond F9 (coverage-gap, not a contract-violation — the surface itself is correctly typed and wired; only one call-site's header use is unasserted).

---

## Phase 3 — Decision log audit

All four architectural-tier decision logs (T1/T1-bis, T4, T5, T8-bis) re-read in full this revision. T9/T10-bis/T11/T12 are `standard` tier per plan §4 — correctly no decision log required (their scopes are mechanical: test rewrite, config-pattern repeat, script/self-test pairing, compose tag pairing — none fork a design decision, consistent with the plan's own "no design fork" `Model class` annotations, and this auditor concurs with that tier assignment on inspection of the actual diffs).

- **Chosen approach vs. code:** T8-backfill-enable.md's registry-merge, backfill-chunking, and `verify-m8.sh`-scope prose all still match code exactly (re-verified, not assumed from rev-1's prior pass).
- **Order-sensitive prose sweep:** T8-backfill-enable.md's description of `verify-m8.sh` ("runs the full M8 scraper adapter/registry/config/backfill pytest slice... then G5 wrapper... then G6 gold... then only the two G6 structural test IDs") is accurate as a description of **T8-bis's own diff** and does not claim to describe the post-T11 extended state — it does not assert current-state falsely, since T11's extension (adding T5/T6 files) is additive and does not contradict any claim T8-bis's log makes about what it itself added. No `decision-log-stale` finding. (Same conclusion rev 1 reached on this exact log; re-verified independently against the now-further-amended script.)
- **Rejected alternatives actually avoided:** confirmed — T12's kill criteria (no other service's tag touched) and T9's kill criteria (registry.py untouched, `test_source_adapter_contract` preserved) hold in the actual diffs.
- **Deferred items actually deferred:** Call 1 hook iteration (`g6-call1-hooks-iteration`), OpenReview PDF full-text, disjoint-window chunking, architecture-folder full refresh, and now `m8-context-map-refresh` and F9's `fetch_content` header assertion are all still genuinely open — none silently absorbed into T9–T12's scope (each of the four remediation commits touches only its own narrow Files-to-touch list, confirmed via `git show --stat`).
- **Narrative-concealment check against the fresh cold read:** none of this revision's cold-read items (1–9 above) are concealed by any decision log or CHANGELOG entry — items 1–5 are independently and more precisely disclosed in the T9/T10-bis/T11/T12 CHANGELOG bullets (read *after* pinning the cold read); item 6 (F9) is explicitly named in T10-bis's own CHANGELOG bullet, which is the opposite of concealment — it is the cleanest disclosure in this plan's history. Items 7–9 (F5/F6/unchanged) were already disclosed at rev 1 and remain accurately described.

---

## Phase 4 — Adversarial testing

**Focus areas:** Integration seams (mandatory), Regression surface, Contract compliance / typed-surface admission — rationale in Audit metadata above.

### Integration seams (§Coupling surfaces C1–C5, re-verified at HEAD `9983927`, not carried forward from rev 1)

| Coupling | Status | Adversarial check performed at current HEAD | Result |
|---|---|---|---|
| C1 — `ADAPTER_REGISTRY` ↔ content-scraper `adapter_resolver` | confirmed | Read `services/content-scraper/app/adapter_resolver.py` directly: `from scraper_app.adapters.registry import ADAPTER_REGISTRY`; iterates it to build the resolver map. All 7 adapter classes still expose `fetch_content` (read each adapter module) | **passes** |
| C2 — state-worker hub ↔ query-api ↔ UI | confirmed | `services/ui/app/main.py` grepped for `state-worker`/`STATE_WORKER`: only `STATE_WORKER_INTERNAL_PORT` import for port arithmetic, no direct request construction | **passes** |
| C3 — `reading_status` SQLite vs. DuckDB mirror | suspected → disproved | `services/query-api/app/retrieval/search.py:97` branches `reading_status is not None` to the SQLite path (`sqlite_filter_source_ids`), never DuckDB | **ruled out**, unchanged from rev 1 |
| C4 — `SOURCE_RATE_LIMITS` before `failure_envelope` | confirmed | Adapters bind `rate_limit = SOURCE_RATE_LIMITS[...]` at class-definition time (import-time failure, not runtime `KeyError`) — read `huggingface.py:160` and confirmed the pattern holds for all 7 | **passes** |
| C5 — G4/G5/G6 manual gates | resolved via v1.3 waiver, unchanged | `.dev/quality/g6-enrichment-template.md` unchanged since rev 1 (7/10, three named rejects); `verify-m8.sh` still never exports `BISHOP_G6_MANUAL=1` (re-grepped script text this revision) | **passes** |

**§5.4 tuples added in v1.4/v1.5 (T9–T12/T10-bis-specific):** all four re-verified directly against code/tests this revision (not taken from plan §8.4's own disposition claim) — see Phase 1 above. All **confirmed held**.

**Frozen-adjacent paths falsifier** (re-run independently this revision, not trusted from plan §8.4's claim): `git diff 5e048337b9b7262c604dfce04f3e565d33cf0f4a -- config/index_policy.yaml bishop_shared/index_policy.py config/sources/arxiv.yaml bishop_shared/source_config.py bishop_shared/profile_renderer.py config/profiles/professional_v1.2.0.yaml config/profiles/professional_v1.0.0.yaml eval/prefilter_v1/{contract,items,labels}.json scripts/{replay_prefilter,build_eval_v1,apply_adjudication}.py tests/{test_index_policy,test_g5_quality_gate}.py` at current HEAD → **empty**. Holds through the T9–T12/T10-bis remediation wave, as all four kill criteria forbade touching these paths (confirmed via `git show --stat` on each commit — none appear).

### Regression surface (this milestone's historically highest-risk area, per rev 1's F2)

The naive full-suite run still surfaces the documented `app`-package collision artifact (78 failed this revision vs 79 at rev 1 — the 1-test delta matches the M2-era test T9 rewrote no longer failing in the naive run either, since it's now assertion-shape-correct regardless of collision). Systematic re-run under per-milestone/per-service isolation (8 prior-milestone verify scripts + the M8 gate + 5 ungated-file groupings, all executed directly this revision) resolves **zero** to genuine regressions — every isolated slice passes. This is the direct, independently-reproduced answer to rev 1's F2: the regression that shipped past the milestone's own gate is now caught by an extended gate (F3→resolved) and is itself fixed (F2→resolved).

### Contract compliance / typed-surface admission

Covered in detail under Phase 2 above and the F1 detailed finding — all three admission legs verified for `HUGGINGFACE_TOKEN`, the surface F1 was filed against.

---

## Phase 5 — Coverage gap analysis

- `ADAPTER_REGISTRY`'s declared acceptance test (`tests/test_scraper_loop.py::test_registry_lists_all_expected_sources`) — **exists and passes** (was the rev-1 coverage-gap half of F2; now closed).
- `HUGGINGFACE_TOKEN`'s declared tests (`test_huggingface_token_from_env`, `test_huggingface_token_default_none`) — **exist and pass** (was the rev-1 coverage-gap half of F1; now closed).
- **New this revision:** `HuggingFaceAdapter.fetch_content`'s use of `_auth_headers()` is not asserted by a header-inspecting test — filed as **F9** (minor coverage-gap, disclosed at landing by T10-bis's own CHANGELOG entry, judged non-blocking above).
- `scripts/verify-m8.sh`'s own completeness is now provable by `tests/test_verify_m8.py` (was the rev-1 §5.3 highest-re-plan-risk item for T11) — verified both files name the same module set; no drift.
- Kill-criterion / coverage-scope contradiction check: none of T9–T12/T10-bis's kill criteria describe a scope the plan declines to test automatically — all four remediations are fully pytest-covered by design (their whole purpose was closing test gaps or gate gaps).
- Test-quality spot check: `test_registry_contains_all_expected_adapters` asserts membership by set-equality against live `SourceEnum` values (not tautological); `test_fetch_manifest_sends_huggingface_token_header`/header-setattr variant asserts the literal `Authorization` header value sent on a mocked HTTP request (not just "no exception raised"); `test_image_tags_use_milestone_convention` asserts literal tag strings per service. All meaningful, non-tautological.
- No other kill criterion across the T1-bis/T2/T3/T4/T5/T6/T7/T8-bis architecture-tier subtasks was found newly uncovered this revision (re-checked; unchanged from rev 1's Phase 5 conclusion).

---

## Verdict

**`pass-with-conditions`**

All four blocking findings from revision 1 (F2 critical, F1/F3/F4 major) are **resolved** — independently re-verified against current HEAD code and a fully-green, independently-executed test suite (750 tests, zero failures under proper per-service isolation; the declared M8 gate `scripts/verify-m8.sh` itself passes at exit 0). No new critical or major findings were introduced by the remediation wave.

**Conditions (all minor/observation — do not block merge, but are named rather than silently absorbed):**

1. **F5** (minor, unchanged) — query-api's `READING_STATUS_VALUES` frozenset duplicates `ReadingStatusEnum` instead of importing it. Accepted residual risk: silent drift if the enum changes without updating this literal. No follow-up ID named; low urgency.
2. **F6** (observation, absorbed, unchanged) — backfill chunk windows overlap rather than partition disjointly (no `until` param on `SourceAdapter`). Accepted residual risk: bounded re-fetch volume, deduplicated by `source_id` at ingest. Named landing gate: a future packet touching `adapters/base.py` + all seven adapters.
3. **F7** (process, disclosed, unchanged) — `.dev/architecture/bishop/` refresh remains partial (module-map/coupling-surfaces/dependency-graph/INDEX refreshed; several pre-M4/M7 files still flagged stale). Named landing gate: next `project-architecture` pass or M9 kickoff.
4. **F8** (absorbed, charter-waived, unchanged) — G6 enrichment Call 1 quality debt (3/10 `challenge_hooks` rejects kept). Owner waiver 2026-09-10 still in force. Named follow-up: `g6-call1-hooks-iteration`.
5. **F9** (new, minor, disclosed at landing) — `HuggingFaceAdapter.fetch_content`'s `Authorization` header use is not independently test-asserted (only `fetch_manifest`'s is). Accepted residual risk: narrow — shared, already-tested `_auth_headers()` function; only the second call-site's use is unasserted. No amendment required; pick up incidentally.
6. **PF1 / `context-map-stale`** (major-by-skill-default, downgraded in practice per rev-1 precedent and this auditor's independent concurrence) — scout SHA `4809890` still predates all M8 code. Named follow-up (now formal, plan §8.2): `m8-context-map-refresh`.
7. **PF2 / `scout-incomplete`** (minor, unchanged) — §Coupling surfaces lacks literal grep patterns. Feedback signal for pre-plan-exploration; no code action.

None of these seven conditions implicate the milestone's core adapter/hub/backfill/gate architecture, which held up under direct code reading, decision-log cross-checking, live test execution, and the mandatory Integration-seams adversarial pass. The milestone is merge-ready with these seven items tracked as named, disclosed residuals rather than silently closed.

---

## §Divergence log entry

Conditions for writing this section (intent-drift findings at minor/observation severity, absorbed, under a `pass`/`pass-with-conditions` verdict) **are met** this revision (verdict is `pass-with-conditions`; F6 is an absorbed intent-drift finding at observation severity). Appending to `.dev/architecture/bishop/architectural-decisions-divergence.md`:

```
## M8 — 2026-09-11

**Spec intent:** §18.4 describes chunked backfill as fetching bounded windows; no explicit
disjoint-vs-overlapping design constraint is stated but a naive reading implies non-overlapping chunks.
**Execution decision:** `compute_backfill_chunk_starts`/`_run_backfill_chunks` produce overlapping
(superset-minus-earlier-days) windows because `SourceAdapter.fetch_manifest` has no `until` parameter;
the manifest-insert path dedupes by `source_id`.
**Rationale:** Chunking's purpose is bounding single-request volume and giving pre-filter an inter-chunk
pause, not eliminating re-fetched rows (T8-bis decision log, `.dev/decision-logs/m8-hardening-scale/T8-backfill-enable.md`).
Disjoint windows would require a new `until` parameter across all seven adapters — out of scope for this milestone.
**Status:** needs-ph1-review (a future `SourceAdapter.fetch_manifest(since, until)` signature change is the
named landing gate; re-fetch volume at true backfill scale has not yet been measured against §18.3's volume gate).
```

---

## Scout-prediction reconciliation

| Scout prediction | Type | Description | Outcome (re-verified at HEAD `9983927`) | Finding ID |
|---|---|---|---|---|
| `services/scraper/app/adapters/registry.py` — direct | file-map | "Expand beyond `[ArxivAdapter]`" | verified | — |
| `services/scraper/app/adapters/*.py` — direct | file-map | "T2–T4 new modules + tests" | verified | — |
| `services/scraper/app/rate_limit.py` — direct | file-map | "Appendix B all sources" | verified | — |
| `services/scraper/app/config.py` — direct | file-map | "Backfill windows, schedules, chunking" | verified — **now includes `HUGGINGFACE_TOKEN`** (T10-bis) | F1 resolved |
| `bishop_shared/scraper_config.py` — direct | file-map | "Shared BACKFILL_CONFIG" | verified | — |
| `services/state-worker/app/{routers/entries.py,transitions.py}` — direct | file-map | "Hub extension" | verified | — |
| `services/query-api/app/routers/` — direct | file-map | "POST/PATCH escalation + reading status" | verified | — |
| `services/ui/app/main.py` + templates — direct | file-map | "Escalations, DB explorer, controls" | verified | — |
| `scripts/verify-m8.sh` — direct | file-map | "M8 gate (T8)" | verified created, **now complete as a gate** (T11) | F3 resolved |
| `docker-compose.yml` — direct | file-map | "compose tags `bishop/scraper:m8`, `bishop/ui:m8`" | **prediction fulfilled** (T12) — was prediction-divergence at rev 1 | F4 resolved |
| `tests/test_scraper_adapters.py` — direct | file-map | "Extend per adapter" | **prediction fulfilled** (T9) — was prediction-divergence at rev 1 | F2 resolved |
| C1 `ADAPTER_REGISTRY` ↔ `adapter_resolver` | suspected_coupling | fetch_content must land with manifest adapter | verified (confirmed, held) | — |
| C2 state-worker ↔ query-api ↔ ui | suspected_coupling | UI never calls state-worker directly | verified (confirmed, held) | — |
| C3 `reading_status` SQLite vs. DuckDB | suspected_coupling | post-INDEXED status edits need consistent filter semantics | ruled-out (mitigated as designed) | — |
| C4 `SOURCE_RATE_LIMITS` ↔ `failure_envelope` | suspected_coupling | every new source needs a rate-limit entry first | verified (confirmed, held) | — |
| C5 G4/G5/G6 manual gates | suspected_coupling | owner sign-off before backfill enable | verified (resolved via documented v1.3 waiver, unchanged) | — |
| Ambiguity flag 1–5 | ambiguity_flag | see rev-1 table | resolved, unchanged | — |
| Ambiguity flag 6 (Mark Resolved) | ambiguity_flag | explicit non-goal | not-tested (correctly out of scope; no code found implementing it, re-checked) | — |

---

## §Milestone handoff (charter-governed)

**`audit_status: accepted-with-waivers`**

**Waiver table** (finding ID + accepted residual risk — mapping the seven verdict conditions above):

| Finding ID | Accepted residual risk |
|---|---|
| F5 | Reading-status literal duplication vs `ReadingStatusEnum`; drift risk only if the enum changes without updating this frozenset |
| F6 | Overlapping backfill chunk windows; bounded re-fetch volume, deduplicated by `source_id`; disjoint windows require an `until` param across 7 adapters (out of scope) |
| F7 | Architecture folder refresh partial (pre-M4/M7 files stale); landing gate = next `project-architecture` pass or M9 kickoff |
| F8 | G6 Call 1 `challenge_hooks` quality debt, 3/10 rejects kept; owner-waived 2026-09-10; follow-up `g6-call1-hooks-iteration` |
| F9 | `fetch_content`'s `Authorization` header use unasserted (shared function already tested via `fetch_manifest`); disclosed at landing by T10-bis |
| PF1 (`context-map-stale`) | Scout inventory (2026-06-13) predates all M8 landed state; follow-up `m8-context-map-refresh` |
| PF2 (`scout-incomplete`) | §Coupling surfaces lacks literal grep patterns; feedback signal only, no code risk |

**`landed_contracts`** (symbol + owning file only, no definitions pasted — re-derived from live code this revision, not copied from plan §8.3):

- `BackfillConfig`, `BACKFILL_CONFIG`, `SOURCE_SCHEDULE_INTERVAL_SEC` — `bishop_shared/scraper_config.py`
- `SOURCE_RATE_LIMITS` (7 sources) — `services/scraper/app/rate_limit.py`
- `BISHOP_BACKFILL_ENABLED`, `BISHOP_BACKFILL_CHUNK_DAYS`, `BISHOP_BACKFILL_INTER_CHUNK_DELAY_SEC`, `GITHUB_TOKEN`, `SEMANTIC_SCHOLAR_API_KEY`, **`HUGGINGFACE_TOKEN`** — `services/scraper/app/config.py` (all six now landed and typed — F1 closed)
- `HuggingFaceAdapter`, `PapersWithCodeAdapter`, `SemanticScholarAdapter`, `GitHubAdapter`, `OpenReviewAdapter`, `LessWrongAdapter` — `services/scraper/app/adapters/{huggingface,paperswithcode,semantic_scholar,github,openreview,lesswrong}.py`
- `ADAPTER_REGISTRY` (7 sources, module + **test coverage** now both landed) — `services/scraper/app/adapters/registry.py` + `tests/test_scraper_adapters.py::test_registry_contains_all_expected_adapters` + `tests/test_scraper_loop.py::test_registry_lists_all_expected_sources`
- `compute_backfill_chunk_starts`, `_run_backfill_chunks` — `services/scraper/app/loop.py`
- `ReadingStatusPatchRequest/Response`, `PermanentFailPostRequest/Response` — `services/state-worker/app/models/http.py`
- `PATCH /entries/{source_id}/reading-status`, `POST /entries/permanent-fail` — `services/state-worker/app/routers/entries.py` + `transitions.py`
- query-api proxies (retry/permanent-fail/reading-status) — `services/query-api/app/routers/entries.py`
- UI `/escalations`, `/explorer`, reading-status control — `services/ui/app/main.py`
- `scripts/verify-m8.sh` — declared M8 gate, **now complete relative to its own §2 test-surface declaration** — gap closed by T11
- G6 prefilter gold binding — `tests/test_g6_prefilter_gold.py` (≥129 items, unchanged)
- G6 enrichment sampling — `.dev/quality/g6-enrichment-template.md` + `tests/test_g6_enrichment_sampling.py` (7/10, owner-waived, unchanged)

**Charter cross-check:** every M8 charter-block row (adapter registry expansion; escalation panel retry/permanent-fail; reading-status update; backfill config; G7 backfill/e2e exit; pre-filter and enrichment quality gates; escalation panel functional; G4/G5/G6 entry gates) has a landed counterpart above, **including** the `HUGGINGFACE_TOKEN` sub-row (previously the sole gap, F1 — now closed) and the compose-tag half of the Naming-contract row (previously F4 — now closed). No charter-block row is absent from `landed_contracts` without a corresponding finding.

---

## Closure ceremony (emit only — do not apply)

Verdict is `pass-with-conditions` → `audit_status: accepted-with-waivers`. The following exact path/field/value writes close the ceremony. **This auditor does not apply these** — plan-runner or a ceremony-only cheap subagent may byte-apply them per the skill's closure-ceremony clause.

1. **File:** `.dev/plans/m8-hardening-scale/plan.md`
   **Field:** the `Re-audit slot: audit_status:` token, currently `not_run` (plan header line 5, "Re-audit slot: `audit_status: not_run`" and again in §8 lead-in line 697/920 area — both instances of the literal string `audit_status: not_run` in this plan file should be updated together).
   **Value to write:** `audit_status: accepted-with-waivers`

2. **File:** `.dev/plans/m8-hardening-scale/plan.md`
   **Field:** plan header `**Status:**` line (line 6) and `**Audit consumed:**` line (line 15).
   **Value to append:** a reference to this audit — `.dev/audits/2026-09-11-m8-hardening-scale.md`, revision 2, verdict `pass-with-conditions`, `audit_status: accepted-with-waivers`; F1/F2/F3/F4 resolved; F5–F9 + PF1/PF2 named as waivers (not blocking).

3. **File:** `.dev/plans/m8-hardening-scale/plan.md`
   **Field:** `run_status:` (line 5) — **no change**. Per the skill and the task brief, `run_status` stays `amended` (this is a plan-run-status field, distinct from the audit disposition slot). Do not flip to `complete` as part of this ceremony — that is a separate milestone-completion decision outside this audit's scope.

4. **File:** `.dev/plans/m8-hardening-scale/plan.md §8.6 Audit remediation cross-link**
   **Field:** append a closing line under the existing F1–F4 table: "Re-audit revision 2 (2026-09-11): `pass-with-conditions` / `audit_status: accepted-with-waivers`. F1–F4 resolved. F5–F9, PF1 (`context-map-stale`), PF2 (`scout-incomplete`) named as waivers per `.dev/audits/2026-09-11-m8-hardening-scale.md`."

No other plan bytes are named to flip. Do not touch §2, §4, §5, or any packet — those are historical record of what was planned/executed, not audit-disposition fields.

---

*Audit revision 2 — m8-hardening-scale — auditor-review v1.0 — supersedes revision 1 (2026-09-10, verdict `fail`) — verdict `pass-with-conditions` / `audit_status: accepted-with-waivers`*
