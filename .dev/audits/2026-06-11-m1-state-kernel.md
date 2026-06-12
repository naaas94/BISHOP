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

---

# Audit Report — m1-state-kernel (Revision 2 — Re-audit)

**Audit document revision:** 2 (re-audit)  
**Supersedes verdict of:** Revision 1 (initial, **fail** at `2ac1e3c`)  
**Date:** 2026-06-11  
**Plan version:** 1.2 (HEAD) + §8A append (working tree, uncommitted)  
**Audit HEAD:** `3d1ee2e720eae21d2169eee7c15b279634acf47a`  
**Amendment scope:** T7–T9 (`6581ed7`…`3d1ee2e`) closing revision-1 findings F-002…F-009  
**Auditor focus areas:**
1. **Integration seams** (mandatory) — T8 `record_failure` ↔ `emit_alert` transaction boundary; T8 ALERT row ↔ `GET /escalations` wire shape.
2. **Failure paths** — §14.3 alert dual-write closure (F-004); log-level contracts (F-005/F-006).
3. **Regression surface** — full `pytest tests/` after amendment; adjudicate §8A.4 open escalations coupling.

**Omission-free artifact checklist (revision-1 fail surfaces reviewed):**

| Surface | Opened at re-audit |
|---------|-------------------|
| `.dev/audits/2026-06-11-m1-state-kernel.md` (rev 1) | Yes |
| `.dev/plans/m1-state-kernel/plan.md` (§8 + §8A) | Yes |
| Packets T1–T9 | Yes |
| Decision logs T1, T2, T8 | Yes |
| `services/state-worker/app/alerts.py`, `transitions.py` | Yes |
| `tests/test_state_worker_alerts.py`, `test_state_worker_contract.py` | Yes |
| `tests/test_state_worker_routers_escalations.py` | Yes |
| `CHANGELOG.MD`, `scripts/verify-g2.sh` | Yes |
| Context map | Yes (stale-qualified) |

---

## R2.1 Audit metadata

| Field | Value |
|-------|-------|
| Task | M1 — State Kernel + amendment T7–T9 |
| Context map | `.dev/plans/m1-state-kernel/context-map.md` — **CONDITIONAL**, scout SHA `8d339ee` (stale) |
| Baseline audit SHA | `2ac1e3cb3da1e4fb427ff19776a9ae77ba7e230c` |
| Re-audit SHA | `3d1ee2e720eae21d2169eee7c15b279634acf47a` |
| Provenance | **Diverged** from scout (unchanged from F-001); amendment commits landed |
| Working tree | **dirty** — `M .dev/plans/m1-state-kernel/plan.md` (§8A append only; implementation clean at HEAD) |
| Phase 0 discipline | Cold-read on `alerts.py`, `transitions.py` `record_failure`, alert tests, contract T9 test, escalations router test **before** §8/§8A narrative and amendment packets |
| Pytest (auditor run) | G2+amendment slice: **43 passed**; full suite: **153 passed, 1 failed** |

---

## R2.2 Provenance log

### SHA comparison

| Check | Result |
|-------|--------|
| Scout SHA vs re-audit HEAD | **Diverged** (`8d339ee` → `3d1ee2e`) |
| Baseline audit SHA vs re-audit HEAD | **Diverged** (`2ac1e3c` → `3d1ee2e`) — expected; amendment landed |

**F-001 (`context-map-stale`):** **open** (treat-as-prediction). Scout inventory obsolete; no re-scout in amendment scope. M2 pre-plan should re-explore at `3d1ee2e`.

### Working-tree state

| Check | Result |
|-------|--------|
| Implementation files at HEAD | **clean** |
| Dirty paths | `.dev/plans/m1-state-kernel/plan.md` — §8A re-audit handoff append (126 lines) not in HEAD |

### Plan-artifact provenance (`git show HEAD:<path>` at `3d1ee2e`)

| Artifact | HEAD | On disk | Notes |
|----------|------|---------|-------|
| `.dev/plans/m1-state-kernel/plan.md` v1.2 §8 | present | **modified** | §8A append disk-only → F-015 |
| Packets T7–T9 | present | present | Amendment packets committed at `3d1ee2e` |
| `.dev/decision-logs/m1-state-kernel/T8-alert-logging.md` | present | present | |
| `services/state-worker/app/alerts.py` | present | present | T8 |
| `tests/test_state_worker_alerts.py` | present | present | 6 tests |
| `.dev/audits/2026-06-11-m1-state-kernel.md` rev 1 | present | present | This append adds rev 2 |
| `CHANGELOG.MD` T3/T7/T8/T9 lines | present | present | F-008 closed |

**New findings filed:** F-013, F-014, F-015

---

## R2.3 Context chain completeness

| Artifact | Provided | Limits |
|----------|----------|--------|
| Context map | Yes | Stale (pre-M1 SHA) |
| Plan §2 + §8A cold-read seeds | Yes | §8A on disk only until committed |
| Packets T1–T9 | Yes | |
| Decision logs T1, T2, T8 | Yes | |
| Changelog | Yes | T3 line present |
| Revision-1 audit | Yes | Preserved above |
| Codebase | Yes | `2ac1e3c..3d1ee2e` (+ orch commit) |
| Tests | Yes | Full suite run by auditor |

Phase 0 completed before §8/§8A narrative, T7–T9 packets, and T8 decision log.

---

## R2.4 Cold-read log (Phase 0 — pinned, fresh)

| ID | Severity guess | Finding |
|----|----------------|---------|
| CR2-01 | major | `test_escalations_returns_flagged_entry_with_error_log` asserts `len(error_log)==1`; T8 dual-write produces operational + ALERT rows → full suite fails |
| CR2-02 | minor | `verify-g2.sh` runs contract + health + constants only; does not include `test_state_worker_alerts.py` despite plan §8A.1 command listing alerts in amendment slice |
| CR2-03 | observation | `GET /escalations` returns all `error_log` rows unfiltered — consistent with spec §14.2 "all attempts" + §14.3 ALERT rows; stale test is the defect |
| CR2-04 | observation | `manual_retry` selects `ORDER BY timestamp DESC LIMIT 1` without excluding `error_class='ALERT'`; ALERT rows carry same `state_at_failure` — likely benign but tie-order undefined when timestamps equal |
| CR2-05 | resolved vs rev1 | `alerts.py` implements `logger.critical` + `error_class=ALERT` insert — addresses CR-01/F-004 |
| CR2-06 | resolved vs rev1 | `transitions.py` has `logger.warning` (ingest skip) and `logger.error` (`transition failure`) — addresses CR-03/CR-04/F-005/F-006 |

---

## R2.5 Finding status vs revision 1

| Prior ID | Prior severity | Prior type | Status | Evidence at `3d1ee2e` |
|----------|----------------|------------|--------|------------------------|
| F-001 | major | context-map-stale | **open** | Scout SHA unchanged; expected M2 re-scout |
| F-002 | major | artifact-not-in-HEAD | **resolved** | §8 v1.2 committed at `bb1365d`; `git show HEAD:plan.md` has filled §8 |
| F-003 | major | process-violation | **resolved** | Clean tree at T7 handoff; dirty path now only §8A append (F-015) |
| F-004 | major | contract-violation | **resolved** | `alerts.py` + 6 alert tests pass |
| F-005 | minor | contract-violation | **resolved** | `test_manifest_ingest_skip_logs_warning` passes |
| F-006 | minor | contract-violation | **resolved** | `test_record_failure_logs_error_not_info` passes |
| F-007 | minor | coverage-gap | **resolved** | `test_entries_poll_vector_write_queued_omits_content_raw` in contract file |
| F-008 | minor | intent-drift | **resolved** | `CHANGELOG.MD` L9 T3 line |
| F-009 | minor | contract-violation | **resolved** | Plan §2 L100 `invalid_batch_status` row |
| F-010 | observation | prediction-divergence | **open** | Benign; T1 log documents `models/` package |
| F-011 | observation | prediction-divergence | **open** | Benign test expansion |
| F-012 | observation | coverage-gap | **open** | Docker compose kill criterion still manual |

---

## R2.6 Findings table (revision 2 — new and changed)

| ID | Severity | Type | Phase | Subtask | Description |
|----|----------|------|-------|---------|-------------|
| F-013 | major | coverage-gap | 4, 5 | T8, T5 | `test_escalations_returns_flagged_entry_with_error_log` expects 1 error_log row; T8 inserts ALERT sibling — full suite 153/154 |
| F-014 | minor | process-violation | 2 | T8/T6 | `verify-g2.sh` omits `tests/test_state_worker_alerts.py`; F-004 proof outside G2 script path |
| F-015 | minor | artifact-not-in-HEAD | 0.5 | orch | Plan §8A re-audit handoff append exists only in working tree |

---

## R2.7 Detailed findings (above minor — revision 2)

### F-013 — coverage-gap (major)

**Expected:** After T8 amendment, automated test suite green; escalation panel reflects spec §14.2/§14.3 error history including ALERT rows.  
**Found:** `tests/test_state_worker_routers_escalations.py::test_escalations_returns_flagged_entry_with_error_log` asserts `len(entries[0]["error_log"]) == 1`. `record_failure` with escalation HTTP 404 inserts operational row (`HTTPStatusError`, message "Not found") then `emit_alert` inserts `error_class=ALERT` row — router correctly returns both (`escalations.py` L42–51, unfiltered). Test fails: `assert 2 == 1`.  
**Evidence:** Auditor `pytest tests/ -q` → 153 passed, 1 failed; plan §8A.1 documents same failure.  
**Classification:** Stale T5 unit test not updated in T8 scope — implementation matches spec; test is wrong.  
**Action:** Update test to expect 2 rows (or assert operational row message + ALERT row presence). Optional: filter ALERT from panel wire if UI contract differs — not indicated by spec.

### F-015 — artifact-not-in-HEAD (minor)

**Expected:** Re-audit handoff §8A committed for merge archaeology.  
**Found:** `git diff HEAD -- plan.md` shows 126-line §8A append only on disk. HEAD plan ends at orch decision log table (v1.2 §8 committed).  
**Action:** Commit §8A + this audit revision 2 append.

---

## R2.8 Adversarial test log (revision 2)

### Focus 1 — Integration seams (amendment couplings)

| Surface | Scenario | Expected | Actual | Result |
|---------|----------|----------|--------|--------|
| T8 transaction | `record_failure` + `emit_alert` same commit | Both rows or neither | Operational INSERT → manifest UPDATE → `emit_alert` INSERT → `commit` in `transitions.py` L968–1008 | **passes** |
| T8 ↔ escalations | Panel shows post-escalation error history | All error_log rows per §14.2 | Router returns 2 rows for escalated entry | **passes** (wire correct) |
| T8 ↔ escalations test | Unit test matches wire | Test passes | `len==1` assertion fails | **fails** (F-013) |
| T9 ↔ G2 gate | `content_raw` omission in contract file | In `verify-g2.sh` slice | `test_state_worker_contract.py` L634; `verify-g2.sh` includes contract file | **passes** |
| T8 ↔ manual_retry | Retry target from most recent error_log | Correct predecessor state | ALERT row has same `state_at_failure`; tie on timestamp possible | **unknown** (no adversarial test) |

### Focus 2 — Failure paths / §14.3

| Scenario | Expected | Actual | Result |
|----------|----------|--------|--------|
| Retry budget exhaustion alert | CRITICAL + `alert_type=retry_budget_exhausted` + ALERT row | `test_record_failure_escalation_emits_critical_alert` | **passes** |
| Permanent failure alert | `permanent_failure` | `test_record_failure_permanent_failure_emits_alert` | **passes** |
| Sub-threshold retriable failure | No alert | `test_retriable_failure_without_alert_does_not_emit_critical` | **passes** |
| Idempotent skip WARNING | `logger.warning` | `test_manifest_ingest_skip_logs_warning` | **passes** |
| Failure ERROR not INFO | `logger.error("transition failure")` | `test_record_failure_logs_error_not_info` | **passes** |

### Focus 3 — Regression surface

| Scenario | Expected | Actual | Result |
|----------|----------|--------|--------|
| G2 charter contract suite | All pass | 33 contract tests + health + constants | **passes** (40 in verify-g2 slice) |
| Amendment proof slice | Alerts + contract | 43 passed (auditor command) | **passes** |
| Full `pytest tests/` | Green before M1 sign-off | 153 passed, 1 failed | **fails** (F-013) |

---

## R2.9 Coverage gap list (revision 2)

| Priority | Gap | Tests exist? | Notes |
|----------|-----|--------------|-------|
| **P1** | Escalations router test stale post-T8 | Yes — failing | F-013; blocks full suite |
| **P2** | Alert tests outside `verify-g2.sh` | Yes, not in script | F-014 |
| **P3** | `manual_retry` with ALERT row tie-break | No adversarial test | CR2-04 observation |
| **P4** | Docker compose healthcheck | No | F-012 unchanged |

G2 charter kill criteria: **all covered and passing** in `test_state_worker_contract.py`.

---

## R2.10 Intent traceability (Phase 1 summary)

**Amendment intent → code:** T8 alert dual-write and log levels — **landed**. T9 G2 `content_raw` — **landed**. T7 handoff/CHANGELOG/§2 sync — **landed** at `bb1365d`.

**T8 decision log vs code:** Chosen module `alerts.py`, same-transaction insert, M1 trigger taxonomy, deferred M3/M5 conditions — **matches** implementation. Rejected post-commit alert — **avoided**.

**Narrative vs cold-read:** §8A.4 correctly flags escalations test as open; does not claim full suite green. No narrative-concealment on F-004 closure — alert code verified independently.

**Non-goals:** M3/M5 alert conditions not wired — **respected** per T8 decision log deferrals.

---

## R2.11 Scout-prediction reconciliation (amendment delta)

No new scout predictions. Prior table (§10 revision 1) stands stale-qualified. Amendment confirms Flag 3 (`content_raw`) now **verified** in G2 contract file (F-007 resolved).

---

## R2.12 Verdict (revision 2)

**`pass-with-conditions`**

Amendment successfully closes revision-1 **blocking** findings **F-002, F-003, F-004** (and minors F-005–F-009). G2 charter gate and amendment proof slice are green (**43/43**). Integration seams for T8 dual-write compose correctly; spec-aligned escalation wire exposes both operational and ALERT rows.

**Conditions before M1 merge sign-off:**

1. **F-013 (major)** — Fix `test_escalations_returns_flagged_entry_with_error_log` to expect dual error_log rows (or document/filter if product intent differs). Full `pytest tests/` must pass.
2. **F-015 (minor)** — Commit plan §8A and audit revision 2 for archaeology.

**Accepted without blocking:**

- F-001 context-map staleness — M2 re-scout
- F-014 — extend `verify-g2.sh` to include alert tests, or document intentional split (contract gate vs logging gate)
- F-010, F-011, F-012 — observations from revision 1

**Upgrade to `pass`:** Resolve F-013 + commit §8A/audit rev 2 (F-015).

---

## R2.13 Auditor execution notes (revision 2)

Commands run at re-audit time:

```
git rev-parse HEAD  → 3d1ee2e720eae21d2169eee7c15b279634acf47a
git status --short  → M .dev/plans/m1-state-kernel/plan.md
python -m pytest tests/test_state_worker_contract.py tests/test_state_worker_health.py tests/test_constants.py tests/test_state_worker_alerts.py tests/test_verify_g2.py -q  → 43 passed
python -m pytest tests/ -q  → 153 passed, 1 failed (test_state_worker_routers_escalations.py)
python -m pytest tests/ -k "state_worker or verify_g2 or test_sqlite" -q  → 108 passed, 1 failed
```

Diff scope reviewed: `git diff 2ac1e3c..3d1ee2e` (amendment commits T7–T9 + orch metadata).
