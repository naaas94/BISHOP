# Learning retrospective — m1-state-kernel

## 1. Task context

- **Task:** M1 — State Kernel
- **Date:** 2026-06-11 (primary execution); follow-on docker fix 2026-06-13
- **Produced:** Complete `state-worker` service — Alembic schema (six SQLite tables), transition engine, all sixteen §9.1 REST routes, background sweeps, G2 contract gate (`scripts/verify-g2.sh`), and post-audit alert dual-write (`emit_alert`).
- **Why this qualifies:** Three architectural subtasks (schema foundation, transition engine, alert logging); introduced the program's contract anchor — every downstream worker (discovery, pre-filter, content, enrichment, indexing) will poll and POST through this hub. First milestone where the spec's state machine became executable code rather than prose.

---

## 2. What I now understand that I didn't before

### The state kernel is a single-writer coordination layer, not a generic CRUD API

BISHOP's pipeline is not "services talk to each other." It is: workers call `state-worker` REST endpoints; only `state-worker` mutates `processing_state` and owns atomic poll-and-claim. SQLite is the persistence layer behind that API, not a shared database every service opens. That discipline is what makes double-poll emptiness and H3 rollback testable — if a future worker bypasses REST to write SQLite directly, the whole claim model breaks silently.

I had treated "state-worker implements §9.1" as an endpoint checklist. It is actually a **concurrency contract**: one writer, explicit transaction boundaries, poll maps that define which transitions happen atomically on read.

### aiosqlite transactions are explicit, not contextual

For multi-step enrichment writes (the spec's H3 pattern), `async with conn` is **not** a transaction boundary in aiosqlite. Claims and H3 sequences need literal `BEGIN` → work → `COMMIT` / `ROLLBACK`. I would have assumed the async context manager handled this — it doesn't. Any future change to transition code that wraps operations in `async with conn` without explicit BEGIN would look correct and be wrong.

### Spec gaps become binding derived contracts

Several §9.1 request/response shapes are undocumented in the normative spec. M1 derived them from §5/§7 prose, logged them in the schema-foundation decision log, and enforced them via contract tests. Those derived models are now **de facto API** for M3/M5 workers. I underestimated how sticky "temporary derived wire" becomes — downstream code will conform to what shipped, not what the spec eventually says.

Concrete examples I can reconstruct without the plan:
- `POST /manifest/pre-filter-results` body with `{batch_id, profile_version, entries: [{source_id, decision, pre_filter_rationale}]}`
- `GET /escalations` returning entries with embedded `error_log` arrays per §14.2 panel fields

### §14.3 alerts are sibling rows, not replacements

Alert emission is a **dual-write**: one operational `error_log` row (TimeoutError, HTTPStatusError, etc.) plus a separate row with `error_class = "ALERT"` and a CRITICAL structured log with `alert_type`. Mutating the failure row to ALERT was rejected — the operational detail and the human-facing alert are intentionally separate.

This is why the escalations router test broke after alert logging landed: the wire shape is *correct* with two rows; the test was stale. I had mentally modeled `error_log` as "one row per failure event" when the spec models it as "history of attempts plus alert annotations."

### TestClient + temp SQLite ≠ Docker layout

The Alembic root-resolution bug (2026-06-13) crystallized this: `_repo_root()` used `Path.parents[3]`, which exists in a deep repo checkout (`…/services/state-worker/app/db.py`) but not in the container (`/app/app/db.py` has only three ancestors). Python evaluates tuple elements eagerly, so the fallback candidates never ran. **147 pytest passes did not prove `docker compose up` works.**

G2 deliberately defers Docker — that is a reasonable milestone tradeoff — but I now treat "green pytest" and "green compose" as orthogonal signals, not substitutes.

### Observability contracts are as binding as type contracts — and easier to skip

The first audit found zero `logger.critical` / `alert_type` in the codebase despite plan §2 declaring them binding. Functional tests (idempotency, double-poll, H3 rollback) all passed. The logging row was hollow until an adversarial cold-read caught it.

I conflated "G2 charter criteria pass" with "milestone complete." Charter G2 covers pipeline semantics; §14.3 alert emission is a separate observability surface that also gates merge quality.

### Sweep timing without `state_entered_at` is a deliberate imprecision

Lock-state recovery uses `discovered_at` / `ingested_at` as age proxies because §7 has no per-state timestamp column. The 15-minute default threshold absorbs most false positives, but a worker holding a claim legitimately for 14 minutes then failing could interact badly with sweep logic. This was documented and deferred — not a bug, a **known approximation** I need to remember when debugging "why did this entry reset to DISCOVERED."

### JSON list columns are encoded at the state-worker boundary only

`concepts`, `tags`, etc. are `json.dumps` on write and `json.loads` on read inside state-worker. Any service that raw-SQL reads those columns gets JSON text, not Python lists. M1 owns all writes; the coupling becomes real when batch-poller or query-api read directly — which they later do.

---

## 3. Decisions I would make again

**Single-writer via REST, SQLite behind the API.** Correct for MVP scale and testability. The alternative (shared SQLite with advisory locks per worker) would multiply failure modes without simplifying the spec.

**Enums in state-worker only, not bishop_shared.** Downstream services consume string values from SQLite/API. Duplicating Python enums later is cheaper than premature shared-package coupling before the enum surface stabilizes.

**Alembic at repo root with Dockerfile COPY.** Keeps one migration history for the whole program; state-worker runs migrations on lifespan startup before serving. Correct sequencing for "health check must not race migrations."

**Decompose routers (poll/ingest vs entry writes) with assembly in a later subtask.** Let T3 and T4 develop in parallel-safe files; one subtask owns `main.py` lifespan and router registration. Avoided merge hell on the assembly point.

**Reject deferring §14.3 alerts to M2.** Audit F-004 was major for a reason — alert emission is part of the error/escalation story, not polish. Shipping transitions without alerts meant escalation paths were structurally incomplete.

**Same-transaction alert INSERT (not post-commit).** Prevents escalated manifest state without a matching ALERT row if the process dies between commits. Small correctness win that matters at 2am.

**Generalizable principle:** For hub services that own state machines, put the transition engine in one module (`transitions.py`) and keep routers thin. The ~1150-line concentration looks scary but is easier to audit than logic scattered across six router files.

---

## 4. Decisions I would change

**Treat "147 tests pass" as sufficient pre-audit confidence.** Wrong signal composition. The suite tested pipeline semantics heavily and observability barely. Better rule: before audit, grep §2 contract table row-by-row against code + named test — especially rows not in the G2 script path.

**Leave §8 handoff uncommitted at T6 closure.** Process error, not technical. Handoff archaeology is part of the deliverable; "filled in working tree" is not landed. Better rule: handoff commit is a kill criterion for the integration/contract subtask, not a separate optional doc pass.

**Accept `pass-with-conditions` on F-013 without fixing the escalations test.** Momentum toward M2 overrode a five-minute test fix. The stale test still fails at HEAD (OPEN-001) and poisons honest "full suite green" narrative through M7. Better rule: conditions on major findings block milestone sign-off until closed or explicitly waived with a dated owner — not "logged in still_open."

**Assume `parents[N]` path arithmetic works in all layouts.** The docker alembic fix was preventable with one shallow-layout unit test at schema-foundation time. Better rule: any path resolution that differs between repo tree and container gets a layout-falsifier test, even when Docker is deferred from the gate script.

**Underlying error on observability skip:** I categorized logging as "secondary" because the spec's G2 charter lists four behavioral criteria (idempotency, double-poll, H3, sweep) and none mention alerts. I mapped "charter exit gate" onto "everything that matters" — a framing error.

---

## 5. Patterns in my own thinking

**Trusted the orchestrator's T2 risk prediction.** Plan §5.3 flagged the transition engine as highest re-plan risk. T2 landed cleanly; trouble came from logging omission and handoff hygiene — areas I mentally deprioritized as "process" or "observability." I overweighted algorithmic complexity risk and underweighted contract-table completeness.

**Green tests as emotional closure.** 147 passing created a false sense of "M1 is done" before audit. I wanted to move to M2 (discovery, batches, real pipeline motion) and treated audit as a formality. It wasn't — it found a major contract hole.

**Review-driven shallow learning on transitions.** I validated agent output rather than generating the claim maps and H3 sequences myself. I can explain atomic poll-and-claim now because audit forced me to read `transitions.py` cold — not because I internalized it during execution. The methodology retro's point about review-driven vs generation-driven workflows is accurate for me here.

**Accepted pass-with-conditions as "good enough."** Sunk-cost toward downstream milestones. The escalations test failure was correctly diagnosed as stale test, not wrong implementation — which made deferral feel harmless. Harmless for wire correctness; harmful for test hygiene discipline.

**Did not push back on G2 scope excluding Docker.** Correct deferral for milestone velocity, but I didn't internalize the consequence until compose failed two days later on alembic root. Under-planned the "when do we first run compose" checkpoint.

---

## 6. Open questions

- **When does `state_entered_at` become worth a migration?** Operational false-positive sweep resets haven't appeared yet, but the proxy timestamp model feels fragile as pipeline stages get slower (enrichment batches, 48h timeouts).

- **Should `verify-g2.sh` include alert tests and a minimal compose smoke?** F-014 remains open. Where is the line between "milestone gate" and "program hygiene gate"?

- **Direct SQLite reads by query-api and batch-poller — still the right seam?** M1 assumed state-worker-only writes; M7 and ops incidents (2026-06-13 corruption) suggest multi-consumer sqlite on Windows bind mounts is fragile. Is HTTP-only reads the long-term shape?

- **`manual_retry` with ALERT sibling rows:** Re-audit noted `ORDER BY timestamp DESC LIMIT 1` without excluding ALERT rows — tie-break undefined when timestamps equal. Benign today; worth an adversarial test?

- **Derived wire models vs spec amendment:** At what milestone do undocumented §9.1 shapes get promoted into `bishop_spec_0_6.md` rather than living only in decision logs?

---

## 7. Single paragraph synthesis

M1 taught me that BISHOP's state-worker is not a REST CRUD layer but a **single-writer state machine with explicit SQLite transactions** — and that the hardest part of landing it wasn't the transition engine (which shipped cleanly) but **treating observability and handoff artifacts as first-class contracts**. Green functional tests created false confidence: alert logging was declared binding in plan §2 but absent in code until audit caught it; pytest green in a repo layout did not prove Docker worked until a path-index bug blocked compose. The most durable technical insight is smaller: §14.3 alerts are **sibling error_log rows**, not replacements, and any dual-write feature requires scanning existing tests for cardinality assumptions — a five-minute fix I deferred and am still paying for four milestones later.
