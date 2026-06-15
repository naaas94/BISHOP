# Learning retrospective — m3-prefilter

## 1. Task context

- **Task:** M3 — Pre-filter Slice (June 2026)
- **What it produced:** A versioned NL relevance profile (`professional_v1.0.0`), a shared profile renderer with JSON-canonical SHA-256 hashing, state-worker batch registration/lifecycle endpoints, a `pre-filter-worker` that polls `DISCOVERED` entries and submits Anthropic batch jobs, and a `batch-poller` that recovers in-flight batches on restart, posts results back to the hub, and enforces a 48-hour timeout.
- **Why this qualifies:** Two architectural subtasks (profile hashing + batch lifecycle API), a new async two-service pipeline pattern (submit → external wait → poll → apply), and first real Anthropic Batch API integration. Live compose immediately after M3 surfaced three production bugs that mocked CI never touched — that's enough signal to compound.

---

## 2. What I now understand that I didn't before

### Async batch pipelines are state machines across three owners, not two services

Before M3 I thought of pre-filter and batch-poller as "the Anthropic side" of the pipeline. After building it — and especially after the live sweep/orphan incident — I see three independent state machines that must stay aligned:

1. **Manifest rows** (`DISCOVERED` → `RELEVANCE_QUEUED` → passed/rejected)
2. **`batches` table rows** (`submitted` → `processing` → `completed` / `failed` / `batch_timed_out`)
3. **Anthropic's external batch** (opaque until polled)

The lock-state recovery sweep only knew about manifest timestamps. It had no awareness of in-flight `batches` rows. So when the poller went down long enough, the sweep released entries back to `DISCOVERED` while Anthropic still held results and SQLite still had `submitted` batches. The poller came back, fetched valid Anthropic results, and got `409 invalid_transition` forever.

**The lesson:** any background sweep that resets "stuck" work must consult every system that has claimed that work — not just the manifest's own clock. "Accepted per spec G4 caveat" in the plan was technically true and operationally naive.

### Mocked protocol tests can green-light wrong SDK calls

The batch-poller crash (`client.batches` vs `client.messages.batches`) is the clearest example. Submitters used the correct namespace; the poller used a plausible-sounding wrong one. Unit tests injected fakes at the protocol boundary, so the wrong path never executed against a real SDK shape.

Same class of problem for `custom_id`: the plan assumed `custom_id = source_id` because that's the natural primary key. Anthropic's wire format allows `[a-zA-Z0-9_-]{1,64}` — canonical BISHOP IDs have colons, dots, slashes. G3 (`messages.create`) passed; batch submit 400'd. Worse, the error handler lumped all 400s into `model_string_fatal`, so Docker logs pointed at the model string when the payload field was wrong.

**The lesson:** for external APIs, I need at least one test that asserts the *actual SDK call path* (method name, namespace, argument shape) against a thin mock of the real client object — not just a hand-rolled protocol fake. And G3 probing `messages.create` does not validate batch-specific constraints.

### Profile hash is an audit anchor, not a prompt checksum

The T2 work (NL profile YAML + renderer) forced a distinction I had hand-waved before:

- **`canonical_hash`** — JSON-canonical SHA-256 of the YAML dict *minus* the hash field itself. Proves the profile artifact wasn't tampered with between commit and batch time.
- **`render_profile_prompt()`** — deterministic markdown template for the LLM. Intentionally *not* hashed.

Hashing the prompt would couple audit integrity to template formatting choices (section order, newline style). Hashing the structured YAML dict ties integrity to semantic content. The subtle trap: the hash input is the *full YAML dict* including metadata keys outside the pydantic `ProfileDocument` model — not just the "business fields." A naive reading of §11.2 would miss that.

### Submit-before-register is a deliberate orphan risk, not an accident

The pre-filter-worker submits to Anthropic, then calls `POST /batches`. If registration fails, an external batch exists with no SQLite row. M3 documented this, tested it, and shipped it. The alternative (register first, then submit) would leave SQLite rows pointing at batches that never reached Anthropic.

Neither ordering is free. I now think of this as a **saga without compensation**: the plan chose "orphan external batch" over "orphan internal record" and didn't add cancel/retry logic. The post-M3 `invalid_source_state` guard at registration time closes the *duplicate submit* half of the problem but not the *orphan spend* half.

### Deferred validation is a loan with interest

The state-worker batch registration API (T3) deliberately did not validate that `source_ids` were actually in `RELEVANCE_QUEUED` at registration time — that was deferred to the pre-filter integration layer. In mocked tests the ordering always held. In production, after sweep released claims, pre-filter could re-poll and register duplicate batches until state-worker started returning `409 invalid_source_state`.

**The lesson:** "the worker owns ordering" is fine as a design principle, but the hub should still reject impossible states. Defense in depth at the single-writer boundary is cheaper than debugging infinite poll loops in compose.

---

## 3. Decisions I made and would make again

**Split pre-filter-worker and batch-poller into separate services and subtasks.** Charter semantics (startup scan is poller-only, distinct restart behavior) map to real operational boundaries. Merging them would have hidden the sweep/orphan coupling inside one process and made the failure harder to reason about.

**Close the state-worker batch API gap in M3, not M5.** Without `POST /batches`, workers would write SQLite directly or leave batch provenance orphaned. The hub-as-single-writer pattern is load-bearing; extending it early was correct even though it was the highest re-plan-risk surface.

**JSON-canonical dict hash over raw YAML bytes or prompt text.** Environment-independent, parser-independent, and separates audit integrity from LLM formatting. The T2 decision log captures the reasoning well; I'd reuse this pattern anywhere versioned config drives LLM behavior.

**Persist `source_ids` on `BatchRecord` at registration.** Timeout and restart recovery need to know which manifest rows belong to a batch without inferring from `pre_filter_batch_id` (unset until results land). Storing the list at submit time was the right denormalization.

**Hardcode `professional_v1.0.0.yaml` for M3 instead of a pointer file.** One fewer moving part while the profile system is new. Pointer files are for when selection logic actually varies.

---

## 4. Decisions I made that I would change

**Treat "live compose deferred per M2 pattern" as sufficient exit evidence.** Mocked integration tests proved wire contracts and happy-path state transitions. They did not prove SDK namespace correctness, wire-format validation on `custom_id`, transport error resilience, or sweep/batch interaction under downtime. Three hotfixes landed the same day as first real `docker compose up`.

*Better rule:* any milestone that introduces a **new external API surface** (not just new internal routes) gets one manual compose smoke in the exit gate, or an explicit charter waiver naming which failure classes remain unproven. "Deferred per M2 pattern" became a reflex.

**Accept `custom_id = source_id` without checking Anthropic's field constraints in pre-plan.** The scout grep found the model string and route literals but not batch payload validation rules. A five-minute read of the Batch API docs during planning would have caught the encoding issue before implementation.

*Better rule:* for each external write path in §2, add a row for **wire-format constraints** (max length, allowed charset, required fields) — not just semantic mapping.

**Defer registration-time manifest validation with only a T4 integration test as backstop.** The integration test assumed happy ordering. Production needed hub-side `409 invalid_source_state` and sweep/batch coupling — neither was in the original M3 scope.

*Better rule:* when deferring hub validation because "the worker owns ordering," still file a follow-up contract row: *hub rejects physically impossible states* (entries not in expected lock state). Don't treat worker ordering as a substitute for hub guards.

**Let G3 mean only `messages.create` and call the milestone "G3 verified" in mocks.** Charter exit language says "model string confirmed via direct API call." CI SKIP-without-key is pragmatic, but I blurred "pinned constant matches spec" with "API accepts our payloads." Those are different claims.

*Better rule:* separate **G3-model** (string valid for Messages API) from **G3-batch-payload** (a minimal batch create succeeds) in gate vocabulary. One live probe or an explicit waiver per dimension.

**Ship submit-before-register without a decision log at architectural tier.** Audit accepted it at standard tier for the pre-filter loop subtask. It's a distributed-systems tradeoff that kept biting (M5 enrichment copied the pattern; post-M3 fixes addressed symptoms). Should have been logged when first identified in cold-read.

---

## 5. Patterns in my own thinking

**Over-trusted mocked integration as a stand-in for "the pipeline works."** M3 had good contract coverage — every §2 row with a named test, 20-entry e2e, startup scan restart. I felt done. The gap was *fidelity of the mock boundary*, not *coverage of the contract table*. I conflated "auditor pass" with "ops-ready."

**Under-weighted coupling C5 because the spec already had a caveat.** Plan §5.4 flagged lock-sweep vs in-flight batch as confirmed coupling, disposition "treat-as-prediction," spec G4 accepts duplicate submit risk. That framing made it feel like someone else's problem. In compose it became *the* problem — infinite 409 loops, duplicate Anthropic spend. I used "spec accepts it" to avoid designing the sweep/batch guard in M3.

**Repeated the handoff-not-in-HEAD pattern without treating it as a learning.** M0, M1, M2, M3, M4, M5, M7 all filed the same audit finding. I keep fixing it post-audit instead of changing when handoff gets committed. That's sunk-cost attachment to "T6 commits code, handoff is orchestrator cleanup" — a habit, not a reason.

**Right push-back: keeping T2 as one subtask (YAML + renderer).** I might have been tempted to split for parallelism. The hash must be computed by the same code path at authoring and batch time; one subtask enforced that. Trusting the plan here was correct.

**Right skepticism: not deferring the batch lifecycle API to M5.** That would have forced hub drift or direct SQLite writes. The re-plan risk was real but the alternative was worse.

---

## 6. Open questions

- **What's the right compensation story for submit-before-register?** Cancel Anthropic batch on register failure? Register as `pending` before submit and flip to `submitted` only after Anthropic ack? Outbox pattern? M3 picked the simplest ordering; I don't yet know the right saga shape for BISHOP's cost and idempotency constraints.

- **How should charter exit gates relate to CI economics?** Live Anthropic probes cost money and need secrets. Mocked tests scale. I don't have a clean vocabulary yet for "proven at wire-contract layer" vs "proven at vendor-acceptance layer" without sounding like I'm lowering the bar.

- **When does a background sweep need a global lock vs consultative reads?** The M3 fix made sweep consult `batches` rows. As more batch types land (M5 enrichment), does each sweep rule grow ad hoc, or is there a general "in-flight work registry" abstraction?

- **Profile quality (G6) vs profile integrity (hash).** M3 ships a functional prompt template; empirical relevance tuning is M8. I don't yet know how I'll detect "hash matches but profile is bad" without expensive human eval loops.

- **Should G3 expand to a minimal batch smoke?** Cheap if it catches `custom_id` class errors early; unclear if Anthropic charges for empty/failed batch creates.

---

## 7. Single paragraph synthesis

M3 taught me that a green mocked integration gate and a passing adversarial audit are not the same as an ops-ready async pipeline — especially when three independent state machines (manifest, `batches` table, Anthropic) can drift apart under sweep, downtime, and wire-format constraints that unit tests never see. The architectural choices I'd repeat are hub-first batch registration, JSON-canonical profile hashing, and separate submit/poll services; the habits I'd break are deferring live compose for any new vendor API, treating `custom_id = primary key` without reading vendor charset rules, and letting background sweeps ignore in-flight batch claims because the spec already "accepts" the race. The real design work started when compose ran, not when pytest finished.
