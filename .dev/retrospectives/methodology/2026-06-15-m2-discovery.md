# Methodology retrospective — m2-discovery

## 1. Task identifier

- **Task:** M2 — Discovery Slice (`scraper` service: `SourceAdapter`, ArXiv-only registry, failure envelope, scrape loop, state-worker HTTP client)
- **Date:** 2026-06-12 (execution + audit); retrospective filed 2026-06-15
- **Plan version:** `m2-discovery` v1.1 · pre-plan-exploration v0.2 · orchestrator + executor + auditor (no amendment cycle)
- **One line:** Land the pipeline discovery stage so ArXiv manifest rows reach `DISCOVERED` with rate limiting, retry envelope, and idempotent re-run.

---

## 2. Plan vs reality

### DAG match

**Yes — matched.** Five executor commits in planned order: `febf62c` T1 → `5c3c45a` T2 → `fa98e72` T3 / `d6c94bc` T4 (file-disjoint; no evidence of unsafe parallelization issues) → `0954ea8` T5. T5 correctly merged loop, compose tag, and M2 gate last. No re-sequencing, no re-plan.

### Contracts at implementation surface

**Mostly held; two hollow spots and one narrative overclaim.**

| Area | Verdict |
|------|---------|
| §2 symbol table (22 rows) | Landed at declared paths; 78/78 M2 gate tests green at audit |
| Enum drift guard | Real — `test_shared_enums_match_state_worker` compares literals, not cross-import |
| Kill-criteria falsifiers | 429 survival, idempotency `skipped >= 1`, batch-failure state guard, compose `:m2` tag — all tested |
| `BISHOP_ARXIV_MAX_RESULTS` | Admitted in `arxiv.py`; default asserted in fixture test; **no env-override admission test** (audit F-005) |
| `RetryExhaustedError` at loop | Handler in `loop.py`; **no loop-level test** — envelope-only coverage in T3 (audit F-004, OPEN-015) |
| C4 rate-limiter ordering | Code correct (`acquire` before HTTP); plan §5.4 "disproven by" cited a unit test that **does not exist** (audit F-006) |

No `getattr` defaults or dropped-key hollow contracts observed on the scraper wire surface.

### §2 and decision-log narrative survival

**Minor drift, not repaired in-session.**

- T1 decision log still says "stub CMD retained until T5" with no supersession banner after T5 landed (audit F-009; still in `still_open.md` OPEN-019).
- Plan §5.4 C4 disposition in handoff §8.4 says "closed" via `test_token_bucket_throttles` — that test covers `calls=1` bucket math, not adapter acquire order. Handoff partially reconciles F-006 but plan prose and §8.3 evidence row overclaim.
- Context-map header says **READY**; plan §0 intake records **CONDITIONAL** — undocumented mismatch (audit F-003).

### Log tier calibration

**Appropriate.**

- T1, T2, T4 `architectural` — cross-service enums, ABC/registry charter override, Atom wire protocol: correct.
- T3, T5 `standard` — envelope and loop integration without new contract-anchor surfaces: correct.
- T3 correctly omitted a decision log per plan.

### Closure vs committed reality

**Implementation clean; orchestration artifacts lagged — M1 pattern repeated.**

| Check | Result |
|-------|--------|
| Closure SHA `0954ea8` = first commit with full T1–T5 code | **Yes** |
| Decision logs T1/T2/T4 in HEAD at `0954ea8` | **Yes** |
| Plan, handoff, context-map, packets in HEAD at `0954ea8` | **No** — entire `.dev/plans/m2-discovery/` untracked (audit F-002) |
| Audit run tree | Correct implementation at `0954ea8`; plan artifacts read from dirty working tree |
| Context-map pinned SHA vs audit HEAD | Scout `7e8be99` predates all M2 code — expected staleness (F-001) |
| Post-audit repair | `b9ff78e` committed plan dir + audit report; **did not** add T7-style amendment subtasks or close F-004/F-009 |

F-002 caught at audit; repaired in follow-up commit but **not** at the cited implementation SHA. M3+ pre-plan could consume M2 handoff from HEAD today; archaeology at `0954ea8` alone remains broken for plan artifacts.

---

## 3. HALTs and amendment cycles

### Executor HALTs

**Zero fired.** All five subtasks completed without executor halt. Kill criteria appear satisfied by tests rather than improvised past:

- Flag resolutions frozen in plan §0 before execution (enum sharing, Atom API, 7-day window).
- No evidence of silent improvisation on kill criteria — except **deferred gaps logged in CHANGELOG rather than escalated as HALT-shaped blockers**:
  - `RetryExhaustedError` loop branch (T5 CHANGELOG deferral; no §8.6 waiver at handoff time).
  - Live `docker compose` smoke (consistent with M1/M3+ program pattern; explicitly deferred).

### Amendment cycles

**None — and that is the main process gap vs M1.**

- Plan §7: "None — initial plan v1.0."
- Audit verdict: `pass-with-conditions` (F-002 major; F-004, F-009 minor).
- **No T7-shaped amendment subtasks** were planned or executed (contrast M1 T7–T9 closing audit findings).
- F-002 closed by artifact-only commit `b9ff78e`, not an orchestrated amendment packet.
- F-004 and F-009 remain open in `still_open.md` (OPEN-015, OPEN-019) without committed handoff §8.6 waiver.
- First-pass audit was not "genuinely clean" on process hygiene; amendment machinery was bypassed in favor of "log conditions and move to M3."

---

## 4. Adversarial pass calibration

### Rejected alternatives

| Alternative | Mattered later? |
|-------------|-----------------|
| Merge T3+T4 (envelope inside adapter) | Not yet — M8 multi-adapter case still benefits from separate T3 |
| Enums in scraper only (no `bishop_shared`) | **Yes** — M4+ content-scraper and cross-service enums justified the choice |
| Live ArXiv in CI gate | Correct rejection — fixtures-only policy held |

### Load-bearing assumptions

**All held at M2 scope.** G2 green, Atom API + fixtures, container isolation, Arxiv-only registry, 7-day default — verified. Live API availability remains treat-as-prediction (appropriate).

### Highest re-plan risk

**T4 named; trouble did not come from there.** Atom parsing, date-range query, and fixture tests landed without re-plan. Actual gaps were test-coverage and closure hygiene (T5, orchestration), not T4 parsing surprises.

### Hidden couplings (§5.4)

C1–C3 verified. C4 verified by code inspection only — plan's predicted disproof test was fiction (F-006). C5 disproven correctly (httpx in dev deps).

---

## 5. Methodology gaps surfaced

**Orchestrator should have prompted for:**

1. **Commit plan artifacts before or with T5 closure** — identical failure mode to M0/M1 F-002; charter §7 or orchestrator handoff checklist did not prevent recurrence.
2. **Readiness label consistency** — context-map READY vs plan CONDITIONAL should be reconciled at plan intake, not left for audit F-003.
3. **Explicit §7 amendment row when audit is expected** — if pass-with-conditions is likely (artifact-not-in-HEAD is predictable when code commits precede plan commits), pre-declare T6/T7 remediation subtasks like M1.

**Executor let through:**

1. Plan §5.4 C4 "disproven by" prose citing nonexistent test — executor or handoff author should not assert test evidence without grep proof.
2. Handoff §8.3 mapping rate-limiter proof to `test_token_bucket_throttles` — misaligned with §2 test naming for C4.
3. CHANGELOG deferrals for loop exhaustion without requiring handoff §8.6 cross-link — waiver path unused.

**Contracts schema:**

- Nothing vestigial.
- Missing: explicit **orchestration-artifact-in-HEAD** row in §2 or §8 closure checklist (process contract, not code).
- `BISHOP_ARXIV_MAX_RESULTS` in plan §2 wire narrative but absent from typed-surface table — admission gap easy to miss (F-005).

*(Skill edits deferred — pattern observation only.)*

---

## 6. Single sentence verdict

**Partially** — the DAG, packets, and §2 implementation surface held up on a clean five-commit execution with zero HALTs, but closure hygiene leaked again (plan directory absent at `0954ea8`), audit conditions were closed only halfway (F-002 yes, F-004/F-009 no), and the program skipped the M1-style amendment cycle that would have formalized remediation instead of parking debt in `still_open.md`.
