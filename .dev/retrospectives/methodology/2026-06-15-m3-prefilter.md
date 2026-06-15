# Methodology retrospective — m3-prefilter

## 1. Task identifier

- **Task:** M3 — Pre-filter Slice (`m3-prefilter`)
- **Date:** 2026-06-12 (pre-plan / plan) → 2026-06-13 (execution, audit, closure commit `a072787`)
- **Plan version:** v1.0 · pre-plan-exploration v0.3 · scout SHA `6d36e73`
- **One line:** NL profile v1.0.0, profile renderer, state-worker batch lifecycle API, `pre-filter-worker`, and `batch-poller` v1 — entries `DISCOVERED` → `RELEVANCE_PASSED` / `RELEVANCE_REJECTED` with G3 gate and 48h timeout.

## 2. Plan vs reality

### DAG match

**Mostly yes.** Planned parallel groups `{T1,T2,T3}` and `{T4,T5}` were respected in scope; git history landed six implementation commits in dependency-safe order (`e07d285` T1 → `6a93194` T2 → `303bd22` T3 → `b098170` T4 → `e50786e` T5 → `1d2a89d` T6). No re-sequencing or unsafe parallelization surfaced in artifacts. T5 correctly did not wait on T2.

### §2 contracts at implementation surface

**Held.** Auditor Phase 2 marked every §2 row **Pass** with a named test (`handoff.md` §8.3 table; audit §7 contract compliance). No hollow contracts observed — symbols exist at declared paths, wire shapes match pydantic models, env vars parsed with config tests, error envelope events (`profile_hash_mismatch`, `model_string_fatal`) exercised. `BatchRecord.source_ids`, 409 duplicate semantics, and timeout → `DISCOVERED` all have dedicated tests.

### §2 / decision-log narrative survival

**Held.** T2 and T3 decision logs match code at audit HEAD; auditor Phase 3 found no `narrative-concealment` and no stale unfenced assertions. T3 deferred item (registration-time manifest validation) remained accurately deferred — not narrated as shipped. Minor gap: CR-1 (Anthropic submit before `POST /batches`, orphan external batch on register failure) is tested and CHANGELOG-noted but not in any decision log; audit accepted for standard-tier T4.

### Log tier calibration

**Appropriate.** T2/T3 architectural (hash algorithm, batch API shape) warranted decision logs — both landed. T1/T4/T5/T6 standard tier without logs matches policy. T6 integration gate at standard tier was sufficient given §8.3 evidence table and named falsifiers in `test_m3_integration.py`.

### Closure vs committed reality

**Partially clean — repaired post-audit, no re-audit.**

| Check | Result |
|-------|--------|
| Implementation anchor | `1d2a89d` — first commit with full T1–T6 code + packets in tree |
| Plan §8 / handoff at implementation SHA | **Absent** at `1d2a89d` — audit F-002 |
| Audit run tree state | **Dirty** (`M plan.md`, `?? handoff.md`) at initial audit |
| Follow-up closure | `a072787` committed `handoff.md`, audit report, plan §8 — F-002 resolved |
| Re-audit after closure | **No** — unlike M1 revision-2 pattern |
| Context-map pinned SHA | Scout `6d36e73` stale vs implementation — acknowledged F-001, expected |
| Handoff test count | 90 vs auditor 98 (F-007 typo); not corrected in `a072787` prose |

First audit ran against pre-handoff HEAD; drift caught by audit, repaired same session in `a072787`. Residual: F-003 (charter G3 live exit) waived in audit §14 but handoff §8.6 still reads "Absent" — no explicit §8.6 waiver artifact as audit condition requested.

## 3. HALTs and amendment cycles

### Executor HALTs

**Zero.** No executor HALT records in packets, CHANGELOG, or handoff. Kill criteria appear satisfied:

- T2: real `canonical_hash`, JSON-canonical hash
- T3: 409 idempotency, hub single-writer, timeout → `DISCOVERED`
- T4: G3 gate, hash verify, `custom_id=source_id`
- T5: startup scan first, enrichment type guard, timeout endpoint
- T6: 20-entry pass+reject, startup-scan restart falsifiers

Nothing HALT-shaped was silently improvised past. CR-1 orphan-batch ordering was an explicit ship decision (test documents behavior; M5 CHANGELOG echoes same pattern) rather than a kill-criterion bypass.

### Amendment cycles

**Zero §7 amendments.** Audit verdict `pass-with-conditions`; no T7-shaped remediation subtasks. F-002 closed by hygiene commit, not amendment packet. First pass was substantively clean on code/contracts; process findings (artifact HEAD, G3 exit wording) were hygiene-level, not architectural drift.

**Calibration note:** For an architectural-tier milestone (T2+T3), zero amendments with `pass-with-conditions` is credible — audit did not miss obvious contract holes. Live-compose failures surfaced later in `m3-batch-pipeline` decision logs (sweep race C5, poller crash) — audit marked C5 `unknown`/accepted; sharper adversarial pass predicted the risk but M3 scope accepted it per G4 caveat.

## 4. Adversarial pass calibration

### Rejected alternatives

**Mattered indirectly, not via replan.**

- **Merge T4+T5:** Correct rejection — two compose services, distinct restart semantics; no merge pressure during execution.
- **Defer T3 to M5:** Would have blocked execution; T3 landed without churn — validates rejection.
- **Split T2 YAML vs renderer:** Avoided hash drift; T2 single commit — validated.

### Load-bearing assumptions

| Assumption | Outcome |
|------------|---------|
| M1 `apply_pre_filter_results` on `RELEVANCE_QUEUED` | Closed — integration tests |
| `custom_id` = `source_id` | Closed at M3; **later revised** in batch-custom-id encoding (post-M3) when live Anthropic rejected colons |
| G3 model string valid at execution | Treat-as-prediction — pinned + mocked; live probe skipped |
| `source_ids` migration before workers | Closed |
| JSON canonical hash not prompt text | Closed |

### Highest re-plan risk (T3)

**Did not cause replan.** T3 was the largest spec-gap closure; wire shapes landed as planned, T4/T5 clients did not require rewrites. Timeout `RELEVANCE_QUEUED → DISCOVERED` was not challenged at audit. Trouble came **elsewhere**: live compose after M3 exposed C5 sweep/orphan-batch coupling (documented in `.dev/decision-logs/m3-batch-pipeline/batch-poller-orphan-batch-resilience.md`), not T3 API shape errors.

## 5. Methodology gaps surfaced

**Orchestrator skill should have prompted for:**

1. **Charter exit gate vs CI policy reconciliation** before plan freeze — charter L254/L280 require live G3 probe; T1 explicitly SKIP-on-no-key. Plan and handoff defer without §8.6 waiver text; audit elevated to F-003 major. This is the same class of drift as "exit gate wording" not "implementation bug."
2. **Handoff commit bundled with T6** — recurring `artifact-not-in-HEAD` (M0→M7). Orchestrator §8 should require handoff + plan §8 in the **same commit as T6** or as immediate follow-up before audit invocation. M3 repeated M1/M2/M4 pattern; only M1 ran formal re-audit.
3. **Post-closure re-audit trigger** when audit runs on dirty tree and closure commit lands same day — `a072787` resolved F-002 but audit document still describes pre-commit HEAD as anchor.

**Executor skill let through (acceptable but notable):**

- Submit-then-register ordering without architectural decision log (audit CR-1) — standard-tier T4; should perhaps HALT-or-log when plan error envelope is silent on compensating transaction.
- Handoff §8.1 "clean at `1d2a89d`" true for code only; narrative handoff artifacts intentionally post-dated — accurate but repeats M1 cleanliness confusion.

**Contracts schema:**

- Nothing vestigial. Registration-time manifest validation gap was correctly deferred with explicit T3 log row — schema worked.
- `scout-incomplete` not filed for M3 (unlike M6/M7) — scout grep coverage was adequate for this slice.

**Note:** No artifact named "evert" found in plan folder; interpreted request as audit + handoff + execution chain.

## 6. Single sentence verdict

**Partially** — the orchestrator/executor pipeline delivered a DAG-faithful, contract-tested M3 slice with zero HALTs and no amendment cycle, but recurring closure hygiene (`handoff` not in implementation HEAD, charter G3 exit vs CI SKIP unresolved in committed waiver prose) leaked through the same holes seen in M1–M2 and was caught only at audit, not prevented by methodology gates.
