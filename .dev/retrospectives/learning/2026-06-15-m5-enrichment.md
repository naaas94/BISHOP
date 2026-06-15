# Learning retrospective — m5-enrichment

## 1. Task context

- **Task:** M5 — Enrichment Slice (June 2026)
- **What it produced:** Shared enrichment library (`bishop_shared` truncation, taxonomy, prompts, parsers), state-worker hub extensions (submit transitions on batch registration, enrichment timeout paths, OOV tag persistence), a new `enrichment-batcher` service with two concurrent asyncio loops (Call 1 from `SCRAPED`, Call 2 from `ENRICHMENT_STAGE2_QUEUED`), `batch-poller` v2 dispatching all three batch types, and an integration gate proving five entries reach `VECTOR_WRITE_QUEUED` with enrichment fields and OOV logs populated.
- **Why this qualifies:** Three architectural subtasks (shared enrichment surface, hub amendment, Call 2 cache/profile semantics), first two-call LLM enrichment stage in the pipeline, and the moment the batch-poller graduates from a single-purpose M3 tool into a shared completion engine for the whole ingest path.

---

## 2. What I now understand that I didn't before

### Two-call enrichment is a dependency graph, not "one big prompt twice"

Call 1 consumes raw (truncated) content and *produces* `entry_type`, `summary`, `tags`, `concepts`, `challenge_hooks`. Call 2 consumes only **title + summary** plus the cached NL profile and produces relevance scoring. That separation is load-bearing:

- Call 2 must not see full `content_raw` — cost, context window, and the risk of the model re-deriving metadata Call 1 already committed.
- Call 2 is where **profile caching** (`cache_control: ephemeral` on the system block) pays off: the profile is identical across many entries in a batch; Call 1 content is per-entry and uncached.

Before M5 I treated "enrichment" as a monolithic "make the entry smart" step. After wiring it, I see it as **extract structured fields first, then score against a stable persona** — two different optimization problems with different input shapes and different failure modes.

### Truncation strategy has a chicken-and-egg at Call 1

Spec §13.1 gives per-`entry_type` strategies (paper abstract+body, HF model-card YAML, github header, etc.), but Call 1 is what *determines* `entry_type`. M5 resolved this by routing on **`source`** at truncation time, not `entry_type`: arxiv/openreview/semantic_scholar get the paper strategy; huggingface/github get specialized paths only when a hint exists; everything else gets beginning/end fallback.

That's not a hack — it's acknowledging that **ingest metadata and semantic classification are different clocks**. Source is known at scrape time; entry type is model output. Designing truncation as a function of `(source, content_raw, optional_hint)` instead of `(entry_type, …)` is the general pattern for any pipeline where classification happens inside the LLM step you're preparing input for.

The residual risk I still carry: paper truncation quality on real M4 HTML (`Abstract` heading heuristics, empty body after strip) is unproven at scale. Unit fixtures pass; live ArXiv HTML is a prediction, not a closed fact.

### `register_batch` is the submit transition, not just provenance

M1 left `mark_enrichment_stage*_submitted()` helpers with no REST caller. M3 taught me that `POST /batches` registers a `BatchRecord`. M5's insight — obvious in retrospect — is that **registration and submit transition are the same atomic moment**: the worker has already sent work to Anthropic; SQLite must move entries to `_SUBMITTED` in the same transaction as the batch row insert, or the poller's result POST will 409 forever.

I no longer think of batch registration as "bookkeeping." It's the **commit point** of the distributed saga between manifest state, SQLite batch row, and external Anthropic batch. Pre-filter, enrichment stage 1, and enrichment stage 2 all share that shape; only the target `batch_type` and transition helpers differ.

### OOV tags need a return path through the hub, not a side channel

The natural implementation urge: batch-poller strips invalid tags locally and logs them. That violates sole-writer discipline and loses auditability. The correct shape is a **wire field** (`oov_tags_stripped`) on the stage1 results POST, persisted inside the existing H3 success transaction in state-worker.

What I learned about schema design: OOV rows need `entry_type` for §7.5, but `entry_type` comes from the same Call 1 response that produced the stripped tags. The happy path always has both. The edge case (stripped tags, no type) is real but rare — deferring insert without a row is acceptable if documented, not if silently assumed impossible.

### batch-poller v2 is a router, not a rewrite

Extending M3's poller meant: widen `TRACKED_BATCH_TYPES`, branch `poll_once` / `_handle_batch_complete` on `batch_type`, add two result POST client methods, reuse T1 parsers. Pre-filter behavior stayed on its branch; regression tests were the safety net.

The pattern generalizes: **one poller service per external async API namespace** (Anthropic Messages Batch), with **batch_type as internal dispatch key**. Adding a fourth batch type in the future should be additive handlers, not a new service — unless dispatch complexity forces a split.

### Dual `asyncio.gather` in one enrichment-batcher is the right default for independent stages

Stage 1 polls `SCRAPED`; stage 2 polls `ENRICHMENT_STAGE2_QUEUED`. They don't depend on each other within a tick — entries flow through state-worker between them. Running both cycles concurrently inside one process avoids deploying two services while honoring charter "dual asyncio tasks."

Tradeoff I'm aware of: one shared `StateWorkerClient` and one poll interval for both stages. If stage 2 backlog grows while stage 1 is idle, they still wake together. For M5 scale that's fine; if enrichment becomes the bottleneck, independent intervals or services may be warranted.

### M1 front-loaded enrichment routes; M5 was mostly wiring

A large fraction of M5 was connecting things M1 already defined: enrichment result POST routes, H3 multi-step writers, poll claims for `SCRAPED` and `ENRICHMENT_STAGE2_QUEUED`. The charter's vertical-slice strategy paid off here — M5 felt like **closing gaps flagged in the context map** (submit hook, timeout dispatch, OOV insert) more than inventing a new subsystem.

That reframes how I read "deferred to M5" in older decision logs: not procrastination, but **sequencing honesty** — don't wire submit transitions until a worker exists that calls them.

### Mocked e2e proves state-machine coherence, not prompt quality

M5 integration seeds synthetic `content_raw`, mocks Anthropic, and asserts terminal states and field population. That's the right gate for a milestone slice: **can the pipeline move entries and persist fields correctly?** It does not answer whether Call 1 summaries are good, whether truncation preserves the right technical content, or whether G3's model string will still be valid next quarter.

I now separate **coherence gates** (milestone CI) from **quality gates** (charter G6, live sampling, backfill validation). Conflating them creates false confidence.

---

## 3. Decisions I made and would make again

**Keep state-worker as sole SQLite writer; extend hub via `register_batch` hook instead of new routes.** One transaction, one REST surface workers already call, no poller-side DB access. Same principle as M3 batch API — correct again.

**Put truncation, taxonomy, prompts, and parsers in `bishop_shared`.** Enrichment-batcher and batch-poller both consume them; duplicating in services would drift within one milestone. Shared library with named contract tests is the cheap anti-drift mechanism.

**Sequence enrichment-batcher T3 → T4, not parallel.** Both touch `main.py` and shared clients. Flag 6 in the context map was real; the DAG edge prevented a merge conflict that would have wasted executor time.

**Route OOV persistence through `oov_tags_stripped` on the wire.** Preserves audit trail, keeps batch-poller as HTTP client only, and reuses H3 atomicity. Rejected alternative (poller writes `oov_tags_log` directly) would have been faster to code and wrong for the architecture.

**Use tiktoken `cl100k_base` as the truncation ruler.** Spec says tokens; character cuts are wrong. Accepting tokenizer mismatch vs Anthropic's internal count is a documented prediction, not silent equivalence.

**Treat live Docker compose as manual, same as M3/M4.** M5 shipped clean mocked gates; I would still make that choice at M5 time — but I hold the M3 lesson that **live compose finds SDK and wire-format bugs mocks miss**. Schedule manual smoke before calling enrichment production-ready, even when CI is green.

---

## 4. Decisions I made that I would change

**Let handoff and plan §8 lag implementation SHA again.** M1 taught this; M5 repeated it. The code was correct at `0331dd5`; audit archaeology was messy. Better rule: **T6 is not done until `handoff.md` is committed in the same commit chain as the gate script**, or T6 kill criteria explicitly require it. This is operational discipline, not architecture — but I keep paying interest on the loan.

**Leave `plan.md` §8 as a placeholder when `handoff.md` exists.** Creates two sources of truth; F-003 persisted because I treated handoff as canonical without updating the plan stub. Next time: either inline §8 in `plan.md` at completion or add one line at the top: "§8 canonical in `handoff.md` only" and bump plan status to Complete.

**Defer exhaustive §2 logging enumeration without amending the contract.** Auxiliary events (`empty_poll`, `unsupported_domain`) are useful; fighting F-005 retroactively is silly. I should have defined §2 logging as **minimum required events** plus "implementations may emit additional operational events" at plan time — or added rows when the executor shipped them.

**Rely on `entry_type` presence for OOV insert without a negative test.** The deferral is intellectually honest; the missing negative test means I won't notice if a parser regression drops `entry_type` while still stripping tags. Cheap fix worth doing when touching that path again.

---

## 5. Patterns in my own thinking

**I overweight "highest re-plan risk" as "where execution will hurt."** T2 (hub amendment) was named top risk; it landed in one commit. The actual friction was process closure and inherited M1 test debt — same pattern as M2/M4. I should track **risk category**: architectural risk vs closure hygiene vs inherited debt. They need different mitigations.

**I underweight closure as a first-class deliverable.** I celebrate green pytest and treat handoff as paperwork. The methodology retro is right: implementation methodology worked; program hygiene leaked. I gravitate toward "the system runs" and defer "the artifact chain is auditable" — probably because agents finish code faster than they finish narrative bundles.

**I trust the vertical-slice charter more after M5.** Worried M5 would be a sprawling "enrichment system"; it was six subtasks with a clean DAG because M1/M3/M4 had already narrowed the surface. Pushing back on monolithic plans was right; I should trust that framing earlier when scoping new work.

**I accept "treat-as-prediction" labels honestly — good — but don't always schedule when those predictions get falsified.** Truncation quality and live HTML are flagged predictions sitting until G6/M8. That's correct deferral only if I actually run G6 before backfill, not if it becomes permanent background noise.

---

## 6. Open questions

- **How bad is tiktoken vs Haiku token counting in practice?** Systematic over- or under-truncation would degrade `challenge_hooks` quality before any test fails. Worth a small live sample comparing tiktoken count to Anthropic usage metadata on a handful of ArXiv entries.
- **When does enrichment-batcher need split intervals or split services?** `gather` + shared interval is simple; I don't know the backlog threshold where stage 2 starvation matters.
- **Is markdown-fenced JSON in batch responses common enough to matter?** Deferred fence stripping in T1; production will answer this. If Anthropic batch output is consistently raw JSON, the regex parser is fine; if not, that's a cheap hardening pass.
- **Profile below Anthropic caching minimum — what's the cost curve?** `cache_control` is emitted always; caching may no-op until the profile grows. I don't have intuition for when ephemeral cache starts paying off on Call 2 batches.
- **Orphaned Anthropic batch on POST /batches failure — when do I add compensation?** M3 CR-1 pattern accepted for M5. At what operational frequency does "log and move on" become unacceptable spend?

---

## 7. Single paragraph synthesis

M5 taught me that enrichment is two coupled problems — structured extraction from truncated source-shaped content, then profile-conditioned scoring on summary only — glued together by the same batch saga M3 established, with `register_batch` as the atomic commit point between manifest state and external Anthropic work. The hardest design choices (truncation before `entry_type` exists, OOV data routed through the hub wire, poller as batch-type router) were architectural and mostly right on the first pass; the recurring failure mode was mine, not the agents': treating green mocked gates as milestone completion while letting handoff and plan narrative trail the implementation SHA, which I already knew was a problem after M1 and still didn't fix as a personal habit. The compounding insight for Bishop specifically is that vertical slices work because earlier milestones pre-build the state machine — M5 was wiring and shared libraries, not greenfield invention — and the next risks are quality and live-wire validation, not DAG structure.
