# Audit — m8-hardening-scale

**Audit date:** 2026-09-10 · **Audit document revision:** 1 (first audit of this plan; not a re-audit)
**Auditor skill:** auditor-review v1.0 · **Fan-out policy:** operating-posture v0.4
**Plan audited:** `.dev/plans/m8-hardening-scale/plan.md` v1.3 (`run_status: amended`)
**HEAD at audit:** `43a8bc42d5c7499593849e3aab8b5ec918120cde` (confirmed via `git rev-parse HEAD` — matches expected T8-bis SHA)
**Charter binding:** `.dev/bishop_program_charter.md` v0.1.0 — Milestone M8 (L492–540), Gates G4/G5/G6/G7

## Audit metadata

- **Context map:** `.dev/plans/m8-hardening-scale/context-map.md`, scout SHA `48098900eb546cbac9fcb22e7f5180536255007e`, readiness verdict at planning time **CONDITIONAL**.
- **Focus areas chosen (Phase 4):** (1) **Integration seams** (mandatory — 5 catalogued §5.4/context-map coupling tuples), (2) **Regression surface** (pre-existing suite behavior under the M8 diff — this is where the highest-severity finding surfaced), (3) **Contract compliance / typed-surface admission** (§2 rows are numerous and multi-subtask; this is the milestone's actual risk profile, not edge-case/security/perf).
- **Operating-posture disclosure:** the skill directs Phase 0 / 0.5 / 2 reads, greps, and the full-suite run to Composer 2.5 / Grok 4.6 subagents. Two such subagents were dispatched (diff collection on Composer 2.5-fast; full-suite run on Grok 4.6-high-fast) but this auditor did not block on them and instead performed the equivalent reads, greps, and 744-test suite execution directly, because the repository's own "app-package collision" test-isolation convention (documented in `scripts/verify-m7.sh`/`verify-m8.sh` comments) required interactive correction of the naive invocation (see §Provenance / Phase 2 below) — this was judgment-adjacent (interpreting *why* a naive run failed) rather than purely mechanical, so it stayed on the parent rather than being handed back to a subagent blind. Severity, intent-drift-vs-coverage-gap classification, and the verdict below are entirely this agent's own.
- **Phase 0 discipline caveat (disclosed):** `plan.md` was read via a single whole-file tool call before the cold read was pinned (tool constraints do not support section-scoped reads). The cold read below was reasoned primarily from diffs, running code, and test output, per discipline — but strict "§1/§2 only" isolation from the rest of the plan's prose was not literally maintained. Disclosed rather than silently claimed.

---

## §Provenance log (Phase 0.5)

- **Context map SHA vs HEAD:** diverged. Scout SHA `4809890...` (2026-06-13) vs HEAD `43a8bc4` (2026-09-10). Every `direct`-classified §File map row has changed since scout time — **this is the expected, intended outcome of executing the plan**, not drift introduced around the plan. Filed per skill instruction as `context-map-stale` (major, procedural) but downgraded in practice: the divergence *is* the planned work product (registry.py, transitions.py, entries.py routers, ui/main.py, config.py, docker-compose.yml, scripts/verify-m8.sh all changed exactly as the map's `rationale` column anticipated). One row is a genuine miss, not benign drift — see Scout-prediction reconciliation table (`tests/test_scraper_adapters.py`, flagged `direct`/"Extend per adapter", never touched by any subtask).
- **Working-tree state:** dirty, as disclosed by the task brief. Dirty paths are confined to `.dev/plans/m8-hardening-scale/**` (plan.md, packets, dag.json, runs/) and `.dev/quality/g6-enrichment-template.md` — planning/reporting artifacts, not code. No dirty path is in §File map `direct` scope. No `dirty-state caveat` needed on any code finding below.
- **Scout grep coverage:** context-map §Coupling surfaces records five prose tuples (C1–C5) with no literal grep patterns attached; the orchestrator's §5.4 vocabulary (registry merge conflicts, rate-limit KeyError, verify-m8 BISHOP_G6_MANUAL, frozen-adjacent diff) is a superset of C1–C5 by content but not grep-traceable to the map. Filed as `scout-incomplete` (minor, process feedback for pre-plan-exploration — not a code finding).
- **Plan-artifact provenance** (`git show HEAD:<path>` for every plan-declared artifact):

| Artifact | Status |
|---|---|
| `plan.md`, `packets/T1.md`…`T8.md` | present-in-HEAD (working copy has uncommitted edits layered on top — expected per task brief) |
| `packets/T1-bis.md`, `packets/T8-bis.md` | **on-disk-only** (untracked / staged-not-committed) |
| `dag.json` | **on-disk-only** (staged, not committed) |
| `runs/ledger.md`, `runs/execution-summary.md`, `runs/*-brief.md` (all 10) | **on-disk-only** (untracked) |
| `.dev/decision-logs/m8-hardening-scale/{T1-adapter-foundation,T4-openreview-lesswrong,T5-state-worker-ops,T8-backfill-enable}.md` | present-in-HEAD |
| `.dev/quality/g6-enrichment-template.md` | present-in-HEAD (working copy has uncommitted edits — the filled 10-entry review layered on top of a HEAD version) |
| `CHANGELOG.MD` | present-in-HEAD |
| `.dev/architecture/bishop/` | present-in-HEAD |

  Per the task brief this is expected — plan v1.3 amendment materials (dag.json, T1-bis/T8-bis packets, the entire `runs/` ledger tree) were never committed. Filed as `artifact-not-in-HEAD` (major, per the skill's explicit exception to the documentation-only-caps-at-minor rule — this degrades merge archaeology) but not weighted as a blocking finding on its own, since the underlying code commits (`7fd52b9`…`43a8bc4`) that these artifacts describe **are** in HEAD and were independently verified against the artifacts' claims. No plan §8 closure SHA exists yet to cross-check (plan §8 is honestly `not_run` — not a second finding, per the task brief and the skill's guidance not to double-file an already-disclosed gap).

---

## Context chain completeness

All context-chain artifacts named in the task were locatable and reviewed: context map, plan (v1.3), machine DAG, all 10 packets, ledger, execution-summary, all 10 briefs, all 4 decision logs, G6 enrichment template, M7 handoff, CHANGELOG, architecture folder. Nothing was invented in place of a missing artifact. Phase 0 (cold read) completed against task statement + plan §2 + live diffs/code/tests before decision logs, changelog, or briefs were opened, subject to the whole-file-read caveat above.

---

## §Cold-read log (Phase 0, pinned before decision logs/changelog/briefs were opened)

Reasoning from `git log`, `git show` diffs, live code reads, and direct pytest execution only:

1. `services/scraper/app/config.py` has `GITHUB_TOKEN` and `SEMANTIC_SCHOLAR_API_KEY` but **no `HUGGINGFACE_TOKEN`**, despite plan §2 declaring it as a T2-owned typed row with test `test_scraper_config.py::test_huggingface_token_from_env`. The HF adapter reads the env var directly at call-site (`huggingface.py:47`, raw `os.environ.get`). The declared test does not exist anywhere in `tests/`. → suspected major contract-violation.
2. `services/scraper/app/adapters/registry.py` (T8-bis, 7 adapters) coexists with `tests/test_scraper_adapters.py::test_registry_contains_only_arxiv`, an M2-era test hard-asserting `len(ADAPTER_REGISTRY) == 1`. Ran it directly: **fails** (`assert 7 == 1`). → suspected critical/regression, not caught by any milestone verify script.
3. `docker-compose.yml` scraper/ui image tags are still `m2`/`m7`; plan §2 Naming contract declares `bishop/scraper:m8`/`bishop/ui:m8`; `docker-compose.yml` is in T8-bis's own Files-to-touch. → suspected major contract-violation (naming literal unmet).
4. `scripts/verify-m8.sh` (the declared M8 gate script) does not reference `tests/test_state_worker_reading_status.py`, `tests/test_state_worker_permanent_fail.py`, `tests/test_query_api_routes_entry_actions.py`, `tests/test_ui_escalations.py`, `tests/test_ui_explorer.py`, or its own `tests/test_verify_m8.py` — all §2-declared test surfaces for T5/T6. → suspected major process gap in the gate script itself (files individually pass — verified below — but the gate cannot prove it).
5. `services/query-api/app/routers/entries.py` hardcodes a `READING_STATUS_VALUES` frozenset instead of importing `ReadingStatusEnum` — values currently match `state-worker/app/enums.py` exactly. → minor observation (cross-service enum duplication risk, no current defect).
6. Naive `python -m pytest -q` over the whole `tests/` tree produced 79 failures / 13 errors — almost all resolved to `app`-package sys.modules collisions across services when re-run in the project's own per-milestone-script grouping (confirmed real vs. artifact below).

---

## Phase 2 — Test execution (full suite, run before all other Phase 2 checks)

**Command(s) used:** the naive single-invocation `python -m pytest -q` (from repo root) does **not** correctly evaluate this repository — it collects all services' `app.*` packages into one `sys.modules` namespace and produces mass false failures (79 failed / 649 passed / 3 skipped / 13 errors), which is exactly the "app package collision" hazard the project's own `verify-m7.sh`/`verify-m8.sh` comments name and route around via per-milestone subprocess grouping. The auditor replicated every pytest invocation from `scripts/verify-{g1,g2,g3,m2,m3,m4,m5,m6,m7,m8}.sh` (G1 skipped — live Docker/compose integration gate, not a pytest slice, infra-dependent, not run) as separate subprocess calls, plus the handful of test files that exist but appear in **no** verify script (`test_state_worker_{alerts,config,entries_router,sweeps,transitions,main,db}.py`, `test_state_worker_routers_*.py`, `test_anthropic_batch_errors.py`, `test_batch_custom_id.py`, `test_batch_poller_{anthropic_client,config}.py`, `test_index_policy.py`, `test_service_stubs.py`, `test_state_worker_{enums,models}.py`, `test_verify_{g1,g2,m2}.py`) and the M8-declared-but-verify-m8-omitted files (`test_state_worker_reading_status.py`, `test_state_worker_permanent_fail.py`, `test_verify_m8.py`, `test_query_api_routes_entry_actions.py`, `test_ui_escalations.py`, `test_ui_explorer.py`, `test_compose.py`).

**Unique test count (`pytest tests/ --collect-only -q`):** 744 tests.

**Result under proper per-slice isolation:** **740 passed, 1 failed, 3 skipped** (deliberate opt-in skips, none of which are gate holes: `test_g5_quality_gate.py`'s live-embedding case gated behind `BISHOP_G5_LIVE`, `test_g6_enrichment_sampling.py`'s manual-checklist case gated behind `BISHOP_G6_MANUAL`, and `test_scraper_adapters_lesswrong.py`'s live-probe case gated behind `BISHOP_LESSWRONG_PROBE_LIVE` — all three env vars unset). Corroborated by an independently dispatched full-suite run (same per-file subprocess isolation strategy, different tmp-runner implementation): identical 744/740/1/3 breakdown, identical single failure.

**`scripts/verify-m8.sh` run directly** (`bash scripts/verify-m8.sh`): **exit 0**, 98 passed / 1 skipped (the LessWrong live probe) across its four internal slices (9-file scraper/adapter/loop/config block, G5 fixture wrapper, G6 prefilter gold, G6 enrichment structural pair) — corroborated independently. This is the M8 gate as declared, and it is green; the one failing test is invisible to it precisely because `tests/test_scraper_adapters.py` is outside every slice it runs (see F3).

**The one failure:**

```
tests/test_scraper_adapters.py::test_registry_contains_only_arxiv
    def test_registry_contains_only_arxiv() -> None:
        _, registry, _ = _load_adapters_stack()
>       assert len(registry.ADAPTER_REGISTRY) == 1
E       AssertionError: assert 7 == 1
E        +  where 7 = len([<class 'app.adapters.arxiv.ArxivAdapter'>, <class 'app.adapters.github.GitHubAdapter'>,
             <class 'app.adapters.huggingface.HuggingFaceAdapter'>, <class 'app.adapters.lesswrong.LessWrongAdapter'>,
             <class 'app.adapters.openreview.OpenReviewAdapter'>, <class 'app.adapters.paperswithcode.PapersWithCodeAdapter'>,
             <class 'app.adapters.semantic_scholar.SemanticScholarAdapter'>])
1 failed in 0.56s
```

This is an M2-era test (`tests/test_scraper_adapters.py`, added at M2 T2, per `CHANGELOG.MD` m2-discovery section) asserting the pre-M8 single-adapter registry state. It is a genuine, reproducible failure against current HEAD, not a collision artifact — confirmed by running it alone. Per the skill's mandatory clause:

```
Finding
Severity:  critical
Type:      contract-violation
Phase:     2 — test execution
Evidence:  assert 7 == 1 (tests/test_scraper_adapters.py::test_registry_contains_only_arxiv), reproduced standalone
Action:    audit continues to surface all findings; verdict is fail regardless of other phases
```

**F2** below. Every other slice, including every M8-specific file (`scripts/verify-m8.sh`'s own pytest block, plus the six T5/T6 files it omits, plus `test_compose.py`), passed cleanly in isolation.

---

## Findings table

| ID | Severity | Type | Phase | Subtask | Description |
|---|---|---|---|---|---|
| F1 | major | contract-violation | 2 / 0 | T2 (owner), never absorbed by T3/T8-bis/orchestrator | `HUGGINGFACE_TOKEN` never lands as a typed `app/config.py` surface; declared test never written; HF adapter reads env at call-site only |
| F2 | **critical** | contract-violation (mandatory Phase-2 clause) | 2 | T8-bis (registry expansion), orchestrator (root cause) | `tests/test_scraper_adapters.py::test_registry_contains_only_arxiv` fails against the 7-adapter registry; file was scout-flagged `direct`/"Extend per adapter" but never assigned to any subtask's Files-to-touch |
| F3 | major | process-violation | 2 | T8-bis / orchestrator | `scripts/verify-m8.sh` (the M8 gate) never runs the T5/T6 M8 contract tests it is supposed to gate |
| F4 | major | contract-violation | 2 | T8-bis (disclosed) | Compose image tags `scraper`/`ui` not bumped to `m8` per plan §2 Naming contract; fully disclosed in decision log with a named landing gate |
| F5 | minor | observation | 2 | T6 | query-api hardcodes reading-status literals instead of importing `ReadingStatusEnum`; values currently match |
| F6 | observation | intent-drift (absorbed) | 3 | T8-bis (disclosed) | Backfill chunk windows overlap (superset), not disjoint — adapter interface has no `until`; disclosed with rationale + landing gate |
| F7 | observation | process (disclosed) | 3 | T8-bis (disclosed) | `.dev/architecture/bishop/` refresh partial; several files explicitly flagged stale in `INDEX.md` with a named landing gate |
| F8 | observation | absorbed (charter-waived) | 0/3 | T7 / owner | G6 Call 1 `challenge_hooks` quality debt (3/10 kept rejects) — explicit owner waiver 2026-09-10, follow-up ID `g6-call1-hooks-iteration` named |

---

## Detailed findings

### F2 — critical — stale registry test fails against T8-bis's 7-adapter merge

**Expected:** the full project test suite passes at the milestone's closing SHA (§8.1-equivalent gate).
**Found:** `tests/test_scraper_adapters.py::test_registry_contains_only_arxiv` (landed M2, per `CHANGELOG.MD`'s m2-discovery section: *"M2 charter limits registry to one adapter despite spec §10.2"*) hard-asserts `len(ADAPTER_REGISTRY) == 1` and `ADAPTER_REGISTRY[0] is ArxivAdapter`. T8-bis's registry merge (7 adapters) makes this assertion false. Reproduced standalone: `assert 7 == 1`.
**Root cause (Phase 1 map-to-plan):** the context map's §File map explicitly lists `tests/test_scraper_adapters.py` as `direct` scope with rationale *"Extend per adapter"* — i.e., the scout correctly predicted this file needed a change during M8. No plan §4 Files-to-touch list (T1/T1-bis/T2/T3/T4/T8/T8-bis) includes it, and plan §0 does not document why the scout's flag was dropped. This is a `prediction-divergence` against the orchestrator (scout said direct; plan silently declined) that manifested as a live regression because no subtask was ever authorized to touch the file.
**Compounding gap:** the plan's own declared *positive* coverage test for the new state — `tests/test_scraper_loop.py::test_registry_lists_all_expected_sources` (§2 `ADAPTER_REGISTRY` row) — was also never written. The registry expansion therefore has neither a passing regression test nor its own declared acceptance test.
**Why this wasn't caught earlier:** `scripts/verify-m8.sh` never references `tests/test_scraper_adapters.py`; T8-bis's own self-check ran only the file list in that script. This is the exact scenario the auditor-review skill's Phase 2 rationale describes: *"A regression introduced by a later subtask will appear here and not in the executor's self-check."*
**Action:** must be fixed before merge — either delete/rewrite the stale assertion (file is not in any subtask's Files-to-touch today, so this needs an explicit Files-to-touch grant) and/or add the declared `test_registry_lists_all_expected_sources`.

### F1 — major — `HUGGINGFACE_TOKEN` typed-surface admission never landed

**Expected:** plan §2 declares `HUGGINGFACE_TOKEN` as a T2-owned row: `services/scraper/app/config.py`, optional `str | None`, test `tests/test_scraper_config.py::test_huggingface_token_from_env`.
**Found:** `services/scraper/app/config.py` defines `GITHUB_TOKEN` and `SEMANTIC_SCHOLAR_API_KEY` (T3) but not `HUGGINGFACE_TOKEN`. The HF adapter's `_auth_headers()` (`services/scraper/app/adapters/huggingface.py:47`) reads `os.environ.get("HUGGINGFACE_TOKEN")` directly. `tests/test_scraper_config.py` has no `test_huggingface_token_from_env` (confirmed via `rg` across the full test list). This is exactly the skill's "runtime env/getattr default that satisfies contract narrative without typed admission" pattern.
**Provenance is unusually clean for this one:** T2's own CHANGELOG entry explicitly disclosed the gap at the time — *"Deferred: `HUGGINGFACE_TOKEN` typed constant on `app/config.py` + `test_scraper_config.py::test_huggingface_token_from_env` blocked by Files-to-touch; landing gate = orchestrator amendment."* T3 hit the identical situation for its own two tokens and self-healed via documented "positive drift" (touched `config.py` + `test_scraper_config.py` although not in Files-to-touch, citing precedent). T8-bis did the same for its **own** three new backfill env keys, explicitly citing "T3 precedent" in both its decision log and CHANGELOG entry. Neither T3's nor T8-bis's positive-drift pass absorbed T2's still-open `HUGGINGFACE_TOKEN` item, and no amendment subtask (T1-bis, T8-bis — the two amendment rounds that existed) picked it up. The named "landing gate = orchestrator amendment" from T2's own changelog entry never fired.
**Action:** should be fixed before merge — add `HUGGINGFACE_TOKEN` to `app/config.py` and the declared test, following the T3/T8-bis positive-drift precedent already established twice in this same plan.

### F3 — major — `verify-m8.sh` does not run the T5/T6 M8 test surfaces it is supposed to gate

**Expected:** `scripts/verify-m8.sh` is plan §2's declared "M8 pytest gate script."
**Found:** the script (read directly) runs only: the six scraper-adapter test files + `test_scraper_loop.py` + `test_scraper_backfill_chunking.py` + `test_scraper_config.py`, then `run-g5-quality-gate.sh`, then `test_g6_prefilter_gold.py`, then two named G6 structural test IDs. It never references `tests/test_state_worker_reading_status.py`, `tests/test_state_worker_permanent_fail.py`, `tests/test_query_api_routes_entry_actions.py`, `tests/test_ui_escalations.py`, `tests/test_ui_explorer.py`, or its own `tests/test_verify_m8.py` — all of which are §2-declared test surfaces for T5's and T6's contract rows (reading-status PATCH, permanent-fail POST, the three query-api proxies, `/escalations`, `/explorer`).
**Independently verified all six files pass** when run directly (17 + 12 + self-consistent `test_verify_m8.py` — see Phase 2 above), so this is not a hidden regression; it is a **gate-completeness gap**. As shipped, `scripts/verify-m8.sh` cannot, on its own, prove that T5's and T6's new routes/UI work — a future regression on those surfaces would ship silently past the milestone's own named verification command.
**Action:** should be fixed before merge — extend `verify-m8.sh`'s pytest invocation(s) to include the T5/T6 M8 test files (and itself).

### F4 — major (disclosed) — compose image tags not bumped

**Expected:** plan §2 Naming contract: `bishop/scraper:m8`, `bishop/ui:m8`.
**Found:** `docker-compose.yml` still reads `bishop/scraper:m2` and `bishop/ui:m7`. `docker-compose.yml` **is** in T8-bis's Files-to-touch (it was edited — three new env keys were added to the scraper block), so this is not an out-of-scope omission; the tag lines specifically were reverted.
**This is the one disclosed residual named in the task brief**, and it is disclosed cleanly in T8-bis's own decision log and CHANGELOG entry: bumping the tags breaks `tests/test_compose.py::test_image_tags_use_milestone_convention` (verified live by T8-bis per its own log: *"25/26 test_compose.py cases pass, only the tag-mapping case fails"*), and `tests/test_compose.py` is not in T8-bis's Files-to-touch, so editing it to accommodate the bump would itself violate scope discipline. T8-bis names an explicit landing gate: a future packet/amendment that puts **both** `docker-compose.yml` and `tests/test_compose.py` in Files-to-touch together. Filed as major per the plan's own literal Naming-contract clause (this is still an unmet §2 row, and disclosure doesn't retroactively satisfy a contract), but the remediation path is already fully scoped and low-risk, unlike F1–F3.

### Minor / observation findings (F5–F8)

- **F5:** `services/query-api/app/routers/entries.py::ReadingStatusPatchBody` hardcodes `READING_STATUS_VALUES = frozenset({"unread","reading","read","archived"})` rather than importing `ReadingStatusEnum` from the state-worker package. Values match today (verified against `services/state-worker/app/enums.py`); flagged as a duplication/drift risk, not a defect.
- **F6:** `compute_backfill_chunk_starts` / `_run_backfill_chunks` produce overlapping (superset-minus-earlier-days), not disjoint, chunk windows, because `SourceAdapter.fetch_manifest` has no `until` parameter. Explicitly disclosed in T8-bis's decision log with full reasoning and a named landing gate (future packet naming `adapters/base.py` + all seven adapters). Absorbed divergence — see §Divergence log below.
- **F7:** `.dev/architecture/bishop/` refresh is partial (module-map/coupling-surfaces/dependency-graph/changelog/INDEX refreshed; several other files explicitly flagged stale in `INDEX.md`). Disclosed with a named landing gate (next `project-architecture` pass or M9 kickoff).
- **F8:** G6 enrichment Call 1 quality debt (3/10 `challenge_hooks` rejects: `arxiv:2606.09483`, `arxiv:2608.14509`, `arxiv:2606.27330`) is an explicit, dated owner waiver (Ale, 2026-09-10) with a named follow-up (`g6-call1-hooks-iteration`). Independently reproduced: running `BISHOP_G6_MANUAL=1 pytest tests/test_g6_enrichment_sampling.py` fails exactly at slot 6 (`arxiv:2606.09483`) as expected — confirms the manual-checklist falsifier is correctly wired and the waiver is real, not papered over.

---

## Phase 3 — Decision log audit

All four architectural-tier decision logs (T1-bis, T4, T5, T8-bis) were read in full. Findings:

- **Chosen approach vs. code:** all four match the implementation read directly (T1-bis's 7-day/60-day independence claim verified via `arxiv.py`/`app/config.py` being byte-identical pre/post except in files T1-bis actually lists; T4's LessWrong GET-only claim verified against `lesswrong.py` and its falsifier test; T5's 404/409/422 envelope verified against `transitions.py`/`entries.py`; T8-bis's registry/chunking/verify-m8 claims verified directly).
- **Rejected alternatives actually avoided:** confirmed for all four — no partial implementation of a rejected approach was found (e.g., T8-bis's rejected "unconditional per-cycle chunking" is correctly gated on `last_successful_run_at is None`, verified in `loop.py` and by the falsifier test `test_scrape_adapter_backfill_enabled_but_warm_start_stays_incremental`).
- **Deferred items actually deferred (not silently absorbed):** confirmed — Call 1 hook iteration, OpenReview PDF full-text, disjoint-window chunking, architecture-folder full refresh, and the compose tag bump are all still genuinely open, matching their decision-log "Items deferred" sections. No silent scope absorption found.
- **`narrative-concealment` check against the pinned cold read:** **none of the cold-read findings were concealed** — items 1, 3, and 4 from the cold-read log are independently and more precisely disclosed in the T2 CHANGELOG entry and the T8-bis decision log respectively (with named landing gates for #3), which the auditor read *after* pinning the cold read. Item 2 (the stale registry test) is **not** mentioned in any decision log or changelog entry — this is the one genuine gap between "what the executors self-reported" and "what's actually true," but it reads as a genuine miss (nobody grepped for the old test) rather than a concealment, since T8-bis's log is otherwise unusually forthcoming about every other residual it left behind.
- **Order-sensitive prose sweep:** T1-bis's decision log states `arxiv.py`/`app/config.py` are "byte unchanged" for its own diff — verified true for T1-bis's commit specifically; a later commit (T8-bis) did touch `app/config.py` (adding the three backfill env keys), which does not contradict T1-bis's claim (scoped to T1-bis's own diff) but is worth noting for a future reader skimming only T1-bis's log in isolation. Not filed as a finding — the claim is accurate as written and not superseded prose describing current-state.

---

## Phase 4 — Adversarial testing / Integration seams (mandatory)

Focus areas: **Integration seams** (mandatory), **Regression surface**, **Contract compliance**. Seeded from context-map §Coupling surfaces (C1–C5) and plan §5.4.

| Coupling | Status | Adversarial check performed | Result |
|---|---|---|---|
| C1 — `ADAPTER_REGISTRY` ↔ content-scraper `adapter_resolver` (fetch_content must ship with every manifest adapter) | confirmed | Read all 7 adapter modules directly; T8-bis decision log states it grepped for `fetch_content` before merging — independently confirmed present on all 7 classes | **passes** |
| C2 — state-worker hub ↔ query-api ↔ UI (UI never calls state-worker directly) | confirmed | Read `services/ui/app/main.py` in full — every call goes through `_query_api_request`/`QUERY_API_URL`; `STATE_WORKER_INTERNAL_PORT` is imported only for a port-arithmetic constant, never used to construct a request | **passes** |
| C3 — `reading_status` SQLite vs. DuckDB mirror staleness (suspected; disprove condition: DuckDB-only filter retained) | suspected → disproved | Read `search.py`: `reading_status is not None` branches to `sqlite_filter_source_ids(...)`, never the DuckDB path; confirmed by the existing mutation-checked falsifier `test_run_search_reading_status_uses_sqlite_not_duckdb` | **ruled out** (mitigation correctly implemented — recorded as observation, not a finding) |
| C4 — `SOURCE_RATE_LIMITS` must exist before `failure_envelope` indexes it (KeyError risk) | confirmed | `rate_limit.py` has all 7 `SourceEnum` keys; each adapter class binds `rate_limit = SOURCE_RATE_LIMITS[...]` at class-definition time (import-time failure, not silent runtime `KeyError`) if a key were missing | **passes** |
| C5 — G4/G5/G6 manual gates (M7 handoff open) | resolved via v1.3 waiver | G4 spot-checked directly against the live read-only SQLite DB per `.cursor/rules/bishop-sqlite.mdc` (`mode=ro`); G5 fixture test passes; G6 enrichment template + manual-checklist falsifier reproduced exactly as documented (7/10, slot 6 fails when `BISHOP_G6_MANUAL=1`) | **passes** (charter-compliant, fully disclosed) |

**Frozen-adjacent paths falsifier (T1-bis/T7/T8-bis's own repeated kill criterion):** `git diff 5e048337b9b7262c604dfce04f3e565d33cf0f4a -- config/index_policy.yaml bishop_shared/index_policy.py config/sources/arxiv.yaml bishop_shared/source_config.py bishop_shared/profile_renderer.py config/profiles/professional_v1.2.0.yaml config/profiles/professional_v1.0.0.yaml eval/prefilter_v1/{contract,items,labels}.json scripts/{replay_prefilter,build_eval_v1,apply_adjudication}.py tests/{test_index_policy,test_g5_quality_gate}.py` reproduced independently: **empty**. All three subtasks that carried this kill criterion honored it through the entire plan.

**Regression surface (this milestone's actual highest-risk area, per Phase 2):** the naive full-suite run surfaced 79 apparent failures; systematic re-run under the project's own per-milestone isolation convention resolved all but one to `sys.modules` collision artifacts (not real regressions) — see F2 for the one genuine regression.

---

## Phase 5 — Coverage gap analysis

- `ADAPTER_REGISTRY`'s declared acceptance test (`tests/test_scraper_loop.py::test_registry_lists_all_expected_sources`) does not exist — coverage-gap, folded into **F2**.
- `HUGGINGFACE_TOKEN`'s declared test (`tests/test_scraper_config.py::test_huggingface_token_from_env`) does not exist — coverage-gap, folded into **F1**.
- No kill criterion across T1-bis/T2/T3/T4/T5/T6/T7/T8-bis was found to lack test coverage where the plan claimed automated coverage; the kill-criterion / coverage-scope-contradiction check (§ "no integration tests... manual only" pattern) did not fire — this milestone's declared-manual items (G6 enrichment judgment, G5 live probe, LessWrong live probe) are each correctly gated behind explicit opt-in env vars with matching skip/xfail wiring, not silently undertested.
- Test-quality spot check: the mutation-checked falsifiers cited in decision logs and CHANGELOG entries (`test_backfill_config_and_incremental_window_stay_independent`, `test_fetch_manifest_uses_get_and_hits_declared_url`, `test_run_search_reading_status_uses_sqlite_not_duckdb`, `test_scrape_adapter_cold_start_backfill_disabled_stays_single_incremental_call`) all exist and assert meaningful, non-tautological behavior (verified by reading each test body, not just its name).

---

## Verdict

**`fail`**

Blocking:
- **F2** (critical) — `tests/test_scraper_adapters.py::test_registry_contains_only_arxiv` fails against current HEAD. Per the skill, any full-suite test failure forces `fail` regardless of other phases.
- **F1** (major) — `HUGGINGFACE_TOKEN` typed-surface admission never landed; declared test missing.
- **F3** (major) — `scripts/verify-m8.sh` does not gate the T5/T6 test surfaces it is supposed to gate.
- **F4** (major) — compose image tags unmet vs. plan §2 Naming contract (disclosed, with a named and narrow landing gate — lowest-effort of the four to close).

Everything else audited — all 7 new adapters, the state-worker hub extension, the query-api/UI write proxies, the backfill chunking mechanism, the frozen-adjacent-paths discipline, the G4/G5/G6/G7 gate chain, and every catalogued integration seam — held up under direct code reading, decision-log cross-checking, and live test execution (the 744/740/1/3 test-count breakdown and the `verify-m8.sh` 98/1/exit-0 result were each independently reproduced by a second full-suite run). The four blocking items are narrow, independently well-understood (three of the four already have either a named remediation pattern used twice elsewhere in this same plan, or a fully disclosed landing gate), and do not implicate the milestone's core adapter/hub/backfill architecture. This reads as a milestone that is close to clean, not one with a structural problem — but "close" is not the bar the full-suite gate sets.

---

## §Divergence log entry

Conditions for writing this section (intent-drift findings at minor/observation severity, absorbed, under a pass/pass-with-conditions verdict) are **not** met — this audit's verdict is `fail`. No divergence-log entry is written this revision. If a follow-up re-audit reaches `pass` or `pass-with-conditions`, F6 (overlapping backfill chunk windows) is the candidate absorbed-intent-drift entry for `.dev/architecture/bishop/architectural-decisions-divergence.md` at that time.

---

## Scout-prediction reconciliation

| Scout prediction | Type | Description (verbatim/paraphrased) | Outcome | Finding ID |
|---|---|---|---|---|
| `services/scraper/app/adapters/registry.py` — direct, "Expand beyond `[ArxivAdapter]`" | file-map | §File map row | verified | — |
| `services/scraper/app/adapters/*.py` — direct, "T2–T4 new modules + tests" | file-map | §File map row | verified | — |
| `services/scraper/app/rate_limit.py` — direct, "Appendix B all sources" | file-map | §File map row | verified | — |
| `services/scraper/app/config.py` — direct, "Backfill windows, schedules, chunking" | file-map | §File map row | verified (chunking/backfill landed) / **partially missed** (HUGGINGFACE_TOKEN never landed here) | F1 |
| `bishop_shared/scraper_config.py` — direct, "Shared BACKFILL_CONFIG" | file-map | §File map row | verified | — |
| `services/state-worker/app/{routers/entries.py,transitions.py}` — direct, "Hub extension" | file-map | §File map row | verified | — |
| `services/query-api/app/routers/` — direct, "POST/PATCH escalation + reading status" | file-map | §File map row | verified | — |
| `services/ui/app/main.py` + templates — direct, "Escalations, DB explorer, controls" | file-map | §File map row | verified | — |
| `scripts/verify-m8.sh` — direct, "M8 gate (T8)" | file-map | §File map row | verified created, but **incomplete** as a gate | F3 |
| `docker-compose.yml` — direct, "compose tags `bishop/scraper:m8`, `bishop/ui:m8`" | file-map | §File map row | **prediction-divergence** — file touched, tags specifically not bumped | F4 |
| `tests/test_scraper_adapters.py` — direct, "Extend per adapter" | file-map | §File map row | **prediction-divergence** — never assigned to any subtask's Files-to-touch; now a failing test | F2 |
| C1 `ADAPTER_REGISTRY` ↔ `adapter_resolver` | suspected_coupling | fetch_content must land with manifest adapter | verified (confirmed, held) | — |
| C2 state-worker ↔ query-api ↔ ui | suspected_coupling | UI never calls state-worker directly | verified (confirmed, held) | — |
| C3 `reading_status` SQLite vs. DuckDB | suspected_coupling | post-INDEXED status edits need consistent filter semantics | ruled-out (mitigated as designed) | — |
| C4 `SOURCE_RATE_LIMITS` ↔ `failure_envelope` | suspected_coupling | every new source needs a rate-limit entry first | verified (confirmed, held) | — |
| C5 G4/G5/G6 manual gates | suspected_coupling | owner sign-off before backfill enable | verified (resolved via documented v1.3 waiver) | — |
| Ambiguity flag 1 (reading_status write path) | ambiguity_flag | no §9.1 route today | resolved as frozen in plan §0, verified in code | — |
| Ambiguity flag 2 (permanent-fail) | ambiguity_flag | no operator action route | resolved as frozen, verified in code | — |
| Ambiguity flag 3 (LessWrong API) | ambiguity_flag | §23 defer trigger | resolved — probe succeeded, adapter implemented + registered, verified | — |
| Ambiguity flag 4 (ArXiv backfill window 7 vs. 60) | ambiguity_flag | M2 default vs. §18.2 | resolved — verified independence of both constants in code | — |
| Ambiguity flag 5 (DB explorer scope) | ambiguity_flag | spec page vs. charter "full UI" | resolved — `/explorer` implemented against existing `/search` params, verified | — |
| Ambiguity flag 6 (Mark Resolved) | ambiguity_flag | explicit non-goal | not-tested (correctly out of scope; no code found implementing it) | — |

---

## §Milestone handoff (charter-governed)

**`audit_status: blocked`**

**Blocking finding IDs:** F1 (major), F2 (critical), F3 (major), F4 (major).

**`landed_contracts`** (symbol + owning file only, no definitions pasted):

- `BackfillConfig`, `BACKFILL_CONFIG`, `SOURCE_SCHEDULE_INTERVAL_SEC` — `bishop_shared/scraper_config.py`
- `SOURCE_RATE_LIMITS` (7 sources) — `services/scraper/app/rate_limit.py`
- `BISHOP_BACKFILL_ENABLED`, `BISHOP_BACKFILL_CHUNK_DAYS`, `BISHOP_BACKFILL_INTER_CHUNK_DELAY_SEC`, `GITHUB_TOKEN`, `SEMANTIC_SCHOLAR_API_KEY` — `services/scraper/app/config.py` (**`HUGGINGFACE_TOKEN` declared in charter/plan §2 but NOT landed — see F1**)
- `HuggingFaceAdapter` — `services/scraper/app/adapters/huggingface.py`
- `PapersWithCodeAdapter` — `services/scraper/app/adapters/paperswithcode.py`
- `SemanticScholarAdapter` — `services/scraper/app/adapters/semantic_scholar.py`
- `GitHubAdapter` — `services/scraper/app/adapters/github.py`
- `OpenReviewAdapter` — `services/scraper/app/adapters/openreview.py`
- `LessWrongAdapter` — `services/scraper/app/adapters/lesswrong.py` (registered, per verified live-probe decision log)
- `ADAPTER_REGISTRY` (7 sources) — `services/scraper/app/adapters/registry.py`
- `compute_backfill_chunk_starts`, `_run_backfill_chunks` — `services/scraper/app/loop.py`
- `ReadingStatusPatchRequest/Response`, `PermanentFailPostRequest/Response` — `services/state-worker/app/models/http.py`
- `PATCH /entries/{source_id}/reading-status`, `POST /entries/permanent-fail` — `services/state-worker/app/routers/entries.py` + `transitions.py`
- query-api proxies for retry / permanent-fail / reading-status — `services/query-api/app/routers/entries.py`
- UI `/escalations`, `/explorer`, entry-detail reading-status control — `services/ui/app/main.py`
- `scripts/verify-m8.sh` — declared M8 gate (**landed but incomplete relative to its own §2 test-surface declaration — see F3**)
- G6 prefilter gold binding — `tests/test_g6_prefilter_gold.py` (consumes landed `eval/prefilter_v1`, ≥129 items confirmed)
- G6 enrichment sampling — `.dev/quality/g6-enrichment-template.md` + `tests/test_g6_enrichment_sampling.py` (assessed 7/10, owner-waived, reproduced)

**Charter cross-check:** every M8 charter-block row (adapter registry expansion; escalation panel retry/permanent-fail; reading-status update; backfill config; G7 backfill/e2e exit; pre-filter and enrichment quality gates; escalation panel functional; G4/G5/G6 entry gates) has a landed counterpart above **except** the `HUGGINGFACE_TOKEN` sub-row of the adapter/config surface (F1) and the compose-tag half of the Naming-contract row (F4), both filed as findings above, not silently passed. No charter-block row is absent from `landed_contracts` without a corresponding finding.

**Waiver table (none — verdict is `fail`, not `accepted-with-waivers`):** N/A. If this becomes an `accepted-with-waivers` disposition on a future revision after F1–F3 are fixed, F4 is the standing candidate for a named waiver entry (finding ID F4, accepted residual risk: compose tags remain at prior milestone values until a follow-up packet lands `docker-compose.yml` + `tests/test_compose.py` together).

---

## Closure ceremony

Not applicable — verdict is `fail`, not `pass`/`pass-with-conditions`. No plan bytes are named to flip. `plan.md` §8 should remain `audit_status: not_run` until a re-audit follows amendment work on F1–F4; do not hand-flip it to `blocked` outside a re-audit revision, since the current text ("Plan is pre-execution... §8 will be recorded... after all subtasks complete and scripts/verify-m8.sh passes on a clean tree") is itself accurate as written and does not need correction — it correctly predicted that §8 would only be written after a real verification pass, which is what this audit is.
