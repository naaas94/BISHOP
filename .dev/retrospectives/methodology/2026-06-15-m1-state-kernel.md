# Methodology retrospective — m1-state-kernel

## 1. Task identifier

- **Task:** M1 — State Kernel (`m1-state-kernel`)
- **Date:** 2026-06-11 (execution); retro filed 2026-06-15
- **Plan versions:** v1.0 (planning) → v1.1 (T1–T6 complete, §8 uncommitted) → v1.2 (amendment landed) + §8A append (re-audit handoff, disk-only at re-audit time)
- **Skills:** pre-plan-exploration v0.2 · orchestrator-planning · executor-subtask-execution · auditor-review
- **One line:** Implement full `state-worker` (schema, transitions, all §9.1 routes, sweeps, G2 contract gate) as program contract anchor.

---

## 2. Plan vs reality

### DAG match

**Mostly yes.** Primary chain T1→T2→{T3,T4}→T5→T6 matched commits (`68e5148`…`2ac1e3c`). T3/T4 were planned parallel; landed sequentially (T3 `cc85f2d`, then T4 `5f891b0`) — safe, no merge conflict.

Amendment DAG T6→{T8,T9}→T7 also matched intent. Commits ran T9 (`6581ed7`) before T8 (`b7bd8a1`), then T7 (`bb1365d`) — order within the parallel group differed from plan prose but both completed before T7.

**Soft dependency held:** T5 `main.py` merged after T3/T4 routers.

### §2 contracts at implementation surface

**Strong on core types and routes; hollow on logging until audit.**

| Area | Held? | Note |
|------|-------|------|
| Enums, models, DB, transitions, routes | Yes | Named tests per §2 row; G2 charter tests pass |
| Error envelope (409/404/400) | Mostly | `invalid_batch_status` implemented in T5 but absent from plan §2 until T7 narrative sync (F-009) |
| §2 Logging / §14.3 alerts | **No at first audit** | F-004: zero `CRITICAL`/`alert_type` in code despite binding §2 row — green tests did not cover this |
| `content_raw` G2 row | Partial at T6 | Implemented in T3 router; router unit test only until T9 moved assertion into contract file (F-007) |
| `emit_alert()` | Landed T8 | 6 alert tests; not in `verify-g2.sh` (F-014) |

No `getattr` defaults or dropped-key hollow patterns observed on core domain types.

### §2 / decision-log narrative survival

- T1/T2 architectural logs match code (enum placement, `bishop.db`, H3 explicit BEGIN, sweep timestamp proxy).
- T8 decision log (deferred M3/M5 alert types, same-transaction insert) matches `alerts.py` implementation.
- **Drift:** Plan §8.1 cites multiple closure SHAs (`57d95bc`, `bb1365d`, `3d1ee2e`) across §8 vs §8A — narrative not single-canonical. §8.2 artifact table still says "v1.1 — this file" inside §8 while header says v1.2.
- T2 `state_entered_at` deferral survived; not silently absorbed.

### Log tier calibration

- T1, T2, T8 as **architectural** — appropriate (schema anchor, transition engine, spec-bound alert surface).
- T3–T7 as **standard** — appropriate; no obvious over/under-tiering.
- T6 might have warranted architectural attention for §2 Logging binding verification — logging gap escaped standard-tier closure.

### Closure vs committed reality

**Leaked twice.**

1. **First audit (`2ac1e3c`):** T6 complete, 147 tests green, but §8 handoff only on working tree (F-002). §8.1 claimed clean tree while `plan.md` modified (F-003). First audit ran against implementation HEAD, not a committed handoff bundle.
2. **Re-audit (`3d1ee2e`):** Amendment closed F-002–F-009 in code/narrative; verdict `pass-with-conditions`. F-013 (escalations test stale after T8 dual-write) **still open** — tracked as OPEN-001 in `.dev/still_open.md`; test still asserts `len(error_log)==1` at HEAD.
3. Commit `7e8be99` ("passed w conditions which are logged") accepted conditions without closing F-013.
4. Context map pinned at scout SHA `8d339ee` — never refreshed post-M1 (F-001, treat-as-prediction).

Closure SHA in plan §8 commit table does not align with git log canonical chain (`bb1365d` for T7, not `57d95bc`).

---

## 3. HALTs and amendment cycles

### Executor HALTs

**Zero formal HALTs fired** across T1–T9 packets (no executor stop reports in artifacts).

**HALT-shaped improvisations (should have fired or escalated):**

| Surface | What happened |
|---------|----------------|
| T6 §8 handoff | Kill criteria did not require committed §8; executor filled §8 in working tree, claimed clean tree — process violation caught at audit, not by executor |
| §2 Logging binding | T2/T6 shipped without `emit_alert` — no HALT despite plan §2 CRITICAL/`alert_type` row |
| T8 ↔ escalations test | §7R.4 flagged `(T8 ALERT row \| GET /escalations error_log length)` as **suspected**; T8 landed without updating `test_escalations_returns_flagged_entry_with_error_log` — kill criteria treated as satisfied while full suite regressed |

### Amendment cycles

**One full cycle:** Initial audit **fail** → T8+T9+T7 amendment → re-audit **pass-with-conditions**.

| Aspect | Assessment |
|--------|------------|
| Amendment scope vs findings | Right — F-004/F-005/F-006 code (T8), F-007 G2 test (T9), F-002/F-003/F-008/F-009 narrative (T7) |
| Architecture creep | None — T8 stayed within §14.3 M1 triggers; deferrals documented |
| Re-audit closure | **Incomplete** — F-013 major condition not fixed; only logged (§8A.4 open, OPEN-001) |
| Passes required | Two audit passes; second did not upgrade to `pass` because F-013 remained |

For an architectural-tier milestone, first-pass audit was not weak — it correctly caught F-004 (major contract hole) and handoff archaeology failures.

---

## 4. Adversarial pass calibration

### Rejected alternatives

- **7 subtasks by endpoint family (Alt A):** Correct rejection — `main.py` merge bottleneck confirmed in plan §5.1.
- **Single REST-surface subtask (Alt B):** Correct rejection — scope too large, no T3/T4 parallelism.
- **Defer §14.3 to M2 (amendment Alt):** Correct rejection — F-004 major + spec G2 binding.

### Load-bearing assumptions

| Assumption | Outcome |
|------------|---------|
| SQLite single-writer via REST claims | Closed — no bypass path |
| `bishop.db` frozen in bishop_shared | Closed |
| Derived wire models | treat-as-prediction — contract smoke only |
| TestClient + temp SQLite ≡ production | treat-as-prediction — acceptable for M1 |
| M0 `/health` non-blocking | Closed |
| T8 same-transaction alert insert | Closed per T8 decision log |
| Amendment SHA on clean tree (T7) | Partially — T7 commit clean; §8A append dirtied tree again (F-015) |

### Highest re-plan risk

**Predicted: T2 (transition engine).** T2 landed without re-plan. Actual trouble from **§2 logging contract omission (F-004)**, **handoff commit hygiene (F-002/F-003)**, and **T8 side-effect on escalations test (F-013)** — all downstream of T2, none requiring T2 redesign.

Process risk (Flag 5 untracked M0 artifacts) materialized as audit hygiene notes only — did not block executors, as predicted.

---

## 5. Methodology gaps surfaced

**Orchestrator should have prompted for:**

- Explicit subtask or T6 kill criterion: **commit §8 handoff in same bundle as T6 code** (or separate T6b doc-only closure before audit).
- Amendment packet T8: **mandatory full-suite pytest** or grep for `error_log` length assertions before closure — §7R.4 coupling was listed but not assigned.
- Alignment check: plan §8 "primary verification" command vs `verify-g2.sh` module list (alerts added to §8A command but not script — F-014).

**Executor let through:**

- Binding §2 Logging row with no implementation through T6 — auditor gate worked, executor did not self-check against §2 evidence table.
- T7 recorded clean-tree §8.1 while amendment cycle left F-013 open — conditions logged but not gated on fix.

**Contracts schema:**

- §2 Logging row was binding but outside G2 script path — created false confidence (147 green tests, fail on alert contract).
- Split between "G2 charter tests" and "full §2 row tests" needs explicit tier in plan §2 Tests section.

**Do not edit skills here** — patterns to watch across retrospectives: handoff commit coupling, amendment regression scan for dual-write side effects, verify-script parity with §8 commands.

---

## 6. Single sentence verdict

**Partially** — the orchestrator/executor/auditor loop did its job on core implementation and caught the major §14.3 contract hole plus handoff archaeology failures, but closure hygiene leaked twice (uncommitted §8 at first audit, F-013 left open after `pass-with-conditions`), and a predicted T8↔escalations coupling flagged in §7R.4 was not closed in amendment scope despite being detectable before re-audit sign-off.
