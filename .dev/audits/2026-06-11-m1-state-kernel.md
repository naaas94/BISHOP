# Audit Report — m1-state-kernel

**Audit document revision:** 1 (initial)  
**Date:** 2026-06-11  
**Plan version:** 1.1 (working tree) / 1.0 (HEAD)  
**Audit HEAD:** `2ac1e3cb3da1e4fb427ff19776a9ae77ba7e230c`  
**Auditor focus areas:**
1. **Integration seams** (mandatory) — seeded from context-map §Coupling surfaces; M1 is a multi-router assembly with compose, SQLite path, and lifespan ordering.
2. **Concurrency / ordering** — atomic poll-and-claim and H3 transactions are the charter G2 exit criteria.
3. **Failure paths** — provenance 409, H3 rollback, escalation/failure routing, sweep recovery.

---

## 1. Audit metadata

| Field | Value |
|-------|-------|
| Task | M1 — State Kernel (`state-worker` full implementation) |
| Context map | `.dev/plans/m1-state-kernel/context-map.md` — readiness **CONDITIONAL** at scout time |
| Scout SHA | `8d339ee2cd5dd2b16549bbe556ea995462a53a20` |
| Audit SHA | `2ac1e3cb3da1e4fb427ff19776a9ae77ba7e230c` |
| Provenance | **Diverged** — scout predates all M1 implementation commits |
| Scout working tree | **dirty** at scout (`?? .dev/plans/`, `?? .dev/audits/`) |
| Audit working tree | **dirty** — `M .dev/plans/m1-state-kernel/plan.md` (§8 handoff uncommitted) |
| Phase 0 discipline | Completed before narrative artifacts (task statement + §2 only, then code/tests) |
| Pytest (auditor run) | `147 passed` full suite; `102 passed` state-worker slice; G2 slice passes |
| Re-audit | No — initial audit |

---

## 2. Provenance log

### SHA comparison

| Check | Result |
|-------|--------|
| Scout SHA vs audit HEAD | **Diverged** (`8d339ee` → `2ac1e3c`) |
| Expected | Yes — scout baseline was pre-M1; all implementation files are post-scout |

**`context-map-stale` (major):** Context map §File map rows for `enums.py`, `db.py`, `transitions.py`, `routers/`, `alembic/`, contract tests, etc. were marked "**does not exist**" at scout SHA. Findings against scout `suspect_modified` predictions on those paths are **stale-qualified** — implementation landed as planned, not as scout inventory predicted at read time.

### Working-tree state

| Check | Result |
|-------|--------|
| Scout-time dirty paths in §File map scope | `?? .dev/plans/` only (docs, not implementation code) |
| Audit-time dirty paths | `.dev/plans/m1-state-kernel/plan.md` modified — §8 auditor handoff filled in working tree only |

### Scout grep coverage

Context-map §Coupling surfaces recorded patterns for: `STATE_WORKER_URL`, `/app/data/sqlite`, `/health`, §9.1 route prefixes, `ProcessingState`, `PRAGMA journal_mode=WAL`, retry fields, compose `depends_on`. Plan §5.4 hidden couplings reference the same surfaces. **No `scout-incomplete` gaps** identified for required vocabulary.

### Plan-artifact provenance (`git show HEAD:<path>`)

| Artifact | HEAD | On disk | Notes |
|----------|------|---------|-------|
| `.dev/plans/m1-state-kernel/context-map.md` | present | present | Stale vs implementation |
| `.dev/plans/m1-state-kernel/plan.md` | present | **modified** | HEAD = v1.0 planning + deferred §8 template; disk = v1.1 + filled §8 |
| Packets T1–T6 | present | present | |
| Decision logs T1, T2 | present | present | Architectural tier only (expected) |
| `CHANGELOG.MD` | present | present | M1 section present; T3 line missing |
| `scripts/verify-g2.sh` | present | present | |
| `tests/test_state_worker_contract.py` | present | present | |
| `.dev/plans/m1-state-kernel/handoff.md` | absent | absent | Documented omission; §8 embedded pattern |
| `.dev/changelogs/M1-state-kernel.md` | absent | absent | Root `CHANGELOG.MD` used instead |
| Plan §8 closure SHA | not recorded in HEAD plan | — | Working-tree §8 cites `2ac1e3c` |

**Findings filed in Phase 0.5:** F-001, F-002, F-003

---

## 3. Context chain completeness

| Artifact | Provided | Limits |
|----------|----------|--------|
| Context map | Yes | Stale (pre-implementation SHA) |
| Task statement / §2 contracts | Yes | Phase 0 inputs |
| Orchestrator plan (full) | Yes (working tree v1.1) | HEAD plan incomplete vs disk |
| Packets T1–T6 | Yes | |
| Decision logs T1, T2 | Yes | T3–T6 standard tier — no logs (expected) |
| Changelog | Yes (`CHANGELOG.MD`) | T3 commit not narrated |
| Codebase | Yes | 44 files in `7d38c89..HEAD` diff |
| Tests | Yes | 102 state-worker tests; G2 slice verified |
| Pre-plan / charter | Referenced in plan §0 | Not re-read in full |

Phase 0 completed before plan §3+, decision logs, changelog, and §8 handoff prose.

---

## 4. Cold-read log (Phase 0 — pinned)

| ID | Severity guess | Finding |
|----|----------------|---------|
| CR-01 | major | No `logger.critical` or `alert_type` anywhere in `services/state-worker/` despite plan §2 Logging binding |
| CR-02 | major | `plan.md` §8 auditor handoff claims clean tree at `2ac1e3c`, but `plan.md` itself is uncommitted at audit time |
| CR-03 | minor | No `logger.warning` calls — plan §2 binds WARNING for idempotent no-ops |
| CR-04 | minor | Transition/failure paths log at INFO (`logger.info("transition", ...)`) not ERROR per §2 |
| CR-05 | minor | `invalid_batch_status` error code in `routers/batches.py` not listed in plan §2 error envelope |
| CR-06 | observation | `transitions.py` is ~1150 lines — single-module concentration risk for H3/N3/sweeps |
| CR-07 | observation | `VECTOR_WRITE_QUEUED` poll returns `claimed_count > 0` with `transitioned_to: null` — semantically ambiguous but matches plan §2 claim mapping |
| CR-08 | minor | `content_raw` omission for `VECTOR_WRITE_QUEUED` tested in `test_state_worker_routers_poll.py` but not in `test_state_worker_contract.py` (G2 gate file) |
| CR-09 | observation | `assert_pre_filter_provenance` docstring says "M2" while behavior is enforced in M1 |

---

## 5. Findings table

| ID | Severity | Type | Phase | Subtask | Description |
|----|----------|------|-------|---------|-------------|
| F-001 | major | context-map-stale | 0.5 | — | Scout SHA `8d339ee` predates all M1 implementation at `2ac1e3c` |
| F-002 | major | artifact-not-in-HEAD | 0.5 | T6/handoff | Plan §8 auditor handoff (v1.1, completion snapshot, §8.3 evidence) exists only in working tree; HEAD plan still deferred template |
| F-003 | major | process-violation | 0.5, 1 | T6 | Working-tree §8.1 asserts "git status clean at handoff" — false at audit time (`M plan.md`) |
| F-004 | major | contract-violation | 2 | T2,T5 | Plan §2 Logging requires CRITICAL + `alert_type` per §14.3 — not implemented in code |
| F-005 | minor | contract-violation | 2 | T2 | Plan §2 binds WARNING for idempotent no-ops — no `logger.warning` in state-worker |
| F-006 | minor | contract-violation | 2 | T2 | Plan §2 binds ERROR for transition failures — failures log at INFO |
| F-007 | minor | coverage-gap | 5 | T3,T6 | `content_raw` omission on `VECTOR_WRITE_QUEUED` poll absent from G2 contract file / `verify-g2.sh` slice |
| F-008 | minor | intent-drift | 1 | T3 | `CHANGELOG.MD` omits T3 commit narrative (acknowledged in plan §8.4 working tree) |
| F-009 | minor | contract-violation | 2 | T5 | `invalid_batch_status` error literal not declared in plan §2 error envelope |
| F-010 | observation | prediction-divergence | 1 | T1 | Scout §File map `app/models.py` → landed as `app/models/` package (documented in T1 decision log) |
| F-011 | observation | prediction-divergence | 1 | T3+ | Router unit tests (`test_state_worker_routers_*.py`) added beyond T3 packet files-to-touch — benign test expansion |
| F-012 | observation | coverage-gap | 5 | T5 | T5 kill criterion "compose healthcheck fails 5 consecutive starts" has no automated test; plan §2 defers Docker from G2 — accepted operational risk |

---

## 6. Detailed findings (above minor)

### F-001 — context-map-stale (major)

**Expected:** Scout at M0 handoff SHA before M1 code existed.  
**Found:** Implementation added across six commits (`68e5148`…`2ac1e3c`). Context map §Interface inventory "Planned M1 symbols (not yet in codebase)" is obsolete.  
**Evidence:** Scout header `Commit SHA: 8d339ee`; audit `git rev-parse HEAD` → `2ac1e3c`. Plan §8.2 working tree acknowledges staleness.  
**Action:** M2 pre-plan should re-explore at `2ac1e3c` or accept handoff SHA per plan §8.4.

### F-002 — artifact-not-in-HEAD (major)

**Expected:** Plan §8 auditor handoff committed at closure SHA `2ac1e3c`.  
**Found:** `git show HEAD:.dev/plans/m1-state-kernel/plan.md` shows `Status: Complete (planning)`, `Tree SHA: _(pending)_`, deferred §8 template. Working tree has full v1.1 §8 with test results and evidence tables.  
**Evidence:** `git status` → `M .dev/plans/m1-state-kernel/plan.md`; `git diff HEAD -- plan.md` shows §8 insertion.  
**Action:** Commit plan v1.1 §8 handoff before merge archaeology is considered complete.

### F-003 — process-violation (major)

**Expected:** Handoff §8.1 cleanliness claim matches repository state.  
**Found:** §8.1 (working tree) states "Tracked-tree cleanliness: git status clean at handoff recording" while `plan.md` is modified and uncommitted.  
**Evidence:** Cold-read CR-02; audit `git status --short`.  
**Action:** Amend handoff after commit, or record dirty paths explicitly.

### F-004 — contract-violation (major)

**Expected:** Plan §2 Logging — "CRITICAL for alert_type per §14.3"; spec §14.3 MVP alerts as structured CRITICAL logs with `alert_type` and `error_class = "ALERT"` in `error_log`.  
**Found:** `grep alert_type|CRITICAL|ALERT services/state-worker` → no matches. `record_failure()` writes ErrorLog and logs `logger.info("transition", ...)` only. No alert emission path.  
**Evidence:** `services/state-worker/app/transitions.py` `record_failure` L901–994; plan §2 L110.  
**Classification:** Drift — plan declared binding logging contract; implementation omitted alert surface entirely.  
**Action:** Implement §14.3 alert emission for applicable conditions, amend plan §2 if alerts are explicitly deferred to a later milestone, or add amendment subtask.

---

## 7. Adversarial test log

### Focus 1 — Integration seams (context-map §Coupling surfaces)

| Surface | Scenario | Expected | Actual | Result |
|---------|----------|----------|--------|--------|
| 1 — SQLite mount path | `SQLITE_DB_PATH` aligns with compose volume | `/app/data/sqlite/bishop.db` | `bishop_shared/constants.py` L45–47; `test_sqlite_db_filename` | **passes** |
| 2 — health before migrations | Lifespan runs migrations before serving; compose tolerates startup | Migrations sync before `yield`; `start_period: 30s` | `main.py` L26–29; `docker-compose.yml` L17 | **passes** (Docker E2E not run — unknown for real restart loop) |
| 3 — STATE_WORKER_URL route drift | All §9.1 routes registered | 16 method/path pairs per spec | `test_route_surface_matches_spec` — 0 missing | **passes** |
| 4 — schema coupling | Six §7 tables via Alembic | `manifest`, `entries`, `batches`, `error_log`, `oov_tags_log`, `scraper_state` | `test_alembic_migration_clean_from_empty_db`; migration `m1_001_initial_schema.py` | **passes** |
| 5 — processing_state strings | Enum `.value` matches DB/poll params | Spec §6.1 members | `test_processing_state_members_match_spec`; poll routers use `ProcessingState(state)` | **passes** |
| 7 — M0 route falsifier | `test_only_health_route_exposed` removed | Replaced by contract route surface test | Removed from `test_state_worker_health.py`; `test_route_surface_matches_spec` present | **passes** |
| 8 — sync /health in async app | `/health` non-blocking | Sync handler, no DB | `main.py` L50–52 unchanged pattern | **passes** |

**Suspected surfaces ruled out (per scout):**
- Surface 5 (enum typo duplicate) — single enum in `enums.py`; **ruled out**
- Surface 6 (JSON list encoding) — `domain.py` `to_db_row`/`from_db_row` encode/decode; state-worker owns boundary; **confirmed handled**

### Focus 2 — Concurrency / ordering

| Scenario | Expected | Actual | Result |
|----------|----------|--------|--------|
| Manifest double-poll emptiness | Second poll returns `claimed_count=0`, empty entries after atomic claim | `claim_manifest_poll` uses `BEGIN`→`SELECT`→`UPDATE`→`COMMIT`; `test_manifest_poll_atomic_double_poll_empty` | **passes** |
| Entry claim states | `SCRAPED→ENRICHMENT_STAGE1_QUEUED`, `ENRICHMENT_STAGE2_QUEUED→ENRICHMENT_STAGE2_CLAIMED` | `ENTRIES_CLAIM_MAP` in `transitions.py` L47–50 | **passes** |
| VECTOR_WRITE_QUEUED no claim | `transitioned_to: null` | `claim_entries_poll` L411–428 returns without `BEGIN` | **passes** |
| H3 rollback | Mid-sequence failure leaves row at pre-H3 state | `test_enrichment_stage1_results_rolls_back_on_mid_sequence_failure` | **passes** |
| Sweep does not block event loop | Async sleep only | `test_sweep_loop_does_not_block_event_loop` patches `time.sleep` to fail | **passes** |

### Focus 3 — Failure paths

| Scenario | Expected | Actual | Result |
|----------|----------|--------|--------|
| Provenance incomplete on content POST | `409` + `provenance_incomplete` | `test_post_content_provenance_incomplete_returns_409` | **passes** |
| Unknown source_id | `404` + `not_found` | `test_post_entries_not_found_returns_404` | **passes** |
| Invalid transition | `409` + `invalid_transition` + from/to states | `test_post_content_invalid_transition_returns_409` | **passes** |
| Lock-state sweep recovery | Stuck `RELEVANCE_QUEUED` → `DISCOVERED` | `test_lock_state_sweep_resets_stuck_relevance_queued` (contract) + transitions unit test | **passes** |
| Retry sweep | Failed entry requeued when `next_retry_at` elapsed | `test_retry_sweep_requeues_failed_entry` | **passes** |
| §14.3 alert emission on escalation threshold | CRITICAL log + `alert_type` + ALERT error_class | Not implemented | **fails** (F-004) |

---

## 8. Coverage gap list (prioritized)

| Priority | Gap | Tests exist? | Notes |
|----------|-----|--------------|-------|
| **P1** | §14.3 CRITICAL `alert_type` logging | No | F-004 — plan §2 binding |
| **P2** | `content_raw` omission in G2 gate slice | Yes, outside G2 file | `test_entries_poll_vector_write_queued_omits_content_raw` in routers_poll; not in `verify-g2.sh` modules |
| **P3** | Docker compose healthcheck under migration load | No | Plan defers Docker from G2; T5 kill criterion manual |
| **P4** | WARNING/ERROR log level contracts | No level assertions | F-005, F-006 |
| **P5** | Derived wire model consumer parity (M3/M5) | Contract smoke only | Plan §5.2 "treat-as-prediction" — acceptable for M1 |

**Kill-criterion coverage:** All G2 charter criteria (idempotent ingest, double-poll, H3 atomicity, sweep recovery, Alembic clean) have named tests in `test_state_worker_contract.py` and pass. T5 compose kill criterion is executor-time only — not a G2 charter criterion.

**Interface inventory (stale-qualified):** Scout listed `app`/`health`/`run` with `test_state_worker_health.py` — still valid post-M1. Planned symbols now have extensive test coverage under `test_state_worker_*.py`.

**Ambiguity flags resolution:**

| Flag | Test added? | Status |
|------|-------------|--------|
| 1 enum placement | `test_section_20_enum_members` | Resolved |
| 2 sqlite filename | `test_sqlite_db_filename` | Resolved |
| 3 content_raw omission | routers_poll test; not G2 file | Partial (F-007) |
| 4 partial wire schemas | contract smoke + T1 decision log | Resolved with derived models |
| 5 handoff absent | M0 embedded §8 used | Process accepted |
| 6 batch vocabulary | manifest batch vs BatchRecord separated | Resolved |
| 7 provenance assertion | `test_post_content_provenance_incomplete_returns_409` | Resolved |
| 8 health route falsifier | removed; `test_route_surface_matches_spec` | Resolved |

---

## 9. Intent traceability (Phase 1 summary)

**Task statement → code:** Complete `state-worker` with schema, transitions, sweeps, all §9.1 endpoints, G2 criteria — **landed**. M0 `/health` compatible — **landed**. Non-goals (other services, LanceDB, spec edits) — **respected**.

**Subtask → diff alignment:**

| Subtask | Packet files | Extra files in diff | Assessment |
|---------|--------------|---------------------|------------|
| T1 | Matches + decision log | `models/__init__.py` replaces `models.py` | Documented in T1 log |
| T2 | Matches | — | Aligned |
| T3 | Routers only | `tests/test_state_worker_routers_manifest.py`, `tests/test_state_worker_routers_poll.py` | Benign test expansion (F-011) |
| T4 | Matches | `tests/test_state_worker_entries_router.py` | Benign |
| T5 | Matches | Router tests, `test_state_worker_main.py`, `test_state_worker_sweeps.py` | Benign |
| T6 | Matches | Full router test matrix | Aligned |

**Narrative vs cold-read:** Working-tree §8.4 acknowledges CHANGELOG T3 gap and context-map staleness. §8.1 clean-tree claim does **not** acknowledge CR-01 (alert logging) or CR-02 (uncommitted plan) — **narrative-concealment** subsumed under F-003/F-004.

**Decision logs:** T1/T2 chosen approaches match code (enum placement, `bishop.db`, H3 explicit BEGIN, sweep timestamp proxy, provenance helper). T2 deferred `state_entered_at` — not silently absorbed.

---

## 10. Scout-prediction reconciliation

| Scout prediction | Type | Outcome | Finding |
|------------------|------|---------|---------|
| SQLite mount at `/app/data/sqlite` couples DB path | confirmed coupling | **verified** | — |
| Healthcheck before migrations complete | confirmed coupling | **verified** mitigated | — |
| STATE_WORKER_URL path drift breaks M2+ | confirmed coupling | **verified** routes match spec | — |
| Schema table names couple direct readers | confirmed coupling | **verified** six tables | — |
| processing_state string typo risk | suspected | **ruled out** | enum tests |
| JSON list[str] encoding | suspected | **verified** at boundary | T1 log |
| `test_only_health_route_exposed` blocks M1 | confirmed coupling | **verified** removed | — |
| sync /health vs async DB routes | confirmed coupling | **verified** health sync | — |
| Flag 1 enum placement | ambiguity | **verified** state-worker only | — |
| Flag 2 sqlite filename | ambiguity | **verified** `bishop.db` | — |
| Flag 3 content_raw omission | ambiguity | **verified** in routers_poll; partial G2 | F-007 |
| Flag 4 partial wire schemas | ambiguity | **verified** derived + logged | — |
| Flag 5 handoff absent | ambiguity | **not-tested** process | accepted |
| Flag 6 batch vocabulary | ambiguity | **verified** | — |
| Flag 7 provenance assertion | ambiguity | **verified** | — |
| Flag 8 health falsifier | ambiguity | **verified** | — |
| `app.models.py` direct file | file map | **prediction-divergence** | F-010, T1 log |
| `suspect_modified` on `app` constant | interface | **verified** routers added | stale-qualified |

---

## 11. Verdict

**`fail`**

M1 implementation is functionally strong: **147/147 tests pass**, all G2 charter contract tests pass, intent traceability from task statement through T1–T6 is sound, and integration seams from the context map are handled. Merge is blocked by **process and contract gaps**:

1. **F-002 / F-003** — Auditor handoff §8 is not committed at HEAD; cleanliness claim is inaccurate. Fix: commit plan v1.1 §8.
2. **F-004** — Plan §2 Logging contract for §14.3 CRITICAL `alert_type` alerts is undeclared-absent in code. Fix: implement alert emission or amend plan §2 with explicit deferral.

**Conditions that would upgrade to `pass-with-conditions` after fix:**
- F-001 context-map staleness — expected; re-scout at M2 (no code fix required for M1 merge if handoff SHA recorded)
- F-005, F-006, F-007, F-008, F-009 — minor; address or accept with justification

**Not blocking but recommended before M2:**
- Add `content_raw` omission assertion to G2 contract file (F-007)
- Commit or reconcile CHANGELOG T3 line (F-008)
- Optional Docker smoke on bash host per plan §8.1 note

---

## 12. Auditor execution notes

Commands run at audit time:

```
git rev-parse HEAD  → 2ac1e3cb3da1e4fb427ff19776a9ae77ba7e230c
python -m pytest tests/ -q  → 147 passed
python -m pytest tests/ -k "state_worker or verify_g2 or test_sqlite" -q  → 102 passed
```

Diff scope reviewed: `git diff 7d38c89..HEAD` (44 files, +5636 lines).
