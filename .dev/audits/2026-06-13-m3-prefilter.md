# Audit Report — m3-prefilter

**Audit document revision:** 1 (initial)  
**Date:** 2026-06-13  
**Plan version:** 1.0  
**Audit HEAD:** `1d2a89d2d2d734880a88eb145092da74254cefca` (implementation anchor)  
**Auditor focus areas:**
1. **Integration seams** (mandatory) — seeded from context-map §Coupling surfaces and plan §5.4 (C1–C5): state-worker batch lifecycle ↔ pre-filter register ↔ batch-poller results POST; compose profiles volume overlay; batch_id UUID consistency.
2. **Failure paths** — Anthropic submit vs state-worker register ordering; hash mismatch abort; results POST non-2xx skip PATCH; timeout vs in-flight Anthropic batch.
3. **Edge cases** — malformed JSON decision parsing; G3 dev bypass env; lock-state sweep race (C5).

---

## 1. Audit metadata

| Field | Value |
|-------|-------|
| Task | M3 — Pre-filter Slice (`pre-filter-worker`, `batch-poller` v1, NL profile, state-worker batch API) |
| Charter slice | `.dev/bishop_program_charter.md` L235–282 |
| Context map | `.dev/plans/m3-prefilter/context-map.md` — readiness **CONDITIONAL** at scout time |
| Scout SHA | `6d36e7355044a76158dea1bf5f641f780c490c60` |
| Implementation SHA | `1d2a89d2d2d734880a88eb145092da74254cefca` |
| Provenance | **Diverged** — six implementation commits (`e07d285`…`1d2a89d`) post-scout |
| Scout working tree | **clean** |
| Audit working tree | **dirty** — `M .dev/plans/m3-prefilter/plan.md`; `?? .dev/plans/m3-prefilter/handoff.md` |
| Phase 0 discipline | Completed before narrative artifacts (task statement + §2 only, then code/tests) |
| Re-audit | No — initial audit |

---

## 2. Provenance log

### SHA comparison

| Check | Result |
|-------|--------|
| Scout SHA vs implementation HEAD | **Diverged** (`6d36e73` → `1d2a89d`) |
| Expected | Yes — entire M3 surface landed post-scout |

**`context-map-stale` (major, F-001):** All `direct` rows in context-map §File map (`services/pre-filter-worker/`, `services/batch-poller/`, `config/profiles/`, `bishop_shared/profile_renderer.py`, `bishop_shared/anthropic_config.py`, state-worker batch routes, Alembic `m3_001`, M3 tests, compose `:m3` tags) diverged from scout SHA. Scout listed stubs and absent paths; implementation now exists. Findings against scout `suspect_modified` predictions and ambiguity flags are **stale-qualified** — outcomes verified against `1d2a89d`, not scout-time absence.

### Working-tree state

| Check | Result |
|-------|--------|
| Scout-time dirty paths | None (clean) |
| Audit-time dirty paths | `plan.md` modified (§8 back-reference); `handoff.md` untracked |

### Scout grep coverage

Context-map §Coupling surfaces recorded patterns for: Pydantic batch models, `STATE_WORKER_URL`, `canonical_hash`, `profile_render_hash`, manifest/batch wire strings, Anthropic model string, profile path literals, `pre_filter`, image tags, decision-log paths. Plan §5.4 hidden couplings use the same vocabulary. **No `scout-incomplete` gaps** identified.

### Plan-artifact provenance (`git show 1d2a89d:<path>`)

| Artifact | At `1d2a89d` | On disk @ audit | Notes |
|----------|--------------|-----------------|-------|
| `.dev/plans/m3-prefilter/context-map.md` | present | present | Scout SHA stale |
| `.dev/plans/m3-prefilter/plan.md` | present | present (modified) | §8 still "Deferred" at `1d2a89d`; working tree adds handoff pointer |
| `.dev/plans/m3-prefilter/handoff.md` | **absent** | present | Canonical §8.1–§8.6 for auditor |
| `.dev/plans/m3-prefilter/packets/T1.md` … `T6.md` | present | present | |
| `.dev/decision-logs/m3-prefilter/T2-profile-renderer.md` | present | present | |
| `.dev/decision-logs/m3-prefilter/T3-batch-lifecycle-api.md` | present | present | |
| `.dev/plans/m2-discovery/handoff.md` | present | present | M3 entry gate |
| `bishop_spec_0_6.md` | present | present | |
| `CHANGELOG.MD` | present | present | M3 T1–T6 section |
| `scripts/verify-g3.sh`, `scripts/verify-m3.sh` | present | present | |
| `scripts/seed-profiles.sh`, `.ps1` | present | present | |
| Implementation paths (§8.2 table) | present | present | Verified via diff `6d36e73..1d2a89d` |

**Findings filed in Phase 0.5:** F-001, F-002

---

## 3. Context chain completeness

| Artifact | Provided | Limits |
|----------|----------|--------|
| Context map | Yes | Stale vs implementation SHA |
| Task statement / §2 contracts | Yes | Phase 0 inputs |
| Orchestrator plan (full) | Yes (working tree v1.0 Complete) | §8 back-reference uncommitted at `1d2a89d` |
| Handoff §8 | Yes (working tree) | Not in HEAD |
| Packets T1–T6 | Yes | In HEAD at `1d2a89d` |
| Decision logs T2, T3 | Yes | In HEAD |
| CHANGELOG | Yes | M3 entries present |
| Charter / rationale | Yes | M3 slice L235–282 |
| Codebase | Yes | `6d36e73..1d2a89d` diff reviewed |
| Test suite | Yes | Full suite + M3 gate slice executed at audit time |

Phase 0 completed before consuming decision logs, handoff narrative, CHANGELOG, charter prose, and context-map ambiguity/orchestrator sections.

---

## 4. Cold-read log

Pinned findings from narrative-blind code review (task statement + §2 contracts + implementation + tests only):

| ID | Severity guess | Surface | Finding |
|----|----------------|---------|---------|
| CR-1 | major | `services/pre-filter-worker/app/loop.py` | `prefilter_cycle` submits Anthropic batch **before** `POST /batches`. Registration failure leaves an orphaned external batch with no compensating cancel or retry idempotency key beyond client-generated `batch_id`. |
| CR-2 | minor | `services/pre-filter-worker/app/config.py` | `BISHOP_G3_VERIFIED=1` dev bypass can skip live model verification — misuse in production would violate charter G3 intent. |
| CR-3 | observation | `services/state-worker/app/transitions.py` | `apply_batch_timeout` only resets `RELEVANCE_QUEUED` rows; entries already swept to `DISCOVERED` by lock-state are no-ops — spec G4 race accepted in plan §5.4 C5. |
| CR-4 | minor | `services/batch-poller/app/loop.py` | `parse_pre_filter_response` uses a shallow `\{[^{}]*\}` regex fallback for embedded JSON — nested-object responses may mis-parse (counts as reject per contract). |
| CR-5 | observation | `bishop_shared/profile_renderer.py` | Hash input is full YAML dict minus `canonical_hash` (includes `changelog`, metadata) — not `ProfileDocument` serialization alone; aligns with T2 decision log but differs from naive "§11.2 fields only" reading. |

---

## 5. Findings table

| ID | Severity | Type | Phase | Subtask | Description |
|----|----------|------|-------|---------|-------------|
| F-001 | major | context-map-stale | 0.5 | — | Scout SHA `6d36e73` diverged from implementation `1d2a89d` on all direct-scope files |
| F-002 | major | artifact-not-in-HEAD | 0.5 | T6 | `handoff.md` and plan §8 completion prose not in `1d2a89d` / HEAD |
| F-003 | major | process-violation | 1 | T1/T6 | Charter M3 **exit gate** requires live G3 Messages API verification; handoff records SKIP (no `ANTHROPIC_API_KEY`) |
| F-004 | minor | coverage-gap | 5 | T4 | No automated test for orphaned Anthropic batch after state-worker register failure (behavior documented by `test_prefilter_cycle_state_worker_register_error_skips_after_anthropic` only) |
| F-005 | observation | — | 2 | — | Full suite: pre-existing M1 `test_escalations_returns_flagged_entry_with_error_log` failure (2 error_log rows vs 1) |
| F-006 | observation | — | 5 | T6 | Live `docker compose` e2e deferred per CHANGELOG / handoff — not in `verify-m3.sh` |
| F-007 | minor | — | 2 | T6 | Handoff §8.1 reports 90 M3 gate tests; auditor collection at same paths yields **98** |

---

## 6. Detailed findings (major+)

### F-001 — context-map-stale

**Expected:** Context map provenance matches implementation SHA for direct-scope predictions.  
**Found:** Scout at `6d36e73` predates all M3 commits. File map rows for `config/profiles/`, worker `app/` packages, `bishop_shared/anthropic_config.py`, `profile_renderer.py`, Alembic `m3_001`, and M3 tests were absent or stub-only at scout time.  
**Evidence:** `git diff 6d36e73..1d2a89d --name-only` (58 paths); handoff §8.2 acknowledges staleness.  
**Action:** Re-scout before M4 pre-plan; not a code defect.

### F-002 — artifact-not-in-HEAD

**Expected:** Plan §8 and handoff artifact resolvable at implementation SHA for audit archaeology.  
**Found:** `git show 1d2a89d:.dev/plans/m3-prefilter/handoff.md` → fatal. Plan §8 at `1d2a89d` still reads "Deferred until execution completes." Working tree updates plan §8 and adds `handoff.md` uncommitted.  
**Evidence:** `git status`; `git diff .dev/plans/m3-prefilter/plan.md`; handoff L16–17 self-documents follow-up commit.  
**Action:** Commit `handoff.md` and plan §8 back-reference before merge sign-off (same pattern as M2 F-002).

### F-003 — charter exit gate vs live G3

**Expected:** Charter M3 exit gate (L254, L280): "G3 verified (model string confirmed)" and "model string confirmed via direct API call" before M3 is complete.  
**Found:** `scripts/verify-g3.sh` exits 0 with SKIP when `ANTHROPIC_API_KEY` absent. Handoff §8.1 records no live probe. `verify_model_string()` and mocked tests are implemented; pinned constant matches `claude-haiku-4-5-20251001`.  
**Evidence:** `.dev/bishop_program_charter.md` L254, L280; `scripts/verify-g3.sh` L31–34; handoff §8.1 L63–64; `tests/test_verify_g3.py` (mocked).  
**Action:** Run live G3 once with `ANTHROPIC_API_KEY` set before production deploy, **or** document explicit charter waiver in committed handoff §8.6. Plan T1 intentionally defers live probe in CI — orchestrator should have escalated charter exit wording vs CI policy.

---

## 7. Phase 2 — Test execution

**Working tree:** Implementation code at `1d2a89d`; plan/handoff artifacts dirty (see F-002).

### Full suite

```
Command: python -m pytest tests/ -q --tb=short
Environment: win32, Python 3.14.2, pytest 9.0.2
Result: 262 passed, 1 failed, exit code 1
Failure: tests/test_state_worker_routers_escalations.py::test_escalations_returns_flagged_entry_with_error_log
  AssertionError: assert 2 == 1  (error_log length — extra ALERT row from M1 T8)
```

**Finding:** F-005 (observation) — inherited M1 hygiene; not introduced by M3.

### M3 gate slice

```
Command: python -m pytest tests/test_state_worker_contract.py tests/test_state_worker_health.py tests/test_constants.py tests/test_verify_g3.py tests/test_verify_m3.py tests/test_profile_renderer.py tests/test_prefilter_config.py tests/test_prefilter_client.py tests/test_prefilter_anthropic_client.py tests/test_prefilter_loop.py tests/test_batch_poller_config.py tests/test_batch_poller_startup.py tests/test_batch_poller_loop.py tests/test_state_worker_batches_register.py tests/test_m3_integration.py tests/test_anthropic_config.py -q --tb=line
Result: 98 passed, exit code 0
```

### Contract compliance (§2 summary)

| Contract area | Status |
|---------------|--------|
| Types/interfaces (§2 table) | **Pass** — symbols at declared paths; pydantic models match wire |
| Typed-surface admission (env vars) | **Pass** — `BISHOP_PREFILTER_*`, `BISHOP_BATCH_*`, `STATE_WORKER_URL`, `ANTHROPIC_API_KEY` parsed in config modules with tests |
| Error envelope | **Pass** — `profile_hash_mismatch`, `model_string_fatal`, state-worker 409/404 shapes tested |
| Naming / image tags | **Pass** — `:m3` tags in compose; `test_compose.py` matrix |
| Logging structured fields | **Pass** — `event`, `batch_id`, `source_id`, `entries_reset` used per contract |
| Literal-string parity | **Pass** — model string, route paths, `pre_filter` batch type, poll query params byte-match plan §2 |
| §2 test coverage | **Pass** — every §2 row has named test per handoff §8.3 (auditor spot-checked) |

**Drift vs override:** No contract overrides detected; T2 hash algorithm matches plan Flag 6 resolution.

---

## 8. Phase 3 — Decision log audit

| Log | Chosen approach vs code | Rejected alternatives avoided | Deferred items |
|-----|-------------------------|------------------------------|----------------|
| T2 profile renderer | **Match** — JSON canonical hash excludes `canonical_hash`; hardcoded professional path; seed scripts | Raw YAML bytes hash, prompt hashing, pointer file — not present | G6 quality tuning, personal domain — not implemented |
| T3 batch lifecycle | **Match** — POST/PATCH/timeout, 409 duplicate, DISCOVERED on timeout | UPSERT, RELEVANCE_FAILED, manifest inference at timeout — not present | Registration-time manifest validation — not in state-worker (deferred to T4 integration) |

**Cold-read reconciliation:** CR-1 (orphan batch) acknowledged by `test_prefilter_cycle_state_worker_register_error_skips_after_anthropic` but not in decision logs — acceptable for standard-tier T4; no `narrative-concealment`.

**Order-sensitive prose:** No stale unfenced assertions found in T2/T3 logs.

**Log tier:** T1, T4, T5, T6 standard tier — no decision logs required.

---

## 9. Adversarial test log

### Focus 1 — Integration seams (§Coupling surfaces + plan §5.4)

| Scenario | Expected | Actual | Result |
|----------|----------|--------|--------|
| C1 profiles volume shadows image COPY | Seed scripts or image COPY supply profile at runtime | Dockerfile COPY + `seed-profiles.*` + compose mount documented in T2 log | **passes** |
| C2 batch_id UUID consistent register → results | Same `batch_id` in POST /batches and POST /manifest/pre-filter-results | `prefilter_cycle` generates UUID once; e2e `test_m3_e2e_twenty_entry_batch_pass_and_reject` | **passes** |
| C3 compose tag matrix m0→m3 | Both workers at `:m3` | `docker-compose.yml` L38, L85; `test_compose.py` | **passes** |
| C4 batch-poller sqlite mount | HTTP-only; no direct DB | `grep sqlite batch-poller/` → no matches | **passes** (suspected coupling ruled out) |
| C5 lock sweep vs in-flight batch | Duplicate submit risk per spec G4 | No M3-specific race test; M1 sweep tests exist | **unknown** (accepted prediction) |
| Manifest poll DISCOVERED → RELEVANCE_QUEUED | Claim before batch assembly | `MANIFEST_CLAIM_MAP` in `transitions.py` L46–47; poll client uses `state=DISCOVERED` | **passes** |
| custom_id = source_id | Poller maps results by source_id | `anthropic_batch_client.py` L45; startup uses `batch.source_ids` | **passes** |

### Focus 2 — Failure paths

| Scenario | Expected | Actual | Result |
|----------|----------|--------|--------|
| Hash mismatch at batch time | Abort; no Anthropic call | `_verify_profile_hash` returns None; `test_prefilter_cycle_hash_mismatch_aborts_without_anthropic` | **passes** |
| Anthropic 400 on submit | Log `model_string_fatal`; no register | `submit_pre_filter_batch_or_fatal` returns None | **passes** |
| Register fails after Anthropic submit | Error log; no rollback | Submit then register; test asserts both called — orphan external batch | **passes** (contract silent on rollback; residual risk F-004) |
| Results POST non-2xx | Skip PATCH complete | `loop.py` L209–220 return early | **passes** |
| 48h timeout | POST `/batches/{id}/timeout` | `_handle_timeout` → `post_batch_timeout` | **passes** |

### Focus 3 — Edge cases

| Scenario | Expected | Actual | Result |
|----------|----------|--------|--------|
| Malformed JSON in LLM response | decision 0 + rationale | `parse_pre_filter_response` | **passes** |
| Enrichment batch_type in poller | Rejected | `_is_pre_filter_batch` / `_merge_tracked` guards | **passes** |
| G3 without API key | Block submit (except dev bypass) | `ensure_g3_verified` returns False | **passes** |
| Timeout idempotent | `entries_reset=0` if already timed out | `apply_batch_timeout` L451–456 | **passes** |

---

## 10. Coverage gap list

| Priority | Gap | Kill criterion / source | Mitigation |
|----------|-----|-------------------------|------------|
| High | Live G3 Anthropic probe | Charter exit gate L254, L280 | Run `scripts/verify-g3.sh` with API key (F-003) |
| Medium | C5 lock-sweep vs in-flight batch race | Plan §5.4 C5; no M3 test | Spec G4 caveat accepted; handoff treat-as-prediction |
| Low | Orphan external batch on register failure | CR-1 / adversarial | Documented behavior; no compensating transaction in M3 scope |
| Low | Live docker compose smoke | T6 CHANGELOG deferral | Manual validation per M2 pattern |
| Program | M1 escalations test failure | Inherited | Fix in M1 hygiene cycle (F-005) |

---

## 11. Scout-prediction reconciliation

| Scout prediction | Type | Description (verbatim) | Outcome | Finding |
|----------------|------|------------------------|---------|---------|
| Surface 1 | suspected_coupling | pre-filter poll state DISCOVERED | **verified** | — |
| Surface 2 | suspected_coupling | profile_render_hash must match canonical_hash at batch time | **verified** | — |
| Surface 3 | suspected_coupling | BatchRecord lifecycle vs manifest ingest batch vocabulary | **verified** | POST /batches distinct from manifest batch |
| Surface 4 | suspected_coupling | domain professional on manifest rows | **verified** | hardcoded professional path |
| Surface 5 | suspected_coupling | batch-poller sqlite volume mount | **ruled-out** | HTTP-only poller |
| Surface 6 | suspected_coupling | compose image tag matrix | **verified** | `:m3` both services |
| Surface 7 | suspected_coupling | G2 contract tests gate M3 entry | **verified** | verify-m3 includes G2 slice |
| Surface 8 | suspected_coupling | Anthropic custom_id ↔ source_id | **verified** | custom_id=source_id |
| Flag 1 | ambiguity | Who creates BatchRecord rows at submission time? | **verified** | T3 POST /batches |
| Flag 2 | ambiguity | Timeout manifest processing_state | **verified** | RELEVANCE_QUEUED → DISCOVERED |
| Flag 3 | ambiguity | source_ids on restart | **verified** | m3_001 + wire |
| Flag 4 | ambiguity | Profile repo path vs compose volume | **verified** | seed scripts + COPY |
| Flag 5 | ambiguity | No anthropic/profile code in repo | **verified** | stale-qualified — now present |
| Flag 6 | ambiguity | Hash algorithm JSON vs prompt string | **verified** | JSON canonical per §11.3 |
| Flag 7 | ambiguity | Active profile pointer file | **verified** | hardcoded filename |
| C1–C5 | plan §5.4 | Hidden couplings | See adversarial log | C5 **not-tested** |

---

## 12. Intent traceability (Phase 1 summary)

| Layer | Assessment |
|-------|------------|
| Charter → task statement | **Faithful** — NL profile, workers, G3, batch lifecycle, non-goals preserved |
| Task statement → subtasks T1–T6 | **Complete** — each charter surface mapped to subtask |
| Subtasks → code diff | **Aligned** — packet files-to-touch match diff scope (test files added as expected) |
| Non-goals | **Respected** — no scraper/content/enrichment/vector/query/ui changes |
| Map-to-plan | Scout `direct` files all appear in plan §4; plan §4 additions (e.g. `alembic/m3_001`) documented in orch §0 resolutions |
| Cold-read vs narrative | Handoff §8.5 seeds match CR-1..CR-5; no `narrative-concealment` |

**Intent drift:** F-003 only — charter exit G3 live dimension vs CI SKIP policy (orchestrator/plan vs charter wording).

---

## 13. Verdict

**`pass-with-conditions`**

M3 implementation matches the task statement and §2 shared contracts. The M3 gate slice (**98 passed** at audit time) exercises every §2 row with a named test. Integration seams compose correctly at the unit/integration-test layer: manifest poll claims, batch registration, Anthropic custom_id mapping, poller startup scan, results POST, and timeout enforcement. No critical findings or shipped code contract violations.

**Conditions before M3 merge sign-off / M4 entry:**

1. **F-002 (major)** — Commit `.dev/plans/m3-prefilter/handoff.md` and plan §8 completion prose so `git show HEAD:<path>` resolves.
2. **F-003 (major)** — Close charter G3 **exit** dimension: run live `scripts/verify-g3.sh` with `ANTHROPIC_API_KEY`, **or** add explicit §8.6 waiver in committed handoff naming residual risk (model string validity unproven until live probe).

**Accepted with waiver (see Milestone handoff):**

- **F-001** — context-map staleness; re-scout before M4 pre-plan.
- **F-004** — orphan external batch on register failure; documented skip behavior.
- **F-005** — inherited M1 escalations test failure.
- **F-006** — live Docker compose e2e deferred per plan/CHANGELOG.
- **F-007** — handoff test count typo (90 vs 98); update on commit.

**Upgrade to `pass`:** Resolve F-002 + F-003 (live G3 run or committed waiver).

---

## 14. Milestone handoff (charter M3 → M4 gate)

```yaml
audit_status: accepted-with-waivers
milestone_id: M3
implementation_sha: 1d2a89d2d2d734880a88eb145092da74254cefca
audit_verdict: pass-with-conditions
audit_report: .dev/audits/2026-06-13-m3-prefilter.md
```

### Waivers

| Finding | Accepted residual risk |
|---------|------------------------|
| F-001 | Scout predictions stale; M4 pre-plan must re-explore at fresh SHA |
| F-003 | Model string pinned and mocked-tested; live Anthropic validity unproven until `verify-g3.sh` run with API key |
| F-004 | Orphan external Anthropic batch possible if state-worker register fails after submit; rare; no auto-cancel in M3 |
| F-005 | M1 escalations router test failure does not affect M3 surfaces |
| F-006 | Live compose smoke not automated; manual validation before ops deploy |

### `landed_contracts` (charter cross-check)

Charter L245–250 surfaces vs implementation:

| Charter surface | Landed |
|-----------------|--------|
| `config/profiles/professional_v1.0.0.yaml` + `canonical_hash` | Yes |
| Profile renderer (JSON canonical SHA-256) | Yes — `bishop_shared/profile_renderer.py` |
| `BatchRecord.batch_type = pre_filter`, `profile_render_hash` | Yes — registration wire + tests |
| `batch-poller` startup scan `GET /batches?status=submitted,processing` | Yes — `startup.py` |
| 48-hour `batch_timed_out` timeout | Yes — `BATCH_TIMEOUT_HOURS`, `POST .../timeout` |

**Extended symbols (plan §2, not charter bullet list):**

- `bishop_shared/anthropic_config.py` — `ANTHROPIC_MODEL_PREFILTER`, `verify_model_string()`
- State-worker — `POST /batches`, `PATCH /batches/{batch_id}`, `POST /batches/{batch_id}/timeout`
- `BatchRegisterRequest`, `BatchPatchRequest`, `BatchRecord.source_ids` — `services/state-worker/app/models/`
- `alembic/versions/m3_001_batch_source_ids.py`
- `services/pre-filter-worker/app/` — `prefilter_cycle()`, clients
- `services/batch-poller/app/` — `startup_scan()`, `poll_loop()`
- `scripts/verify-g3.sh`, `scripts/verify-m3.sh`, `scripts/seed-profiles.*`
- Compose `bishop/pre-filter-worker:m3`, `bishop/batch-poller:m3`

**Charter cross-check:** No charter-listed surface missing from `landed_contracts`. No undeclared charter surface shipped.

### M4 entry gate readiness

| Gate | Status |
|------|--------|
| G2 (M1 contract tests) | Green in M3 gate slice |
| G3 (model string) | Code + mocks green; live probe **waived** per F-003 |
| M3 exit (20-entry pass+reject, startup scan, BatchRecord fields) | Green — `test_m3_integration.py`, `test_m3_e2e_twenty_entry_batch_pass_and_reject`, startup scan tests |
| Runnable checkpoint (docker compose) | Code present; live smoke **manual** per F-006 |

---

## 15. Auditor execution notes

```
git rev-parse HEAD  → 1d2a89d2d2d734880a88eb145092da74254cefca
git status --short  → M plan.md; ?? handoff.md
python -m pytest tests/ -q  → 262 passed, 1 failed (M1 escalations)
python -m pytest <M3 gate paths> -q  → 98 passed
git show 1d2a89d:.dev/plans/m3-prefilter/handoff.md  → fatal (not in HEAD)
```

Diff scope reviewed: `git diff 6d36e73..1d2a89d` (commits `e07d285` T1 through `1d2a89d` T6).
