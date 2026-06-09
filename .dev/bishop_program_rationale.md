# BISHOP Program Rationale

**Version:** 0.1.0
**Author:** Alejandro Garay Frontini
**Date:** 2026-06-09

Companion to `bishop_program_charter.md`. Explains why the decomposition is structured as it is — slice boundaries, sequencing decisions, what persists between milestones, and what constraints orch skill rules impose on every M-plan.

---

## 1. Why Vertical Slices Beat Horizontal Services

The naive decomposition would assign one milestone per Docker service: "implement scraper", "implement state-worker", "implement pre-filter-worker", etc. This approach fails for a pipeline where correctness depends on end-to-end flow rather than individual service behavior.

**The spec mandates phase-gated deployment** (§21 L1441): *"Do not enable full backfill until the pipeline is validated e2e. Volume at backfill scale is an order of magnitude higher than steady-state."* A horizontal decomposition produces a program that cannot be validated at any intermediate milestone — every service is individually complete but the pipeline cannot run until all services exist. The first runnable checkpoint would be at the very end of development, which is precisely the scenario the spec warns against.

**Section 22 (L1445–1522) is ordered by pipeline dependency**, not by service boundary. The build checklist reads: Foundation → Source Adapters → Pre-filter Layer → Content Scraping → Enrichment Pipeline → Indexing → Query Layer → UI → Validation and Backfill. This ordering reflects the data dependency graph: an entry must reach `DISCOVERED` before it can be pre-filtered; it must reach `RELEVANCE_PASSED` before content can be scraped; it must reach `SCRAPED` before enrichment can proceed. Horizontal service slices violate this ordering by building all scraper logic before any pre-filter logic, leaving no runnable checkpoint.

**Vertical slices follow the data.** M0 establishes structural skeleton. M1 builds the state machine that every entry flows through. M2 produces `DISCOVERED` entries. M3 produces `RELEVANCE_PASSED` entries. M4 produces `SCRAPED` entries. M5 produces `VECTOR_WRITE_QUEUED` entries. M6 produces `INDEXED` entries. M7 serves them. M8 validates and scales. Each milestone's runnable checkpoint is observable in the pipeline state, not just in container health.

---

## 2. Why M1 Is the Contract Anchor

The `state-worker` service is not merely one of nine containers — it is the **sole SQLite writer** (§2 Principle 3, L63: *"The SQLite state store has one writer: the `state-worker` service."*) and the **only service that owns state transitions** (§6.2 L292: *"Every transition is owned by `state-worker`. No service writes state directly."*).

Every subsequent milestone communicates with every other milestone through `state-worker`'s REST API (§9.1, L613–760). The `pre-filter-worker` does not know the `scraper` exists — it only knows `GET /manifest/poll`. The `enrichment-batcher` does not know `content-scraper` exists — it only knows `GET /entries/poll?state=SCRAPED`. The decoupling is designed in; the REST API is the contract.

If M1 were not the anchor — if, say, the `state-worker` were built incrementally across M1 through M5 as each pipeline stage was added — every subsequent milestone would be building against a moving contract surface. An M3 executor extending `state-worker` for pre-filter result endpoints while an M2 executor is still adding atomic-claim behavior for the scraper poll endpoint creates race conditions between plans, not just between services. The orch skill's §7 amendment process exists for mid-milestone contract changes; it cannot handle contract incompleteness across milestones.

Building the **complete** `state-worker` in M1 means M2–M8 build against a stable, tested API. The M1 exit gate (G2: all §9.1 contract tests pass) is the proof of stability that every subsequent pre-plan can trust.

---

## 3. Why Batch-poller Spans M3 + M5

`batch-poller` is unique among Bishop services: it has no entry in the §22 build checklist as a standalone section. Instead, it appears under **Pre-filter Layer** (L1474: *"Batch-poller: Anthropic batch polling for pre-filter batches…"*) and under **Enrichment Pipeline** (L1486: *"Batch-poller service: polls Anthropic for Call 1 completion…"* and L1490: *"Batch-poller: polls Anthropic for Call 2 completion…"*). Its responsibility grows with the pipeline.

The §9 service map (L608) makes its cross-cutting scope explicit: `batch-poller` *"polls Anthropic for all batch types (pre-filter, enrichment stage 1, enrichment stage 2); on startup, queries state-worker for in-flight BatchRecords and re-registers them."* At M3, only pre-filter batch types exist. At M5, enrichment batch types are added and the startup scan must cover them too (S3 fix, L758: *"Without this startup scan, any batch submitted before a batch-poller restart is silently orphaned."*).

Splitting `batch-poller` into two separate milestone implementations is the correct decomposition because:
1. At M3, the enrichment `BatchRecord` schema does not yet need to be polled — no enrichment batches exist.
2. At M5, adding enrichment batch types is a contained extension to an already-running service, not a new service.
3. Requiring M5 to re-implement or fork `batch-poller` would violate single-responsibility and create contract drift risk.

The charter names `batch-poller` as a **contract hub** with an explicit restriction: it must not be split across unrelated plans without a named owner subtask. M3 owns batch-poller v1; M5 owns batch-poller v2. No other M-plan may extend batch-poller without a charter amendment.

---

## 4. Why ArXiv-First in M2

**§3.1 (L87)** names ArXiv as *"Ground truth for ML preprints."* **§22 (L1460)** marks ArXivAdapter as the first adapter in the source adapters list with a parenthetical *"highest priority, most volume."* **§21 step 7 (L1434)** specifies the cold-start smoke test as: *"Run scraper against a single source (e.g., ArXiv cs.AI, last 7 days)."*

ArXiv is the spine of the professional domain source stack: it is the primary source, has the highest volume, has a stable and well-documented REST/RSS API, and is the adapter against which the scraper loop, failure envelope, and content scraper will be tested throughout M2–M4. Every other adapter is a variation on the same pattern — if ArXiv works, the adapter infrastructure works.

Building HuggingFace, PapersWithCode, and other adapters in M2 would:
1. Require verifying five separate external APIs before any end-to-end smoke test is possible.
2. Produce a wider surface for adapter-specific bugs to obscure infrastructure bugs.
3. Delay G4 (e2e smoke) by requiring all adapters to be working before validation can begin.

ArXiv-first in M2, all others in M8, follows the §21 phase-gated deployment principle directly.

---

## 5. Why Backfill Is M8-Only

**§21 steps 10–12 (L1437–1440)** define the mandatory pre-backfill sequence:
1. Step 9–10: embedding quality gate (G5) — 3–5 test queries must return intuitively correct results.
2. Step 11: validate quality of pre-filter decisions and enrichment output; iterate NL profile if off.
3. Step 12: *"After e2e validation and quality gate passage, expand to all sources and enable backfill."*

**§21 L1441** is explicit: *"Do not enable full backfill until the pipeline is validated e2e. Volume at backfill scale is an order of magnitude higher than steady-state. A bug in the enrichment prompt or the pre-filter that goes undetected at small scale will produce thousands of incorrectly enriched entries at backfill scale."*

**§18.1 (L1305)** reinforces: *"Backfill runs after e2e validation on small batches — not on first deployment."*

Backfill appears in M8 because it is the **last gate**, not an early operation. It requires: (1) all adapters functional (M8 also), (2) quality gates G5 and G6 passed (verified at M7 exit / M8 entry), (3) the full pipeline validated e2e (G4 at M7 exit). The §18.2 (L1310–1323) per-source backfill configuration (60-day ArXiv window, 30-day GitHub, 90-day OpenReview) produces tens of thousands of manifest entries and hundreds of enriched entries. Running that against an unvalidated pipeline is explicitly rejected by the spec.

---

## 6. What Persists Between Milestones

Three classes of artifacts persist across milestone boundaries and form the program's **cross-milestone memory**:

### 6a. Architecture Folder (`.dev/architecture/`)

Maintained by the project-architecture skill after each milestone's post-housekeeping step. Contains:
- `module-map.md` — service-to-file mapping at current HEAD
- `public-interface-inventory.md` — all §9.1 REST endpoints, Pydantic model signatures, SourceAdapter ABC
- `data-contract-registry.md` — `ProcessingState` enum, schema tables, volume paths, embedding pin
- `known-coupling-surfaces.md` — where services are coupled: `state-worker` ↔ all workers; `batch-poller` ↔ `enrichment-batcher`; `vector-writer` ↔ `query-api` via BM25/LanceDB/DuckDB files

The architecture folder is the **context a pre-plan reads instead of re-exploring the full codebase**. Pre-plan exploration scope is: charter spec slices + prior §8 handoff + architecture folder. Not the full codebase, not the full spec.

**Staleness rule.** If the pre-plan context map SHA does not match the prior milestone's §8 handoff SHA (because someone committed outside a milestone workflow), re-run pre-plan exploration before re-planning. Stale architecture context is worse than no architecture context.

### 6b. Auditor §8 Handoffs (`.dev/plans/<m-plan>/handoff.md`)

Each milestone's auditor produces a §8 handoff containing:
- HEAD SHA at handoff time
- Verification command and result (clean tree, specific `curl` or test command output)
- Landed contracts summary (all contract surfaces extended during the milestone)

The **next milestone's pre-plan consumes this handoff as its primary context seed**. Specifically: the "landed contracts" section of the M<n-1> handoff feeds directly into the M<n> orch plan's §0 ("context from prior milestone"). Without this, orch planners re-derive contracts from scratch, introducing drift risk.

### 6c. Decision Logs (`.dev/decision-logs/<m-plan>/`)

For every subtask that extends a contract-anchor surface, a decision log records: what was decided, why, what alternatives were considered, and what was deferred. Decision logs are:
- Consumed by the auditor to verify intent alignment (auditor-review skill §narrative-blind cold read)
- Superseded (with pointers) when a prior decision is amended in a later milestone
- Referenced by the project-architecture skill when updating `data-contract-registry.md`

Decision logs are **not retrospective notes** — they are written by executors at implementation time, before the auditor review. A missing decision log for a contract-anchor subtask is an auditor finding.

---

## 7. What Orch Skill Rules This Program Must Respect

Every M-plan produced by the orch skill must comply with these program-level constraints:

### 7a. Binding Artifact Path

The orch skill's §2 contract seeding requires a binding artifact path. For every M-plan in this program, the binding artifact is:

```
bishop_spec_0_6.md (version 1.5.0, status phase1_approved)
```

This path must be a tracked repo path (G0). If the spec is moved or renamed, the charter must be amended with the new path before the next M-plan begins.

**Corollary.** No M-plan may define a spec section as "non-binding" or "advisory." The spec is binding; the charter defines which sections each M-plan reads. A section not listed in a milestone's spec reference block is **not-yet-applicable**, not non-binding.

### 7b. Context Map for Unknown Files

When the pre-plan skill encounters files whose structure is not known from the charter's spec references, it must map them before orch proceeds. The charter's spec reference blocks define **minimum required reading** per milestone — they do not exhaustively list every file a pre-plan may need to read. Pre-plan exploration scope is: charter slices + prior handoff + architecture folder + any files directly referenced by those documents that are not already in scope.

Pre-plan must not pass unknown file structures to orch as "TBD." Every contract surface in the orch plan's §2 must be grounded in either the spec (by line range) or the architecture folder (by module-map entry).

### 7c. 4–7 Subtasks Per Plan

The invocation stubs in §6 of the charter include expected subtask count guidance (4–7 per milestone). The orch skill must not produce more than 7 subtasks without a documented justification in the plan's §1 rationale. Subtasks above 7 indicate either scope creep (the milestone is too large) or unnecessary granularity (merge related subtasks). If a milestone consistently requires more than 7 subtasks, escalate to the charter owner for a milestone boundary review.

### 7d. §8 Clean-Tree Verification

Every auditor §8 handoff must include a clean-tree verification: `git status` shows no uncommitted changes, and the HEAD SHA matches what the executor committed. This is non-negotiable — a handoff with uncommitted changes is not a valid handoff.

### 7e. Amendment vs. Re-plan

If an executor discovers mid-milestone that a contract surface must change (e.g., a new field is needed on a Pydantic model, or a REST endpoint needs a different response shape), the correct action is an **orch §7 amendment**, not a re-plan. The orch plan's §7 section is designed for this. A re-plan discards executor context and packet history; an amendment is a scoped change to specific contracts.

If the discovery is that a **new stage is needed** (e.g., a previously-unspecified worker service must be added), that stage belongs in the **next M-plan**, not in the current one. The current milestone's exit gate must still be achievable without the new stage. If it is not, the milestone boundary must be revised via a charter amendment before proceeding.

### 7f. Non-Goals Boilerplate

Every M-plan §1 non-goals section must include the line:

> All items in §23 and §24 of `bishop_spec_0_6.md` are non-goals for this plan.

This prevents scope creep from "nice-to-have" deferred items being absorbed into milestone execution without explicit charter authorization.

---

## 8. Methodology Notes (Process Decisions)

### Why Not One Mega-Plan

A single orchestrator plan covering all 25+ §22 checklist items would fail on four orch discipline grounds:

1. **§2 contracts unmaintainable.** `state-worker` REST endpoints, `ProcessingState` enum, and Pydantic models are extended in almost every subtask. At 25 subtasks, every contract change requires a sweep across all packets to verify consistency. The amendment process becomes the critical path.

2. **Parallel subtask collisions.** `state-worker` (§6.2, §9.1) and `batch-poller` (§5.7, §9) are cross-cutting hubs touched by multiple pipeline stages. Parallelizing subtasks that both extend `state-worker` produces write collisions on the contracts table. The orch skill's §5.4 "hidden couplings" check would flag this, but flagging is not a fix — the fundamental decomposition is wrong.

3. **Executor packets unusable.** An executor packet for "implement pre-filter worker" that references a `BatchRecord` schema not yet defined (because the schema packet is also in-flight) produces a packet that cannot be executed without resolving the dependency first. The packet is technically in the plan but practically blocked. This is the same problem as a horizontal decomposition, dressed up in a single large plan.

4. **Auditor §8 handoff meaningless.** An auditor reviewing 25 subtasks across 9 services cannot produce a meaningful §8 handoff — the verification surface is the entire program. The auditor handoff is designed for a narrow, well-defined scope. At full-program scope, it degenerates into "all tests pass," which is not useful as a contract anchor for the next planning cycle.

### Why Not Parallel M-plans

The milestone sequence is strictly serial because the pipeline is a data dependency graph. M3 cannot run in parallel with M2 — `pre-filter-worker` needs `DISCOVERED` entries that only M2 produces. M5 cannot run in parallel with M4 — enrichment needs `SCRAPED` entries that only M4 produces. The only intra-milestone parallelism available is within a single milestone's subtasks, not across milestones.

The one structural exception is M8 (remaining adapters), where each adapter is independent. But M8 itself cannot begin until G4, G5, and G6 are satisfied — which requires M7 to be complete. The M8 adapters can be implemented in parallel as subtasks within the M8 orch plan, not as independent M-plans.

### Why Sequential Rather Than Concurrent Charter Planning

This charter was produced before any M-plan is executed. The milestone definitions are seeded from the charter prompt but **may be adjusted** by the first M0 pre-plan if a hard dependency conflict is found. The charter's authority is coordination, not implementation. If a pre-plan discovers that M1's scope is too large for 7 subtasks, the charter's M1/M2 boundary may be revised. Any such revision must be documented in this rationale file with a dated entry explaining what changed and why.

---

*Rationale version 0.1.0 — 2026-06-09 — Alejandro Garay Frontini*
