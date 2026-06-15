# Methodology retrospective — m5-enrichment

## 1. Task identifier

- **Task:** M5 — Enrichment Slice (`m5-enrichment`)
- **Date:** 2026-06-13 (planning + execution); retro filed 2026-06-15
- **Plan version:** v1.0 (no amendment bump)
- **Skills:** pre-plan-exploration v0.3 · orchestrator-planning · executor-subtask-execution · auditor-review v0.4
- **One line:** Ship `bishop_shared` enrichment utilities, state-worker hub submit/timeout/OOV wiring, `enrichment-batcher` dual tasks, `batch-poller` v2, and M5 integration gate → `VECTOR_WRITE_QUEUED`.

No artifact named "evert" in the plan tree; evidence drawn from executor commits, CHANGELOG, decision logs T1/T2/T4, handoff §8, and audit `.dev/audits/2026-06-13-m5-enrichment.md`.

---

## 2. Plan vs reality

### DAG match

**Yes.** Commits match the planned DAG with safe parallelization:

| Planned | Landed |
|---------|--------|
| T1 → T2 | `f1782e9` → `54f7610` |
| T2 → {T3, T5} parallel | `073ff4e` (T3), `31027b3` (T5) — order interchangeable |
| T3 → T4 (not parallel) | `47c7d91` after T3 |
| {T4, T5} → T6 | `0331dd5` |

Flag 6 file-collision constraint honored: T4 did not run parallel to T3. No unsafe parallelization observed.

### §2 contracts at implementation surface

**Strong on typed surfaces; minor hollow spots on logging and one deferred edge.**

| Area | Held? | Note |
|------|-------|------|
| All §2 symbol rows (truncation, taxonomy, prompts, parsers, hub hooks, batch types, cycles, compose tags) | Yes | Audit §8.3 maps every row to artifact + named proof test; M5 gate 105/105 green |
| Error envelope literals (`model_string_fatal`, `profile_hash_mismatch`, `batch_timeout`, etc.) | Yes | Byte-equal per audit Phase 2 |
| §2 Logging `event` set | **Partial** | F-005: enrichment-batcher emits `state_worker_error`, `empty_poll`, `unsupported_domain`, `missing_summary` outside declared set — ops-useful, contract drift |
| OOV persistence (`oov_tags_stripped` → `oov_tags_log`) | Yes on success path | F-006: insert gated on `entry_type is not None`; deferred in T2 decision log; no negative test |
| `custom_id` = `source_id` | Yes at M5 audit time | Later program fix (`batch_custom_id` encoding) post-dates this milestone — out of M5 retro scope |

No `getattr` defaults or dropped-key hollow patterns on core §2 types. Integration e2e (`test_m5_integration.py`) exercises charter falsifiers, not only unit stubs.

### §2 / decision-log narrative survival

- T1/T2/T4 architectural logs match shipped code; audit Phase 3 marks all clean, no narrative-concealment.
- T4 decision log documents packet `files-to-touch` gap vs §2 (`config.py`, `models.py`, `state_worker_client.py`) — drift repaired in same session via decision log, not left latent.
- T2 OOV `entry_type` gate deferral survives in code and log; handoff §8.4 and audit CR-03 acknowledge it — not silently absorbed.
- **Drift uncorrected:** `plan.md` header still `Status: Ready for executor dispatch`; §8 still reads "Pending execution" at `0331dd5` and at current HEAD — F-003 waived, never repaired. Canonical §8 lives only in `handoff.md`.

### Log tier calibration

- T1, T2, T4 **architectural** — appropriate (new shared surface, hub amendment, Call 2 cache/profile semantics).
- T3, T5, T6 **standard** — appropriate; no M1-style escape of a binding contract through standard tier.
- T5 could have been argued architectural (monolithic `loop.py` v2, three batch-type dispatch) but audit agrees wiring was straightforward; tier choice defensible.

### Closure vs committed reality

**Leaked once on closure bundle; repaired partially post-audit.**

| Checkpoint | State |
|------------|-------|
| Implementation anchor `0331dd5` | All T1–T6 code + decision logs + packets + CHANGELOG in HEAD; tree clean per handoff |
| `handoff.md` at `0331dd5` | **Absent** — F-002; committed in `ac991e9` with audit report |
| `plan.md` §8 at `0331dd5` | Placeholder — F-003 |
| First audit | Ran at `0331dd5` with dirty tree (`?? handoff.md`); Phase 0 narrative-blind discipline followed |
| Re-audit | **None** — `pass-with-conditions` accepted with waivers (M2/M4 pattern) |
| Context map | Scout SHA `406ff61` stale vs implementation — F-001; expected, flagged for M6 pre-plan |
| Post-M5 architecture refresh | Not committed — charter §7 housekeeping deferred |

Closure SHA for *code* is `0331dd5`. Closure bundle for *audit archaeology* is `ac991e9` (handoff + audit), not the implementation anchor — same leak class as M1/M2.

---

## 3. HALTs and amendment cycles

### Executor HALTs

**Zero formal HALTs** across T1–T6 (no halt reports in packets, CHANGELOG, or decision logs).

**HALT-shaped improvisations (not escalated):**

| Surface | What happened |
|---------|----------------|
| T6 §8 handoff | Kill criteria did not require committed handoff; handoff authored post-`0331dd5`, audit caught F-002 — process gap, not executor HALT |
| T4 files-to-touch vs §2 | Executor extended `config.py` / `models.py` / `state_worker_client.py` beyond packet list; documented in T4 decision log instead of HALT — correct outcome, informal path |
| §2 logging contract | Auxiliary log events shipped without contract amendment or HALT — audit F-005 minor |
| OOV without `entry_type` | T2 deferred silently per decision log; no negative test — acceptable deferral, not a kill-criteria violation |

Nothing observed where kill criteria were satisfied by appending Landed bullets while scan-visible stale blocks remained in *code* — only in *plan narrative* (§8 placeholder).

### Amendment cycles

**Zero.** Plan §7 none at emission; audit did not trigger T7-shaped remediation.

First pass `pass-with-conditions` with nine waived findings (F-001–F-009). No critical findings; no intent drift. Contrast with M1: audit signal was sharp enough to catch closure hygiene and contract gaps, but M5 gaps were process/housekeeping and accepted deferrals — not false negative on implementation.

---

## 4. Adversarial pass calibration

### Rejected alternatives

All three mattered as guardrails and were honored:

- **Merge T2 into T5** — hub sole-writer preserved; `register_batch` submit hook in state-worker.
- **Parallel T3 + T4** — sequential land prevented `main.py` collision.
- **OOV direct SQLite from batch-poller** — routed through state-worker wire field.

### Load-bearing assumptions

| Assumption | Outcome |
|------------|---------|
| M1 enrichment POST + H3 transitions sufficient | **Closed** — e2e five-entry path |
| `register_batch` extension sufficient for submit | **Closed** — hub + integration tests |
| tiktoken cl100k_base for 4k ceiling | **Treat-as-prediction** — unit clamp only; live quality deferred G6/M8 |
| M4 `content_raw` for paper truncation | **Treat-as-prediction** — e2e synthetic content |
| G3 model string valid | **Treat-as-prediction** — CI mocks Anthropic |

Assumptions flagged as predictions were not falsely closed in audit narrative.

### Highest re-plan risk

**T2 (state-worker hub)** was named highest risk (§5.3). **Did not cause trouble** — landed in one commit, no downstream client rework.

**T1 truncation** was second risk — also clean; paper strategy + abstract heuristic sufficient for M5 gate.

**C7 pre_filter regression** was **suspected** in §5.4 — **disproven**; all seven `test_batch_poller_loop.py` tests green after T5. Adversarial pass correctly flagged it; execution validated it.

Trouble came from **elsewhere:** recurring **closure hygiene** (handoff not in implementation SHA, plan §8 stale) — process, not T2 hub logic.

---

## 5. Methodology gaps surfaced

**Orchestrator should have prompted for:**

- **Committed §8 bundle as T6 kill criterion** — M1/M2/M4 pattern repeated; handoff still follow-up commit after implementation SHA.
- **Plan status + §8 inline update** — or explicit "handoff-only §8" convention so F-003 does not recur every milestone.
- **Packet `files-to-touch` completeness check against §2 owner rows** — T4 gap caught by executor, not orch packet review.

**Executor should have blocked (or orch should have required):**

- Nothing blocking on implementation quality. Optional: HALT or contract-row add when shipping log `event` values outside §2 set (F-005).

**Contracts schema:**

- §2 Logging row may be too brittle for operational auxiliary events — consider "declared minimum set" vs exhaustive enumeration.
- No vestigial rows observed; `EnrichmentStage1EntryWire.oov_tags_stripped` fully wired.

**Audit / program hygiene (positive):**

- `known-test-failures.md` + OPEN-001 centralizes M1 escalations debt — reduces handoff duplication (improvement over M4).
- Cold-read CR-02 (orphaned Anthropic batch) and CR-03 (OOV entry_type gate) surfaced without narrative-first — auditor skill worked.

Do **not** edit skills from this retro.

---

## 6. Single sentence verdict

**Partially held** — the DAG, contracts, and adversarial planning delivered a clean first-pass implementation with no amendment cycle, but closure hygiene leaked again (handoff and plan §8 not co-committed with `0331dd5`), repeating a program-level pattern M1 already surfaced and M5 audit waived instead of re-auditing.
