# Learning retrospective — m2-discovery

## 1. Task context

- **Task:** M2 — Discovery Slice (June 2026)
- **Produced:** The `scraper` service — first real pipeline worker after the state kernel. It discovers ArXiv papers via the Atom export API, posts manifest rows to state-worker at `DISCOVERED`, tracks per-source `last_successful_run_at`, and runs on a six-hour asyncio schedule. Also introduced `bishop_shared/enums.py` as the first cross-container vocabulary module.
- **Why this qualified:** First HTTP client service in the Bishop pipeline; first adapter-registry pattern; first split between lightweight discovery (`fetch_manifest`) and deferred full-content fetch (`fetch_content` → M4). Three architectural subtasks (foundation, adapter ABC/registry, ArXiv wire protocol) plus the failure-envelope and loop integration. This is where the pipeline stops being "one database service" and becomes a chain.

---

## 2. What I now understand that I didn't before

### Discovery and content fetch are different jobs with different failure economics

The spec's `SourceAdapter` has two methods, but M2 only implements `fetch_manifest`. That is not a shortcut — it reflects a real architectural split. Discovery is high-frequency, idempotent, and cheap: titles, abstracts, stable IDs. Content fetch is heavy, source-specific, and belongs later in the pipeline when a row has already passed relevance filtering. Putting both in one scrape pass would couple ArXiv rate limits to PDF/HTML retrieval complexity and make retry semantics muddy. I now read `fetch_content` raising `NotImplementedError("M4")` as an intentional seam, not unfinished work.

### Two layers of "slow down" are not redundant

Before M2 I would have collapsed "respect ArXiv rate limits" and "retry on 429" into one mechanism. The implementation separates them on purpose:

1. **Token bucket inside the adapter** — proactive throttle (`calls=3` per second for ArXiv). Prevents hammering the API.
2. **`failure_envelope` around the adapter call in the loop** — reactive retry with exponential backoff when the API still returns 429/5xx or the network flakes.

These answer different questions. The bucket asks "should I send this request yet?" The envelope asks "this request failed — do I try again?" Wrapping the bucket outside the envelope (or merging them) would either double-throttle or let 429 storms through if you only had the bucket. §15.3's "separate concerns" language finally clicked when I saw `acquire()` immediately before `client.get()` in `arxiv.py` and `failure_envelope(adapter.fetch_manifest, ...)` one level up in `loop.py`.

### Cross-container enum sharing without cross-container imports

State-worker owns the database and defines `SourceEnum` / `DomainEnum` in its own `app/enums.py`. Scraper cannot `from services.state_worker.app.enums import ...` — different Docker images, different `PYTHONPATH`, and importing would couple build contexts.

The pattern that works: duplicate the string enums into `bishop_shared/enums.py`, copy that package into both images, and guard drift with a test that compares literals to hardcoded spec values (not a cross-import). State-worker is deliberately *not* refactored to import shared enums in M2 — that avoids churn on a stable M1 surface. The cost is two copies until someone pays the refactor tax. The benefit is each service stays deployable in isolation. This is the microservice version of "shared kernel" — a tiny copied module, not a shared library dependency graph.

### Idempotency is state-worker's job; the scraper should stay dumb

The scraper does not deduplicate `source_id` before `POST /manifest/batch`. On re-run, it re-posts everything it fetched; state-worker returns `skipped` for duplicates. That felt wrong at first — why waste bandwidth? — but it is correct: the scraper has no durable manifest index, and pre-filtering differently than state-worker would create silent divergence (post fewer rows than the source actually has, or skip rows state-worker would have accepted). The kill-criterion test mocks `skipped >= 1` on second batch; G2 contract tests guard the state-worker side. Trust the single writer.

### ArXiv has a real query API, and it is not RSS

ArXiv exposes an Atom export endpoint (`export.arxiv.org/api/query`) with structured `search_query` syntax — category filters, `submittedDate` ranges, OR-unions across `cs.AI` / `cs.CL` / `cs.LG`. RSS is a separate, coarser path. For incremental discovery ("papers since last run"), the export API's date-range query is the right tool. RSS deferral to M8 is not laziness; it is choosing the API that matches the spec's incremental semantics.

Practical parsing note: Atom XML uses namespaced tags (`{http://www.w3.org/2005/Atom}entry`), entry IDs are URLs with version suffixes (`2301.00001v2`), and abstracts may contain HTML entities — hence a small `HTMLParser` unescape, not naive string strip. Malformed entries (missing id/title) are skipped silently; that is a conscious trade for M2 smoke, not an oversight.

### Empty fetch still advances `last_successful_run_at`

Reading `loop.py` cold: if ArXiv returns zero entries, the cycle still calls `post_manifest_batch([])` and then `post_scraper_state`. That means a successful-but-empty poll moves the incremental window forward. Operationally, that prevents a quiet period from causing infinite re-query of the same date range; it also means a misconfigured query that always returns empty will silently advance state. Worth knowing for M3+ monitoring — not a §2 violation, but a behavior to watch.

### Review-driven execution produces shallow familiarity

I validated green tests and audit pass-with-conditions. I did not personally construct the Atom query builder or reason through the envelope's `attempt <= max_retries` loop invariant. The methodology retro caught process leaks; this section catches the cognitive one: I *know the architecture is right* because the auditor verified it, not because I derived it. That is fine for velocity, but the learning has to happen here or it does not compound.

---

## 3. Decisions I would make again

**`bishop_shared/enums.py` over scraper-local literals.** M4 content-scraper and every downstream client will need `SourceEnum` strings. One small shared module copied into images beats N duplicate string literals with N drift vectors.

**Atom export API over RSS for M2.** Date-range incremental queries are first-class in the export API. RSS would have forced a different incremental model.

**7-day default backfill window over spec's 60-day production value.** First `docker compose up` should not pull two months of ArXiv across three categories. Production override via env is enough; document the 60-day intent in the decision log.

**Fixture-only CI, no live ArXiv gate.** Network flakiness on `export.arxiv.org` would make CI non-deterministic. Recorded Atom XML fixtures test parsing; live smoke stays manual — same pattern as later milestones.

**Charter override: one adapter in registry, not spec §10.2's seven.** Shipping seven stub adapters would be scope theater. A registry with one real entry plus an extension point (`ADAPTER_REGISTRY` list) is honest about M2 and M8.

**Principle that generalizes:** *bind the milestone to a runnable checkpoint, not to the spec's full eventual surface.* The spec describes the cathedral; the charter slice describes the door you need to walk through next.

---

## 4. Decisions I would change

**Commit plan artifacts in the same closure commit as implementation.** Code landed at `0954ea8`; `.dev/plans/m2-discovery/` stayed untracked until a follow-up commit. I had already lived through this on M0/M1. The error was not ignorance — it was treating "the code is merged" as done while treating orchestration docs as optional paperwork. Better rule: *implementation SHA is not closure until `git show HEAD:handoff.md` resolves.*

**Run an amendment cycle for audit conditions instead of logging them.** M1 taught T7–T9 remediation packets. M2 audit said pass-with-conditions; I committed the plan dir and moved to M3 without closing F-004 (loop-level retry-exhaustion test) or F-009 (T1 decision log supersession). Logging conditions in `dev_log.md` felt like resolution; it was deferral without a waiver in handoff §8.6. Better rule: *conditions are either fixed in a named amendment subtask or explicitly waived in committed handoff — no third bucket.*

**Push back on handoff evidence rows that cite the wrong test.** Handoff §8.3 mapped rate-limiter ordering to `test_token_bucket_throttles`, which tests `calls=1` bucket math, not adapter acquire order. I accepted "green audit" without grep-checking the cited proof. Better rule: *when §2 says "Proof test: X", run X and confirm it falsifies the claim before signing handoff.*

**Underlying error:** trust transfer from agent output to "done" without spot-checking the highest-risk claims (integration seams, cited tests). Time pressure was low; this was habit, not schedule.

---

## 5. Patterns in my own thinking

**Defaulted to "tests green = understood."** 78 passing M2 gate tests gave a false sense of mastery. Several tests cover happy paths and envelope unit behavior; the loop's `RetryExhaustedError` branch and empty-manifest state advance are behaviors I only know from the audit cold-read, not from having reasoned about them during execution.

**Under-planned closure, over-planned adapter decomposition.** The five-subtask DAG (foundation → ABC/registry → failure envelope ∥ ArXiv adapter → loop/compose gate) was well-sized. What was under-planned was the last mile: artifact commit hygiene and audit remediation — exactly where M1 had already failed once.

**Trusted the orchestrator on §5.4 C4 disproof.** The plan claimed a unit test proved rate-limiter acquire order; it did not exist. I should have treated adversarial-pass "disproven by" lines as falsifiable hypotheses to verify before audit, not narrative flourish.

**No sunk-cost on scope, but sunk-cost on "move forward."** Correctly accepted Arxiv-only registry and deferred live Docker smoke. Incorrectly accepted open audit conditions to keep momentum into M3 — classic "the implementation works, paperwork can wait."

---

## 6. Open questions

- **When does state-worker import `bishop_shared.enums`?** Two copies will drift eventually unless something enforces single source. Is the right moment M4 (content-scraper needs it), M8 (multi-adapter), or never (test-only guard forever)?
- **Should empty manifest advance `scraper_state`?** Spec §10.3 success path implies yes; operationally it may hide broken queries. Does M3 pre-filter or monitoring need an alert on "zero rows N cycles in a row"?
- **How will nine `app` packages coexist in monolithic pytest?** M2 added another `services/scraper/app`; M7 made the namespace collision acute (~57 failures). Is subprocess-per-milestone the permanent answer, or does the repo need a packaging rename (`scraper_app`, etc.)?
- **ArXiv `submittedDate` vs `lastUpdatedDate`:** M2 filters on submission date. For rediscovery of revised papers, does the pipeline need update-date queries later, or does content-scraper handle that?
- **Registry bootstrap stub:** `registry.py` still has an `ImportError` fallback from when ArXiv adapter landed in a later subtask. Harmless dead code now — delete on next scraper touch, or keep for T2/T4 parallel DAG pattern in future milestones?

---

## 7. Single paragraph synthesis

M2 taught me that a pipeline stage is defined as much by what it refuses to do as by what it implements: discovery without content fetch, throttle without retry (and retry without throttle), dumb repost without client-side dedup. The technical shape — `bishop_shared` as a copied kernel, Atom export API for incremental manifests, failure envelope at the loop boundary — is sound and reusable. The personal failure was repeating a known closure mistake (code committed, plan artifacts lagging) and treating audit conditions as notes instead of work, which means I got a working scraper without fully owning the failure-mode surface (empty fetch advancing state, retry exhaustion at loop level). The compounding insight: **in a review-driven multi-agent build, your job at milestone end is not to confirm green tests but to cold-read the three files that implement the seam you least understand** — for M2, that was `loop.py` ordering state updates after batch POST, and the two-layer rate limit story in `arxiv.py` + `failure_envelope.py`.
