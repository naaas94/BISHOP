# BISHOP — System Specification and Design Document
### Master Seed File · Version 1.5.0 · June 2026

> **v1.1.0 changes:** Adversarial review incorporated. Pre-filter consolidated to Anthropic Batch API (Gemini removed). QUEUED states documented as pessimistic-lock guards. Vector-writer idempotency contract specified. Embedding model pinned (all-MiniLM-L6-v2). BM25 file-lock discipline added. Content truncation policy defined. BATCH_TIMED_OUT added. GitHub source_id fixed. DomainEnum.both removed. Tags enforcement mode specified. Acknowledged limitations added throughout. Section numbering corrected.

> **v1.2.0 changes:** Phase 2 adversarial review incorporated. ENRICHMENT_STAGE2_CLAIMED added as lock state for Stage 4b (structural fix). VECTOR_WRITE_QUEUED atomic-claim exemption explicitly documented. canonical_hash field added to NL profile YAML. scraper_state table added to schema. Alembic/aiosqlite sync-before-async startup pattern documented. oov_tags_log schema added. Embedding model quality gate tied to e2e validation step. REST API schema coverage gap acknowledged.

> **v1.3.0 changes:** Phase 3 review incorporated. Scraper loop pseudocode corrected to per-adapter `last_run` reads (Section 10.3). canonical_hash build checklist step added with explicit serialization ordering requirement — JSON with sorted keys, not raw YAML (Sections 11.3, 22). Lock-state recovery sweep added to state-worker for all QUEUED/CLAIMED orphaned states — crash-between-claim-and-submit scenario now has a defined handling path (Section 6.2, 22). Section 8 `## Storage Layer` parent heading restored. Challenge hooks BM25 index storage, locking, reload behavior, and subdirectory naming convention fully documented (Section 8.4). RRF channel count inconsistency resolved — metadata filter correctly classified as pre/post-filter (not RRF channel), 3-channel formula with conditional challenge_hooks activation specified, problem-shaped query detection heuristic defined, implicit rank ∞ behavior for absent channels documented (Sections 16.1, 16.2, 16.3). Footer version string corrected.

> **v1.4.0 changes:** Phase 2 cycle 1 review incorporated. Entry schema enrichment fields marked nullable — record is created at Stage 3 before enrichment exists; non-nullable fields produced a ValidationError on every SCRAPED entry creation (H1). Anthropic model string pinned to dated identifier `claude-haiku-4-5-20251001` throughout (H2). Multi-step result writes (COMPLETE + field writes + next QUEUED) explicitly required to execute within a single SQLite transaction — COMPLETE states are now safely transient, never orphanable (H3). DuckDB `read_only=True` specified for query-api (S1). Retry sweep added to state-worker background task — FAILED states with exhausted `next_retry_at` re-enqueue to work-ready predecessor; FAILED→work-ready mapping table added to Section 6.2 (S2). Batch-poller startup scan specified — re-discovers in-flight BatchRecords on restart (S3). BM25 persistence wrapper required to use atomic write semantics: temp-file write, fsync, rename (S4). Four enrichment write endpoint schemas specified (S5). GET /entries/poll response schema specified — returns full Entry model (S6). ESCALATION_FLAGGED manual retry mapping table added (S7). Section 8.1 and service map corrected — REST poll endpoints own atomic claim; direct SQLite reads limited to non-claiming queries (S8). Single-instance assumption documented for VECTOR_WRITE_QUEUED exemption (G1). Alert definition added to Section 14 (G2). Scraper schedule defaults added to Appendix B (G3). Sweep threshold note under API degradation added (G4). BM25 reload copy-on-write requirement added (G5). HuggingFace model card truncation variant added (G6). Query-api cold-start graceful initialization contract specified (G7). Batch API 10,000 item cap corrected (M1). list[str] SQLite storage representation specified as JSON-encoded string (M2). enrichment-batcher dual-task polling behavior specified (M3). Scraper state endpoint schemas added (M4).

> **v1.5.0 changes:** Phase 2 cycle 2 review incorporated. Formal Document Meta fields (status, review_cycle, phase2_verdict) and Phase 2 Feedback Log section added per spec-artifact §5.21 (previously absent). Embedding text input pinned — `title + "\n" + summary + "\n" + " ".join(challenge_hooks)` — schema-pinning decision documented alongside model pin in Sections 5.6 and 8.4 (N1). Retry sweep max_retries scope clarified: state-worker carries its own configurable `RETRY_MAX_ATTEMPTS` (default: 3), a separate budget from the adapter-layer per-source within-call retry limit; scope distinction made explicit in Section 6.2 (N2). Manual retry mapping table now consistently operates on _FAILED states only — state-worker normalizes batch result failure `state_at_failure` from SUBMITTED to corresponding FAILED before writing ErrorLog, documented in Section 9.1 result endpoints and Section 6.2 (N3). aiosqlite transaction syntax corrected: `await conn.execute("BEGIN")` / `await conn.commit()` / `await conn.rollback()` pattern replaces the ambiguous "async with conn" phrasing (M1). Pre-filter provenance null assertion requirement added to Section 5.3 Stage 3 Entry creation step (M2). GET /entries/poll for VECTOR_WRITE_QUEUED state now excludes content_raw — vector-writer does not need it; reduces payload at backfill scale (M3).

---

## 0. Document Meta

**Purpose.** This document is the canonical reference for the Bishop system. It serves simultaneously as:
- Architecture specification
- Design rationale log
- Implementation checklist
- Deferred and rejected item registry
- Context window distillation of all design decisions made prior to build start

**Status.** `phase1_approved` — Phase 1 re-greenlighted on v1.5.0 after absorbing Phase 2 cycle 2 feedback (N1–N3, M1–M3). Submitted to Phase 2 for Mode B cycle 3 re-review.

**Review cycle.** 3 (Phase 2 cycle 2 absorbed; awaiting cycle 3 APPROVED verdict to achieve dual-greenlight).

**phase2_verdict.** CONDITIONAL (cycle 2). Cycle 3 re-review scoped to N1, N2, N3 resolution verification.

**Architectural decisions.** Locked unless explicitly marked as deferred or pending. Implementation-level decisions (exact retry intervals, BM25 field weights) are left for the implementation phase and should be documented in code comments or a changelog when resolved.

**System Name.** Bishop.

**Author.** Alejandro Garay Frontini.

---

## 1. System Overview

Bishop is a two-layer, local-first knowledge intelligence system. It scrapes, filters, enriches, stores, and serves AI/ML/engineering content from multiple sources for two primary use cases:

**Layer 1 — Scrape and Surface.** A scheduled, asynchronous pipeline that discovers content from configured sources, filters it for relevance against a versioned natural-language profile, enriches relevant entries with LLM-generated metadata, and surfaces batch summaries for review.

**Layer 2 — Persistent Local Knowledge Base.** A hybrid semantic and relational store of enriched entries, queryable at any point during professional work — when tightening a spec, facing an implementation challenge, or doing research. Query patterns range from semantic problem-shaped lookup to structured metadata filtering.

**Scope at launch.** Professional domain only: AI/ML/engineering research, architectural patterns, production systems, LLM inference, RAG, agentic systems, document intelligence. The personal domain (philosophy, psychology, cinema) is architecturally provisioned but not implemented.

**Operational model.** Nothing is urgent. The entire pipeline is async and stateful. Entries flow through stages at the pace of batch workers and external API cadences. No real-time requirements except the query layer, which is interactive.

**What Bishop is not.** It is not a real-time news aggregator, a recommendation engine, a social feed, or a replacement for structured search tools. It is a personal, curated, professionally-oriented knowledge base that compounds over time.

---

## 2. Design Principles

These principles governed every architectural decision and should govern implementation decisions not yet specified.

1. **Local-first.** All data persists on the host machine. No cloud storage dependency. External APIs are used for enrichment only, not for storage or retrieval.

2. **Async and non-urgent.** The pipeline operates on a best-effort, eventually-consistent model. No entry needs to be indexed in real time. Workers pick up queued work at their cadence. API calls batch for cost efficiency.

3. **Single-writer discipline.** The SQLite state store has one writer: the `state-worker` service. All other services POST state transitions to `state-worker` via its internal REST API. This eliminates concurrent-writer contention on SQLite.

4. **Idempotency everywhere.** Every pipeline operation is safe to re-run. State transitions are idempotent by source_id. Batch submissions are tracked. Dedup runs on every scrape cycle.

5. **Fail visibly, not silently.** Failures are classified, logged, and surfaced. Retriable failures retry with backoff. Non-retriable recoverable failures escalate to a visible queue. Fatal failures terminate cleanly without retry.

6. **Extensibility without surgery.** Adding a new source, a new domain, or a new enrichment field should be a contained change. The source adapter registry, the domain routing config, and the NL profile system are all designed for this.

7. **Enrich once, query many times.** LLM enrichment happens at ingest time and is persisted. Query time is cheap — no LLM calls on the query path at MVP.

8. **Profile-driven relevance, not hard-coded.** What is relevant is defined by a versioned, human-readable YAML profile. The profile can be updated without touching code. Enrichment decisions are tagged with the profile version that produced them.

9. **Cost awareness without cost obsession.** At projected volume (tens to hundreds of entries per day), costs are in the range of cents per day. Engineering decisions are made on quality and correctness grounds, not cost grounds. Cost efficiency (batch API, prompt caching) is applied where it falls naturally out of the architecture.

10. **Defer with documentation.** Features not needed for MVP are explicitly documented in the deferred list with rationale. They are not forgotten; they are scheduled.

---

## 3. Source Stack

### 3.1 Professional Domain Sources (Active at Launch)

| Source | Signal Type | API / Access | Notes |
|---|---|---|---|
| ArXiv | Primary research papers | REST + RSS per category | Ground truth for ML preprints. HF papers feed is downstream of ArXiv — use ArXiv directly. |
| Semantic Scholar | Citation graphs, paper enrichment, author networks | REST (`api.semanticscholar.org/graph/v1/`) | Free tier: 100 req/s with API key. Best for citation traversal (deferred). |
| Papers With Code | SOTA benchmarks, code-to-paper links | REST (`paperswithcode.com/api/v1/`) | Acquired by HuggingFace 2021. API runs independently. Critical for "what's the SOTA on X" queries. |
| HuggingFace Hub | Models, datasets, spaces, model cards | REST (`huggingface.co/api/models`, `/datasets`, `/spaces`) | HF wins unambiguously for model/dataset/space metadata. Secondary for papers. |
| GitHub | Implementation signal, trending repos | REST + Search API | 5000 req/hr authenticated. Strong for finding code drops before they appear in papers. |
| OpenReview | ICLR, NeurIPS, ICML submissions, reviews, rebuttals | REST (`openreview.net/api`) | Unique value: peer review text, author responses, decisions. Not covered by other sources. |
| LessWrong / Alignment Forum | AI alignment, safety, long-form ideas | GraphQL | Verify API endpoint before implementing adapter. Lower priority; add after core sources validated. |

### 3.2 Personal Domain Sources (Deferred)

RSS feeds, Substack newsletters, and occasional PDFs for philosophy, psychology, and cinema. Architecture supports it; implementation deferred. Separate NL profile and workflow config required.

### 3.3 Why Not HuggingFace as Primary Paper Source

HuggingFace's daily papers feed is a community-curated upvote layer on top of ArXiv. It provides useful prioritization signal but is lossy on coverage. For a comprehensive KB, ArXiv is the ground truth. HF is one source node in a multi-source graph, not the spine.

---

## 4. System Architecture — High-Level

```
┌──────────────────────────────────────────────────────────────────┐
│  EXTERNAL SOURCES                                                 │
│  ArXiv · Semantic Scholar · Papers With Code · HuggingFace       │
│  GitHub · OpenReview · LessWrong                                  │
└──────────────────────────┬───────────────────────────────────────┘
                           │ fetch_manifest (lightweight)
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│  SCRAPER SERVICE                                                  │
│  Per-source adapters · Rate limiting · Failure envelope          │
│  Writes discovered entries → state-worker                        │
└──────────────────────────┬───────────────────────────────────────┘
                           │ POST /manifest/batch
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│  STATE-WORKER SERVICE (single SQLite writer)                     │
│  Manifest table · Entry table · Error log · Batch records        │
│  State transition logic · Internal REST API                      │
└─────┬──────────────┬──────────────────────────────┬─────────────┘
      │              │                              │
      ▼              ▼                              ▼
┌──────────┐  ┌─────────────────┐        ┌─────────────────────┐
│PRE-FILTER│  │ CONTENT-SCRAPER │        │  ENRICHMENT-BATCHER │
│ WORKER   │  │ SERVICE         │        │  + BATCH-POLLER     │
│          │  │                 │        │  + VECTOR-WRITER    │
│Anthropic │  │ Full content    │        │                     │
│Batch API │  │ fetch per entry │        │  Anthropic Batch    │
│ (Haiku)  │  │                 │        │  API (2 call stages)│
└──────────┘  └─────────────────┘        └─────────────────────┘
                                                    │
                                                    ▼
┌──────────────────────────────────────────────────────────────────┐
│  STORAGE LAYER (host-mounted volumes)                            │
│  SQLite (state + manifest + entry metadata)                      │
│  LanceDB (vectors + hybrid retrieval)                            │
│  DuckDB (analytics + metadata queries via Lance integration)     │
└──────────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│  QUERY-API SERVICE (FastAPI)                                     │
│  Hybrid BM25 + dense semantic + metadata filter + RRF fusion    │
│  Serves UI service                                               │
└──────────────────────────┬───────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│  UI SERVICE (HTMX · localhost)                                   │
│  Batch summary view · DB explorer · Entry detail · Escalations  │
└──────────────────────────────────────────────────────────────────┘
```

---

## 5. Pipeline Architecture — Detailed Flow

### 5.1 Stage 1: Discovery (Scraper → State-Worker)

1. Scraper service runs on schedule (configurable per source via APScheduler or cron).
2. Each registered adapter calls `fetch_manifest(since=last_run_timestamp)`, returning a list of lightweight `ManifestEntry` objects (title, URL, source_id, abstract if available, published_at).
3. For backfill runs, `since` is replaced by `now - backfill_window_days` (per-source config).
4. Scraper POSTs the batch to `state-worker /manifest/batch`.
5. State-worker runs dedup: any entry whose `source_id` already exists in the manifest table is silently skipped.
6. New entries are written with `processing_state = DISCOVERED`.

### 5.2 Stage 2: Relevance Pre-filter (Pre-filter Worker)

1. Pre-filter worker polls state-worker via `GET /manifest/poll?state=DISCOVERED`.
2. **Atomic claim:** state-worker transitions polled entries to `RELEVANCE_QUEUED` within the same SQLite transaction before returning them. A second concurrent worker polling the same endpoint will find no `DISCOVERED` entries — they are already claimed. This is the double-processing guard; no additional locking mechanism is needed.
3. Assembles a batch of up to 50 entries (default; configurable).
4. Loads the active NL profile for the entry's domain.
5. Renders the profile into a prompt string. Profile is rendered once per batch, SHA-256 hash computed and stored on the BatchRecord as `profile_render_hash`. The same rendered string is reused for all calls in the batch. If the hash does not match the profile file's expected hash, the batch is aborted, logged, and alerted.
6. Submits batch to Anthropic Batch API (`claude-haiku-4-5-20251001`). System prompt = rendered NL profile (eligible for Anthropic prompt caching once profile reaches the prompt caching minimum token threshold — growing the profile toward that threshold is the documented path to additional cost savings on top of the 50% batch discount). User prompt per entry = title + abstract.
7. Batch-poller polls Anthropic for batch completion. On completion: results parsed, decisions POSTed to `state-worker /manifest/pre-filter-results`.
8. State-worker transitions: decision=1 → `RELEVANCE_PASSED`; decision=0 → `RELEVANCE_REJECTED` (terminal clean).
9. `pre_filter_rationale` and `profile_version` written to manifest entry.
10. BatchRecord created with `batch_type = pre_filter`, `profile_render_hash` field populated.

### 5.3 Stage 3: Full Content Scrape (Content-Scraper)

1. Content-scraper polls state-worker via `GET /manifest/poll?state=RELEVANCE_PASSED`.
2. **Atomic claim:** state-worker transitions polled entries to `SCRAPE_QUEUED` within the same SQLite transaction before returning them.
3. For each entry, calls the source adapter's `fetch_content(entry)` method.
4. Returns full content string (paper abstract + body text, README, article text, etc.).
5. POSTs content to `state-worker /entries/content`.
6. State-worker creates a new `Entry` record (copied from manifest, plus `content_raw`), transitions to `SCRAPED`. **Pre-filter provenance null assertion (M2):** before copying `profile_version`, `pre_filter_batch_id`, and `pre_filter_rationale` from ManifestEntry into the new Entry record, state-worker must assert these three fields are non-None. They are typed `str | None` on ManifestEntry (they start null and are populated by Stage 2). An entry reaching Stage 3 with any of these still null indicates a state machine violation (Entry creation should only occur from RELEVANCE_PASSED entries, which by definition have completed Stage 2). The assertion is a runtime guard against this invariant being silently violated.

### 5.4 Stage 4a: Enrichment Call 1 — Factual Extraction (Enrichment-Batcher)

1. Enrichment-batcher polls state-worker via `GET /entries/poll?state=SCRAPED`.
2. **Atomic claim:** state-worker transitions polled entries to `ENRICHMENT_STAGE1_QUEUED` within the same SQLite transaction before returning them.
3. Assembles a batch and submits to Anthropic Batch API.
4. Call 1 prompt: factual extraction, no profile context needed.
   - Extracts: `summary`, `concepts`, `tags`, `entry_type`, `challenge_hooks`.
5. State-worker transitions entries to `ENRICHMENT_STAGE1_SUBMITTED`. BatchRecord created with `batch_type = enrichment_stage1`.
6. Batch-poller polls Anthropic for batch completion. **Maximum wait: 48 hours.** If the batch has not completed within 48 hours, batch-poller marks the BatchRecord status as `batch_timed_out` and transitions all entries in the batch to `ENRICHMENT_STAGE1_FAILED` for retry.
7. On completion: state-worker transitions to `ENRICHMENT_STAGE1_COMPLETE`, writes Call 1 fields to entry record, transitions to `ENRICHMENT_STAGE2_QUEUED`.

### 5.5 Stage 4b: Enrichment Call 2 — Evaluative / Profile-Aware (Enrichment-Batcher)

1. Enrichment-batcher polls state-worker via `GET /entries/poll?state=ENRICHMENT_STAGE2_QUEUED`.
2. **Atomic claim:** state-worker transitions polled entries from `ENRICHMENT_STAGE2_QUEUED` to `ENRICHMENT_STAGE2_CLAIMED` within the same SQLite transaction before returning them. `ENRICHMENT_STAGE2_CLAIMED` is the lock state for Stage 4b — a second concurrent batcher instance polling for `ENRICHMENT_STAGE2_QUEUED` entries will find none, because they are already in `ENRICHMENT_STAGE2_CLAIMED`. This is structurally identical to the pattern in all other pipeline stages.
3. Assembles a batch and submits to Anthropic Batch API.
4. Batcher POSTs submission confirmation to state-worker; state-worker transitions entries to `ENRICHMENT_STAGE2_SUBMITTED`. BatchRecord created with `batch_type = enrichment_stage2`.
5. Call 2 prompt: NL profile context injected as system prompt (Anthropic prompt caching via `cache_control` blocks, effective once the profile reaches the prompt caching minimum token threshold).
   - Generates: `relevance_score`, `relevance_reason`, `value_rationale`.
6. Batch-poller polls Anthropic for batch completion. **Maximum wait: 48 hours.** On timeout: BatchRecord status → `batch_timed_out`, entries → `ENRICHMENT_STAGE2_FAILED` for retry.
7. On completion: state-worker transitions to `ENRICHMENT_STAGE2_COMPLETE`, writes Call 2 fields to entry record, transitions to `VECTOR_WRITE_QUEUED`.

### 5.6 Stage 5: Vector Indexing (Vector-Writer)

1. Vector-writer polls state-worker for entries in `VECTOR_WRITE_QUEUED` state.
   **Note: `VECTOR_WRITE_QUEUED` does NOT use the atomic claim pattern.** No intermediate lock state is needed here. Correctness is guaranteed instead by: (a) `INDEXED` as a terminal state that state-worker will never transition away from, providing the primary double-processing guard; and (b) check-before-write idempotency at each store, providing the crash-recovery guard. See Section 6.2 for the explicit exemption note.
2. **Generates embedding** for each entry using `sentence-transformers/all-MiniLM-L6-v2` (384 dimensions, in-process, no additional service dependency). See Section 8.4 for model pin rationale.
   **Pinned embedding text (N1):** the text input to the encoder is the concatenation of `title`, `summary`, and `challenge_hooks`, joined by newlines:
   ```python
   embed_text = f"{entry.title}\n{entry.summary}\n{' '.join(entry.challenge_hooks)}"
   ```
   `summary` contributes the dense factual distillation; `challenge_hooks` contributes the problem-shaped semantic framings that are the primary driver of Layer 2 retrieval quality (Section 13.3). `title` provides the concise identifier anchor. This concatenation is the pinned embedding text — changing it requires a full LanceDB index rebuild from `content_raw`, identical to the consequence of changing the embedding model. `content_raw` is not included in the embedding text (it is the untruncated source corpus, too noisy and large; the enrichment prompt truncation policy in Section 13.1 applies only to enrichment prompt construction, not to embedding).
3. **Idempotency contract (check-before-write):**
   - LanceDB: query for existing `source_id` before writing. If found, skip the write. This handles crash-between-writes retry scenarios without producing duplicate vectors, which would degrade retrieval quality.
   - BM25 index: check document corpus for existing `source_id` before adding. If found, skip. `rank-bm25`-style libraries are additive — duplicate documents corrupt relevance scoring.
   - DuckDB: use `INSERT OR REPLACE` semantics. Upsert is safe and idempotent.
4. Writes enriched entry + embedding to LanceDB (after check).
5. Updates BM25 index for the entry's domain (persisted, incremental update, after check). Acquires file lock before write (see Section 8.4).
6. Mirrors metadata fields to DuckDB (upsert).
7. Releases file lock.
8. POSTs completion to `state-worker /entries/indexed`.
9. State-worker transitions to `INDEXED` (terminal success state). INDEXED is a terminal state — state-worker will not re-transition an INDEXED entry to VECTOR_WRITE_QUEUED, providing a primary guard against duplicate indexing. The check-before-write in steps 3-6 is the secondary guard covering crash-recovery scenarios.

### 5.7 Batch Record Lifecycle

A `BatchRecord` is created at each batch submission (Stage 2, Stage 4a, Stage 4b). It carries:
- batch_id (UUID)
- batch_type
- domain
- profile_version
- profile_render_hash (SHA-256 of the rendered prompt string used for this batch)
- entry_count, passed_count, failed_count
- status: `pending → submitted → processing → complete | failed | batch_timed_out`
- top_entries (entry IDs sorted by relevance_score, populated on completion for enrichment_stage2 batches)
- completed_at

**Partial batch behavior.** A batch that completes with some entry-level failures records `complete` status at the batch level. The `failed_count` field carries the failure signal. Individual entry `processing_state` is the source of truth for failure detail. There is no `partial` status at the batch level — it adds enum complexity without behavioral benefit.

**Batch timeout.** A batch that has not transitioned to `complete` or `failed` within 48 hours is marked `batch_timed_out` by the batch-poller. All entries in that batch are transitioned to their stage's `_FAILED` state for retry.

Batch summaries are surfaced in the UI indexed by batch_id. The batch_type distinguishes pre-filter batches from enrichment batches in the UI.

---

## 6. State Machine

### 6.1 ProcessingState Enum (Complete)

```
Happy path:
  DISCOVERED
  RELEVANCE_QUEUED
  RELEVANCE_PASSED
  RELEVANCE_REJECTED              ← terminal, clean
  SCRAPE_QUEUED
  SCRAPED
  ENRICHMENT_STAGE1_QUEUED
  ENRICHMENT_STAGE1_SUBMITTED
  ENRICHMENT_STAGE1_COMPLETE
  ENRICHMENT_STAGE2_QUEUED        ← work-ready state (set by Stage 4a completion)
  ENRICHMENT_STAGE2_CLAIMED       ← atomic lock state (set by Stage 4b poll claim)
  ENRICHMENT_STAGE2_SUBMITTED
  ENRICHMENT_STAGE2_COMPLETE
  VECTOR_WRITE_QUEUED
  INDEXED                         ← terminal, success

Failure path:
  SCRAPE_FAILED                   ← retry eligible
  ENRICHMENT_STAGE1_FAILED        ← retry eligible
  ENRICHMENT_STAGE2_FAILED        ← retry eligible
  VECTOR_WRITE_FAILED             ← retry eligible
  ESCALATION_FLAGGED              ← visible, needs review, non-terminal
  PERMANENTLY_FAILED              ← terminal, dead-letter
```

### 6.2 Transition Rules

- Every transition is owned by `state-worker`. No service writes state directly.
- Transitions are idempotent: applying the same transition twice does not corrupt state.
- Terminal states (`RELEVANCE_REJECTED`, `INDEXED`, `PERMANENTLY_FAILED`) cannot be overwritten except by an explicit admin override.
- `ESCALATION_FLAGGED` entries are visible in the UI. Manual retry or permanent-fail actions available.
- **Atomic claim semantics for poll endpoints.** `GET /manifest/poll?state=X` and `GET /entries/poll?state=X` are not side-effect-free reads. They operate as atomic claim-and-transition: the state-worker reads entries in state X and transitions them to the corresponding lock state within the same SQLite transaction before returning the list. This prevents double-processing by concurrent worker instances without requiring a separate task queue or locking service. Mapping of source states to lock states: `DISCOVERED → RELEVANCE_QUEUED`, `RELEVANCE_PASSED → SCRAPE_QUEUED`, `SCRAPED → ENRICHMENT_STAGE1_QUEUED`, `ENRICHMENT_STAGE2_QUEUED → ENRICHMENT_STAGE2_CLAIMED`. The `_QUEUED` and `_CLAIMED` states in the enum are the mechanism that enforces this guarantee — they are not vestigial.
- **`VECTOR_WRITE_QUEUED` is explicitly exempt from the atomic claim pattern.** The vector-writer poll does not transition entries to a lock state before returning them. Correctness at this stage is guaranteed by two other mechanisms: `INDEXED` as a terminal state (state-worker never re-transitions an INDEXED entry) and check-before-write idempotency across all three write targets (LanceDB, BM25, DuckDB). These two guards are sufficient and eliminate the need for a lock state here.
- **Lock-state recovery sweep.** State-worker runs a background sweep (configurable interval, default: 5 minutes) that detects entries stuck in any lock/queued state older than a configurable threshold (default: 15 minutes). On detection, the sweep resets them to the preceding work-ready state: `RELEVANCE_QUEUED → DISCOVERED`, `SCRAPE_QUEUED → RELEVANCE_PASSED`, `ENRICHMENT_STAGE1_QUEUED → SCRAPED`, `ENRICHMENT_STAGE2_CLAIMED → ENRICHMENT_STAGE2_QUEUED`. This covers the crash-between-claim-and-submit scenario for all stages — a worker that claimed entries and died before posting the submission confirmation leaves entries stuck in the lock state indefinitely without this sweep. The 15-minute threshold prevents legitimate in-progress batches from being prematurely reset; Anthropic Batch API submissions are not expected to take longer than a few minutes to transition from claim to `_SUBMITTED`. `VECTOR_WRITE_QUEUED` is not included in the sweep scope — the check-before-write and terminal-state guards are sufficient there and the sweep would be redundant. The sweep is implemented as a background asyncio task in state-worker, not a separate service.
  **Sweep threshold caveat (G4).** The 15-minute threshold assumes normal Anthropic Batch API submission latency (< 2 minutes). Under extended API degradation, an entry could remain in a CLAIMED/QUEUED lock state while the submission is still in-flight, and the sweep would reset it before the submission completes — causing a second batch submission for the same entry. This is an accepted risk: duplicate batches produce redundant API charges (cents range) and the second batch's results are applied as idempotent no-ops by state-worker. Duplicate submissions are trackable via BatchRecord count per source_id. A configurable threshold allows operational tuning if API degradation becomes chronic.
- **Retry sweep.** In the same background asyncio task as the lock-state sweep, state-worker scans for `_FAILED` entries where `next_retry_at ≤ now` and `retry_count < RETRY_MAX_ATTEMPTS`, and re-enqueues them by transitioning to the preceding work-ready state. **`RETRY_MAX_ATTEMPTS` is state-worker's own configurable constant (default: 3).** This is a distinct retry budget from the adapter layer's per-source `max_retries` in Section 15.1. The adapter `max_retries` governs within-call retry loops inside the failure envelope for a single `fetch_manifest` or `fetch_content` invocation (transient HTTP failures). `RETRY_MAX_ATTEMPTS` governs how many times state-worker will automatically re-enqueue an entry across separate pipeline runs. These are different failure layers and are intentionally decoupled — configuring one does not affect the other. Retry target mapping (canonical for both automatic re-enqueue and the manual retry action in Section 14.2):
  ```
  SCRAPE_FAILED              → RELEVANCE_PASSED
  ENRICHMENT_STAGE1_FAILED   → SCRAPED
  ENRICHMENT_STAGE2_FAILED   → ENRICHMENT_STAGE2_QUEUED
  VECTOR_WRITE_FAILED        → VECTOR_WRITE_QUEUED
  ```
  `ESCALATION_FLAGGED` entries are not automatically re-enqueued by the retry sweep — they require manual action via the escalation panel. For manual retry, state-worker derives the retry target from the entry's most recent `state_at_failure` field in `error_log`, applying the same mapping table above.
- **Multi-step result write atomicity (H3).** State-worker multi-step result write sequences — (1) transition to COMPLETE, (2) write enrichment field values to the entry record, (3) transition to the next work-ready state — must execute within a single SQLite transaction. **Correct aiosqlite pattern:**
  ```python
  await conn.execute("BEGIN")
  try:
      await conn.execute("UPDATE entries SET processing_state = ? WHERE source_id = ?",
                         ("ENRICHMENT_STAGE1_COMPLETE", source_id))
      await conn.execute("UPDATE entries SET summary = ?, concepts = ?, ... WHERE source_id = ?",
                         (summary, concepts_json, ..., source_id))
      await conn.execute("UPDATE entries SET processing_state = ? WHERE source_id = ?",
                         ("ENRICHMENT_STAGE2_QUEUED", source_id))
      await conn.commit()
  except Exception:
      await conn.rollback()
      raise
  ```
  `async with conn:` is a connection context manager, not a transaction. It does not provide `BEGIN/COMMIT` semantics. Use explicit `await conn.execute("BEGIN")` and `await conn.commit()` / `await conn.rollback()`. The COMPLETE states (`ENRICHMENT_STAGE1_COMPLETE`, `ENRICHMENT_STAGE2_COMPLETE`) are designed as transient audit waypoints, not durable intermediate states. Under correct transaction discipline, an entry should only ever be observed in a COMPLETE state for the duration of the transaction that wrote it. An entry observed in a COMPLETE state outside of an active transaction indicates a partial commit — which should not occur under ACID-compliant SQLite. If one is observed, treat it as requiring manual intervention; the lock-state recovery sweep intentionally does not cover COMPLETE states (they are not lock states and should not appear in normal operation).
- **Single-instance deployment assumption for `VECTOR_WRITE_QUEUED` exemption (G1).** The check-before-write idempotency argument for this exemption assumes single-instance vector-writer deployment. A restart overlap (dying instance + starting instance both polling simultaneously) produces a brief window where both instances read the same VECTOR_WRITE_QUEUED entries, both find no existing source_id in LanceDB, and both attempt a write — producing a duplicate LanceDB vector before either posts `/entries/indexed`. Mitigation: set `stop_grace_period` in Docker Compose for the vector-writer service long enough to allow in-progress writes to complete before the new instance starts. Duplicate vectors produced during an overlap do not corrupt the state machine but degrade retrieval scoring; the index rebuild path (Section 8.4) is the recovery procedure.

### 6.3 Failure Classification and State Routing

```
Retriable HTTP codes:     429, 500, 502, 503, 504
Retriable exceptions:     TimeoutError, ConnectionError, httpx.TimeoutException,
                          httpx.NetworkError, httpx.RemoteProtocolError

Non-retriable recoverable (→ ESCALATION_FLAGGED immediately):
                          401, 403  (auth failure)
                          404       (resource moved or deleted)
                          422       (API schema change, response parsing failure)

Fatal (→ PERMANENTLY_FAILED immediately):
                          400       (bad request — implementation bug)
                          410       (permanently gone)

Retry exhaustion:
  Retriable + retry_count >= max_retries → ESCALATION_FLAGGED
```

### 6.4 Retry Behavior

- On retriable failure: increment `retry_count`, compute `next_retry_at` using backoff formula (exponential or linear, per-source config), stay in failed state, re-enqueue for retry at `next_retry_at`.
- Backoff formula (exponential): `base_delay * (2 ^ retry_count) + jitter`.
- Jitter: uniform random offset ±20% to prevent thundering herd across source adapters.
- `max_retries` is source-specific (see Section 15).

---

## 7. Schema Definitions

### 7.1 ManifestEntry (manifest table)

All discovered entries, including those that fail the pre-filter. The dedup layer.

```python
class ManifestEntry:
    # Identity
    source_id: str                  # canonical: "arxiv:2301.xxxxx", "github:owner/repo"
    source: SourceEnum
    url: str
    title: str
    abstract: str | None            # from lightweight scrape if available from source
    published_at: datetime | None
    discovered_at: datetime
    domain: DomainEnum

    # Pre-filter provenance
    profile_version: str | None     # NL profile semver at time of pre-filter
    pre_filter_batch_id: str | None # UUID of the pre-filter batch this was part of
    relevance_decision: int | None  # 0 or 1 (populated after pre-filter)
    pre_filter_rationale: str | None # one sentence from pre-filter LLM call

    # State machine
    processing_state: ProcessingState
    retry_count: int                 # default 0
    next_retry_at: datetime | None
```

### 7.2 Entry (entries table)

Enriched entries that cleared the pre-filter. The knowledge base. Only entries with `relevance_decision = 1` reach this table.

**Progressive population model.** The Entry record is created at Stage 3 (SCRAPED) with identity and `content_raw` only. Enrichment fields are populated across Stages 4a and 4b. All enrichment fields are therefore `| None` in the schema — non-nullable at database level would produce a `ValidationError` on Stage 3 record creation. Nullability is structurally not observable at query time: the query layer only serves `INDEXED` entries, which by definition have completed both enrichment stages. Any entry appearing in query results with a null enrichment field indicates a pipeline bug.

**SQLite storage for `list[str]` fields (M2).** SQLite has no native array type. `concepts`, `tags`, `challenge_hooks`, `references`, `cited_by` are stored as JSON-encoded strings (`json.dumps(value)` on write, `json.loads(value)` on read). State-worker owns all reads and writes against these fields. The Entry Pydantic model handles serialization/deserialization at the state-worker boundary.

```python
class Entry:
    # Identity
    id: str                              # UUID, primary key
    source_id: str                       # FK to ManifestEntry
    source: SourceEnum
    url: str
    title: str
    content_raw: str                     # full content fetched in Stage 3; non-nullable
    published_at: datetime | None
    ingested_at: datetime
    domain: DomainEnum

    # Pre-filter provenance (carried from manifest)
    profile_version: str                 # NL profile version used for pre-filter
    pre_filter_batch_id: str             # UUID of the pre-filter batch
    pre_filter_rationale: str            # carried from manifest, one sentence

    # Enrichment — Call 1: Factual Extraction (null until Stage 4a completes)
    summary: str | None                  # 200-300 char dense summary
    concepts: list[str] | None           # 5-8 key technical concepts; stored as JSON string in SQLite
    tags: list[str] | None               # controlled taxonomy (see Section 20); stored as JSON string in SQLite
    entry_type: EntryTypeEnum | None
    challenge_hooks: list[str] | None    # 2-4 problem framings; stored as JSON string in SQLite
    enrichment_stage1_batch_id: str | None  # UUID of the enrichment stage 1 batch

    # Enrichment — Call 2: Evaluative, Profile-Aware (null until Stage 4b completes)
    relevance_score: float | None        # 0.0-1.0
    relevance_reason: str | None         # one sentence, why this is relevant to the profile
    value_rationale: str | None          # why worth reading/keeping, in user's professional context
    enrichment_stage2_batch_id: str | None  # UUID of the enrichment stage 2 batch

    # Graph-ready fields (nullable, populated when graph layer is built)
    references: list[str] | None         # source_ids of cited works; stored as JSON string in SQLite
    cited_by: list[str] | None           # populated retroactively; stored as JSON string in SQLite

    # UI / consumption state
    reading_status: ReadingStatusEnum    # unread | reading | read | archived
    flagged_for_review: bool             # set by ESCALATION_FLAGGED path or manual flag

    # State machine
    processing_state: ProcessingState
```

### 7.3 BatchRecord (batches table)

One record per batch submission (pre-filter, enrichment_stage1, enrichment_stage2).

```python
class BatchRecord:
    batch_id: str                   # UUID, canonical reference
    batch_type: BatchTypeEnum       # pre_filter | enrichment_stage1 | enrichment_stage2
    domain: DomainEnum
    profile_version: str            # NL profile version used for this batch
    profile_render_hash: str        # SHA-256 of the rendered prompt string for this batch
                                    # stored for retroactive audit: which exact render produced which decisions
    status: BatchStatusEnum         # pending | submitted | processing | complete | failed | batch_timed_out
    created_at: datetime
    submitted_at: datetime | None
    completed_at: datetime | None
    entry_count: int                # total entries in batch
    passed_count: int               # entries that passed (for pre_filter) or succeeded (for enrichment)
    failed_count: int
    top_entries: list[str]          # entry IDs sorted by relevance_score desc, top 20
                                    # populated only for enrichment_stage2 complete batches
    external_batch_id: str | None   # Anthropic batch ID for polling
```

### 7.4 ErrorLog (error_log table)

Separate table, queryable. Not a JSON blob on the entry.

```python
class ErrorLog:
    id: str                         # UUID
    source_id: str                  # FK to ManifestEntry (or entry ID for post-manifest failures)
    attempt_number: int
    state_at_failure: ProcessingState
    error_class: str                # exception class name
    http_status: int | None
    message: str                    # error message or response body snippet
    is_retriable: bool
    timestamp: datetime
    next_retry_at: datetime | None
```

### 7.5 OovTagsLog (oov_tags_log table)

Tags stripped by the Call 1 parser for being outside the controlled taxonomy. Governance mechanism for taxonomy evolution.

```python
class OovTagsLog:
    id: str                         # UUID
    source_id: str                  # FK to entries table
    tag_value: str                  # the out-of-vocabulary tag string
    entry_type: EntryTypeEnum       # type of entry that produced it
    enrichment_batch_id: str        # FK to batches table (enrichment_stage1 batch)
    timestamp: datetime
    review_status: OovReviewStatusEnum  # pending | added_to_taxonomy | rejected
```

### 7.6 ScraperState (scraper_state table)

Persists the last successful run timestamp per source. Prevents scraper service restarts from triggering full backfill re-scrapes — without this, a restart resets `last_run` to `None`, causing all source adapters to re-fetch their full backfill window and flood the manifest with already-processed entries (all safely deduplicated but generating unnecessary load).

```python
class ScraperState:
    source: SourceEnum              # primary key
    last_successful_run_at: datetime | None  # None on first run → uses backfill_window_days
    updated_at: datetime
```

State-worker owns this table (single-writer discipline). Scraper reads `last_run` at the start of each cycle via `GET /scraper-state/{source}`. After a successful manifest batch is written, scraper POSTs a `last_run` update to `POST /scraper-state/{source}`.

## 8. Storage Layer

### 8.1 SQLite

**Role.** State machine store. Owns `manifest`, `entries`, `batches`, `error_log`, `oov_tags_log`, `scraper_state` tables. Single writer: `state-worker`. All other services are read-only against SQLite or route writes through `state-worker`'s REST API.

**Configuration.** WAL mode (`PRAGMA journal_mode=WAL`) on initialization. Enables concurrent reads, serialized single writer, proper crash recovery with minimal data loss.

**Access pattern.** Writes: exclusively via `state-worker`. Reads: two distinct categories.
  - **Claiming reads (pipeline stages 1–5):** `pre-filter-worker`, `content-scraper`, `enrichment-batcher`, and `vector-writer` claim work by calling the REST poll endpoints on `state-worker` (`GET /manifest/poll`, `GET /entries/poll`). These are not direct SQLite reads — they are REST calls that trigger an atomic claim-and-transition inside state-worker's single-writer SQLite transaction. Any service issuing a direct SQLite read for the purpose of claiming entries would bypass the atomic claim mechanism and break the double-processing prevention guarantee.
  - **Non-claiming reads:** `batch-poller` reads `BatchRecord` status directly from SQLite to track Anthropic batch completion. `query-api` reads entry metadata directly from SQLite (via DuckDB) for metadata-filtered queries. These reads do not perform state transitions and are safe as direct SQLite reads.

**Known limitation — schema coupling.** Direct SQLite reads from multiple services means every reader is coupled to the SQLite schema. Adding a column to the manifest or entries table requires changes across all reader services, not just state-worker. This is an accepted tradeoff at this architecture tier. Decoupling all reads through state-worker would require an event-sourcing or message-passing model with significantly higher complexity. Schema changes should be approached as a cross-service concern.

**Schema migration.** Managed via Alembic. All schema changes are expressed as migration scripts, not applied manually. LanceDB schema evolution: nullable field additions are in-place; vector dimension changes require a full index rebuild from `content_raw` stored in SQLite. `content_raw` is persisted specifically to enable this rebuild path.

**Alembic + aiosqlite compatibility.** Alembic's migration engine uses synchronous SQLAlchemy. The state-worker runtime uses aiosqlite (async). These are compatible but require a deliberate startup sequence: migrations are run synchronously as a startup hook — a dedicated sync SQLAlchemy engine opens the SQLite file, runs `alembic upgrade head`, and closes before the asyncio event loop starts processing requests. Do not attempt to run Alembic migrations inside an asyncio context without a sync wrapper — this will produce a runtime error. The cold-start sequence in Section 21 reflects this ordering.

### 8.2 LanceDB

**Role.** Vector store and primary hybrid retrieval store. Stores enriched entries with their embeddings. Supports vector search, metadata filtering, and full-text search in a single store.

**Access pattern.** Write: `vector-writer` service exclusively. Read: `query-api` for semantic search and hybrid retrieval.

**Format.** Arrow-native, Lance format on disk. Single file directory on host volume.

**DuckDB integration.** LanceDB tables are queryable directly via DuckDB using the Lance file format. DuckDB is the unified query interface for metadata analytics and structured queries that don't need vector search. This collapses the LanceDB+DuckDB query path: DuckDB handles structured; LanceDB Python API handles vector; query-api assembles results from both.

**Important nuance.** Vector search (cosine similarity ranking) still goes through LanceDB's native Python API — DuckDB SQL cannot execute ANN queries. "Unified interface" means DuckDB handles structured/analytics, LanceDB handles vector, and the query-api fuses the results. These are two calls, not one.

### 8.3 DuckDB

**Role.** Analytical queries, metadata filtering, structured aggregations (recency windows, tag distributions, source breakdowns, relevance histograms). Also used for the batch summary analytics.

**Access pattern.** Two processes access the DuckDB file: `vector-writer` (write — `INSERT OR REPLACE` during indexing) and `query-api` (read — metadata filtering queries). DuckDB's default open mode acquires an exclusive file lock, which would cause lock conflicts at steady-state when both services are active simultaneously. **Required configuration:** `query-api` must open DuckDB in `read_only=True` mode (`duckdb.connect(db_path, read_only=True)`). This allows concurrent read access from query-api while vector-writer holds the write lock. Add this as an explicit initialization requirement in the query-api service. `vector-writer` opens DuckDB in default (read-write) mode for its `INSERT OR REPLACE` operations.

### 8.4 BM25 Index

**Role.** Sparse keyword index for exact-match retrieval — concept names, author names, method names, technical terms.

**Scope.** Per domain. Professional domain has its own BM25 index. Personal domain will have its own when implemented. This prevents cross-domain noise (ML papers and philosophy texts in the same index degrade precision for each).

**Persistence.** Index is persisted to host volume. Updated incrementally at the end of the vector-writer indexing step for each new entry. On service startup, index is loaded from disk — no cold rebuild required.

**Fields indexed.** `title`, `summary`, `concepts`, `tags`, `challenge_hooks`. Not `content_raw` (too noisy and large).

**Implementation.** `rank-bm25` Python library with a custom persistence wrapper, or `tantivy-py` for native on-disk persistence. Exact library decision deferred to implementation.

**Single-instance write discipline.** Analogous to the single-writer discipline on SQLite. `rank-bm25` and similar libraries are not multi-process-safe writers. The vector-writer service must acquire a file lock (e.g., `filelock` Python library, cross-platform) on the BM25 index directory before any write operation and release it on completion or failure. If Docker Compose restarts the vector-writer while a write is in progress, the new instance waits on the lock or exits cleanly — it does not corrupt the index.

**Persistence atomicity requirement (S4).** `rank-bm25` operates fully in-memory and requires a custom persistence wrapper. The wrapper must use atomic write semantics: serialize the index to a temporary file in the same directory, call `fsync()` on the temp file, then rename it over the target file (`os.replace(tmp_path, target_path)`). POSIX `rename` is atomic — if the process crashes between the `fsync` and the rename, the target file retains its previous valid state. Do not use in-place overwrite (open target file, write bytes) — a crash mid-write produces a corrupt on-disk index with no recovery path. `tantivy-py` is an alternative that provides WAL-based crash safety natively; if chosen, the atomic wrapper is not required, but its higher startup complexity must be accounted for.

**In-memory index and reload behavior.** The `query-api` loads the BM25 index into memory at startup. The vector-writer updates the on-disk index incrementally after each indexing cycle. The in-memory index in `query-api` diverges from disk immediately after the first new entry is indexed. Known behavior: the query-api reloads the in-memory BM25 index on a configurable interval (default: 5 minutes). During the interval between reloads, newly indexed entries are not reflected in BM25 results but are available via dense semantic search (LanceDB). This is acceptable for a non-real-time personal KB.

**Reload atomicity (G5).** BM25 reload must use a copy-on-write pattern: load the new index from disk into a separate in-memory object, then atomically replace the reference in query-api (`self._bm25_index = new_index`). Do not modify the in-memory index in place during reload — concurrent queries could read a partially-loaded state or trigger a `NullPointerError` if the reference is replaced mid-read.

**Challenge hooks index.** A second per-domain BM25 index over the `challenge_hooks` field only exists alongside the main index. Its storage, locking, and reload requirements are identical: file lock before write, in-memory reload at the same configurable interval (default 5 minutes), updated by vector-writer in the same indexing cycle as the main index. The vector-writer acquires a single file lock per domain covering both indices in the same write operation — do not use separate locks for main and challenge_hooks or introduce interleaved acquisition paths that could deadlock.

**Directory naming convention.** Two indices per domain, namespaced under the domain directory:
```
~/bishop_data/bm25/{domain}/main/          ← main index (title, summary, concepts, tags, challenge_hooks)
~/bishop_data/bm25/{domain}/challenge_hooks/  ← challenge_hooks-only index
```
For the professional domain at MVP: `~/bishop_data/bm25/professional/main/` and `~/bishop_data/bm25/professional/challenge_hooks/`. The single `~/bishop_data/bm25` volume mount in Section 8.5 covers both.

**Embedding model (pinned).** `sentence-transformers/all-MiniLM-L6-v2`, 384 dimensions. Runs in-process as a Python library — no additional service required. Pinned to avoid the schema-breaking consequence of a later model switch (changing the embedding model requires rebuilding the entire LanceDB vector index from `content_raw`).

**Embedding text (pinned, N1).** The text input to the encoder is `title + "\n" + summary + "\n" + " ".join(challenge_hooks)` (see Section 5.6 step 2). This is equally schema-pinning as the model: changing the embedded text produces semantically incompatible vectors requiring the same full LanceDB index rebuild. Document any future change to the embedded text as a logged decision with a planned rebuild, identical to a model change.

**Quality caveat and validation gate.** `all-MiniLM-L6-v2` is a 22M parameter general-purpose model trained on NLI and MSMARCO data. For a KB serving dense technical AI/ML content with heavy acronym and architecture vocabulary, its semantic representations are materially weaker than purpose-built alternatives (e.g., `nomic-embed-text` at 768 dims). The model is pinned for MVP simplicity, not because it is the optimal choice. **Mandatory validation gate:** during e2e validation (cold-start step 9), run 3–5 test queries against `challenge_hooks` that represent realistic mid-spec queries (e.g., "hybrid retrieval for sparse document graphs", "stateful LLM agent crash recovery"). If semantic search fails to surface intuitively expected results, upgrade to `nomic-embed-text` via Ollama (768 dims) before enabling backfill. The index rebuild at that point is cheap (small validation dataset) — the same rebuild at post-backfill scale is expensive. Do not proceed to backfill if the quality gate fails.

If a higher-quality model is chosen later, document it as a logged enhancement, rebuild the LanceDB index from `content_raw` in SQLite, and update the schema dimension constant.

### 8.5 Host-Mounted Volumes

All persistent data stores are mounted from host directories. Container crashes lose no data.

```yaml
# Docker Compose volume mounts (all services that need data access)
volumes:
  - ~/bishop_data/sqlite:/app/data/sqlite
  - ~/bishop_data/lancedb:/app/data/lancedb
  - ~/bishop_data/duckdb:/app/data/duckdb
  - ~/bishop_data/bm25:/app/data/bm25
  - ~/bishop_data/profiles:/app/config/profiles    # versioned NL profiles
  - ~/bishop_data/logs:/app/logs
```

---

## 9. Container Service Map

Nine services. All communicate over a Docker internal network. Only `query-api` and `ui` are accessible from the host (port-mapped to localhost).

| Service | Responsibility | Writes to | Reads from | External API |
|---|---|---|---|---|
| `scraper` | Manifest fetch per source adapter, scheduled | → `state-worker` REST | Source APIs | Yes (sources) |
| `state-worker` | **Only SQLite writer.** State transitions, all table writes, internal REST API, lock-state recovery sweep, retry sweep | SQLite | SQLite | No |
| `pre-filter-worker` | Batches DISCOVERED entries (atomic claim via REST poll → RELEVANCE_QUEUED), submits to Anthropic Batch API (Haiku), posts decisions | → `state-worker` REST | → `state-worker` REST poll (claiming) | Yes (Anthropic) |
| `content-scraper` | Full content fetch for RELEVANCE_PASSED entries | → `state-worker` REST | → `state-worker` REST poll (claiming) | Yes (sources) |
| `enrichment-batcher` | Two separate asyncio tasks: Task A polls SCRAPED entries (Stage 4a, atomic claim via REST), Task B polls ENRICHMENT_STAGE2_QUEUED entries (Stage 4b, atomic claim via REST), each submits independently to Anthropic Batch API | → `state-worker` REST | → `state-worker` REST poll (claiming) | Yes (Anthropic) |
| `batch-poller` | Polls Anthropic for all batch types (pre-filter, enrichment stage 1, enrichment stage 2); on startup, queries state-worker for in-flight BatchRecords and re-registers them; enforces 48hr timeout | → `state-worker` REST | SQLite (BatchRecord reads, non-claiming) | Yes (Anthropic) |
| `vector-writer` | Embeds entries, writes to LanceDB, updates BM25 index, mirrors metadata to DuckDB | LanceDB, DuckDB, BM25 index | → `state-worker` REST poll (claiming) | No (local embedding model) |
| `query-api` | FastAPI. Hybrid retrieval, serves UI. DuckDB opened `read_only=True` | — | LanceDB, DuckDB (`read_only=True`), BM25 index, SQLite (non-claiming reads) | No |
| `ui` | HTMX frontend. Batch summary, DB explorer, entry detail, escalation panel | — | `query-api` | No |

### 9.1 State-Worker Internal REST API

All state transitions route through these endpoints. Contract is POST-heavy. Poll endpoints for stages 1–4b perform atomic claim-and-transition (see Section 6.2). VECTOR_WRITE_QUEUED poll does not (see Section 6.2 exemption note).

```
POST /manifest/batch                    ← scraper writes discovered entries
POST /manifest/pre-filter-results       ← pre-filter-worker (via batch-poller) writes decisions
POST /entries/content                   ← content-scraper writes full content
POST /entries/enrichment-stage1-results ← batch-poller writes Call 1 results
POST /entries/enrichment-stage2-results ← batch-poller writes Call 2 results
POST /entries/indexed                   ← vector-writer signals indexing complete
POST /entries/failed                    ← any service reports a failure
POST /entries/retry                     ← any service or manual trigger retries
GET  /manifest/poll?state=X&domain=Y&limit=N  ← atomic claim for stages 1-2
GET  /entries/poll?state=X&domain=Y&limit=N   ← atomic claim for stages 3-4b; no claim for VECTOR_WRITE_QUEUED
GET  /scraper-state/{source}            ← scraper reads last_run timestamp
POST /scraper-state/{source}            ← scraper updates last_run on successful manifest ingest
GET  /batches?status=submitted,processing  ← batch-poller startup scan (see S3 below)
GET  /batches/{batch_id}
GET  /health                            ← health check for Docker Compose depends_on
GET  /escalations                       ← UI escalation panel
```

**`POST /manifest/batch`** — request body:
```json
{
  "entries": [
    {
      "source_id": "arxiv:2301.xxxxx",
      "source": "arxiv",
      "url": "https://...",
      "title": "...",
      "abstract": "...",
      "published_at": "2026-01-01T00:00:00Z",
      "domain": "professional"
    }
  ]
}
```

**`POST /entries/content`** — request body:
```json
{
  "source_id": "arxiv:2301.xxxxx",
  "content_raw": "<full text, potentially thousands of tokens>"
}
```
state-worker creates the Entry record (identity fields copied from ManifestEntry, `content_raw` set, all enrichment fields null) and transitions manifest entry to `SCRAPED`.

**`POST /entries/enrichment-stage1-results`** — request body (batch array):
```json
{
  "batch_id": "uuid",
  "entries": [
    {
      "source_id": "arxiv:2301.xxxxx",
      "success": true,
      "summary": "...",
      "concepts": ["concept1", "concept2"],
      "tags": ["RAG", "embeddings"],
      "entry_type": "paper",
      "challenge_hooks": ["how to reduce latency in dense retrieval", "..."],
      "error_message": null
    }
  ]
}
```
For entries with `success: false`, `error_message` carries the failure detail; state-worker **normalizes `state_at_failure` before writing the ErrorLog** — it records `ENRICHMENT_STAGE1_FAILED` (not `ENRICHMENT_STAGE1_SUBMITTED`) as `state_at_failure`, regardless of the entry's actual current state. This normalization ensures the manual retry mapping table and the automatic retry sweep both operate consistently on `_FAILED` states only; no separate handling for `_SUBMITTED` states is needed anywhere else in the system. State-worker transitions the entry to `ENRICHMENT_STAGE1_FAILED`. For success entries, state-worker writes Call 1 fields and transitions `ENRICHMENT_STAGE1_SUBMITTED → ENRICHMENT_STAGE1_COMPLETE → ENRICHMENT_STAGE2_QUEUED` atomically (single transaction — see Section 6.2 H3 requirement).

**`POST /entries/enrichment-stage2-results`** — request body (batch array):
```json
{
  "batch_id": "uuid",
  "entries": [
    {
      "source_id": "arxiv:2301.xxxxx",
      "success": true,
      "relevance_score": 0.87,
      "relevance_reason": "Directly addresses hybrid retrieval for sparse graphs.",
      "value_rationale": "...",
      "error_message": null
    }
  ]
}
```
Atomic transaction requirement applies: `ENRICHMENT_STAGE2_SUBMITTED → ENRICHMENT_STAGE2_COMPLETE → VECTOR_WRITE_QUEUED` plus field writes in one `BEGIN/COMMIT`. For per-entry failures, state-worker normalizes `state_at_failure` to `ENRICHMENT_STAGE2_FAILED` in the ErrorLog (not `ENRICHMENT_STAGE2_SUBMITTED`) — same normalization as Stage 4a.

**`POST /entries/indexed`** — request body:
```json
{
  "source_id": "arxiv:2301.xxxxx"
}
```
state-worker transitions entry to `INDEXED` (terminal state).

**`POST /entries/failed`** — request body:
```json
{
  "source_id": "arxiv:2301.xxxxx",
  "state_at_failure": "SCRAPE_QUEUED",
  "error_class": "httpx.TimeoutException",
  "http_status": null,
  "message": "Connection timed out after 30s",
  "is_retriable": true
}
```

**`GET /manifest/poll`** — response body:
```json
{
  "entries": [{ /* full ManifestEntry fields */ }],
  "claimed_count": 50,
  "transitioned_to": "RELEVANCE_QUEUED"
}
```

**`GET /entries/poll`** — response body (S6):
```json
{
  "entries": [{ /* Entry model fields as currently populated; enrichment fields null if not yet enriched */ }],
  "claimed_count": 50,
  "transitioned_to": "ENRICHMENT_STAGE1_QUEUED"
}
```
Returns the full Entry model for each claimed entry. **`content_raw` exclusion at `state=VECTOR_WRITE_QUEUED` (M3):** when polling for `VECTOR_WRITE_QUEUED` entries, state-worker omits `content_raw` from the response. Vector-writer embeds `title + summary + challenge_hooks` (Section 5.6) and does not use `content_raw`. At backfill scale, returning `content_raw` (full untruncated fetched content, potentially thousands of tokens per entry) for each batch-poll would produce payload sizes with no benefit. For all other state values, `content_raw` is included in the response.

**`GET /scraper-state/{source}`** — response body (M4):
```json
{
  "source": "arxiv",
  "last_successful_run_at": "2026-06-01T12:00:00Z",
  "updated_at": "2026-06-01T12:00:00Z"
}
```
Returns `null` for `last_successful_run_at` on first run (source has never scraped). Scraper interprets `null` as "use `backfill_window_days` config."

**`POST /scraper-state/{source}`** — request body (M4):
```json
{
  "timestamp": "2026-06-08T10:00:00Z"
}
```
Response: `204 No Content`. Sets `last_successful_run_at` to the provided timestamp.

**`GET /batches?status=submitted,processing`** — batch-poller startup scan (S3):
Returns all BatchRecords with status in the specified set. batch-poller calls this on startup to re-discover in-flight batches and re-register them in its active polling queue. Without this startup scan, any batch submitted before a batch-poller restart is silently orphaned — entries remain in `_SUBMITTED` states indefinitely because no poller knows about them. The 48-hour timeout in batch-poller's polling loop can only be enforced for batches the poller knows about; orphaned batches are never timed out.

---

## 10. Source Adapter Pattern

### 10.1 Abstract Base

Every source implements this interface. All source-specific logic (pagination, auth, response parsing, rate limiting) is encapsulated inside the adapter. The pipeline is source-agnostic.

```python
from abc import ABC, abstractmethod

class SourceAdapter(ABC):
    source: SourceEnum              # class-level constant
    domain: DomainEnum              # which workflow this belongs to
    rate_limit: RateLimit           # from SOURCE_RATE_LIMITS config

    @abstractmethod
    async def fetch_manifest(
        self,
        since: datetime | None = None
    ) -> list[ManifestEntry]:
        """
        Lightweight scrape: IDs, titles, abstracts only.
        No full content. Returns canonical ManifestEntry objects.
        since: timestamp for incremental fetch. None = backfill window.
        """
        ...

    @abstractmethod
    async def fetch_content(self, entry: ManifestEntry) -> str:
        """
        Full content fetch for a single manifest entry.
        Returns raw content string (paper body, README, article text).
        """
        ...

    def make_source_id(self, raw_id: str) -> str:
        """Canonical source ID format: 'source_name:raw_id'"""
        return f"{self.source.value}:{raw_id}"
```

### 10.2 Adapter Registry

Adding a source is one line in this list. The scraper loop iterates all registered adapters.

```python
ADAPTER_REGISTRY: list[type[SourceAdapter]] = [
    ArxivAdapter,
    SemanticScholarAdapter,
    HuggingFaceAdapter,
    PapersWithCodeAdapter,
    GitHubAdapter,
    OpenReviewAdapter,
    LessWrongAdapter,      # verify GraphQL API availability before implementing
]
```

### 10.3 Scraper Loop

```python
async def scrape_cycle():
    for AdapterClass in ADAPTER_REGISTRY:
        adapter = AdapterClass()
        # Read per-source last_run timestamp before fetching — each source has its own
        # run history. A single global last_run would either under-fetch (recently-run sources)
        # or over-fetch (sources not yet run). ScraperState is per-source (Section 7.6).
        last_run = await state_worker_client.get_scraper_state(adapter.source)
        try:
            entries = await failure_envelope(
                adapter.fetch_manifest,
                since=last_run,
                source=adapter.source
            )
            await state_worker_client.post_manifest_batch(entries)
            # Update last_run only after successful manifest batch write
            await state_worker_client.update_scraper_state(adapter.source, now())
        except PermanentFailureError as e:
            log_permanent_failure(adapter.source, e)
```

### 10.4 Failure Envelope

Wraps any adapter call with source-specific retry logic and failure classification.

```python
async def failure_envelope(
    fn: Callable,
    *args,
    source: SourceEnum,
    **kwargs
) -> Any:
    config = SOURCE_RATE_LIMITS[source]
    attempt = 0
    while attempt <= config.max_retries:
        try:
            return await fn(*args, **kwargs)
        except RETRIABLE_EXC as e:
            if attempt == config.max_retries:
                raise RetryExhaustedError(source, attempt, e)
            delay = compute_backoff(config, attempt)
            await asyncio.sleep(delay)
            attempt += 1
        except HTTPStatusError as e:
            if e.status_code in RETRIABLE_HTTP:
                # same as above
                ...
            elif e.status_code in ESCALATABLE_HTTP:
                raise EscalatableError(source, e.status_code, e)
            else:
                raise PermanentFailureError(source, e.status_code, e)
```

---

## 11. NL Profile System

### 11.1 Design Rationale

Semantic anchor embeddings (pre-computed vectors of representative texts) were evaluated as the pre-filter mechanism and deferred in favor of a versioned NL profile. Rationale:

- Anchor curation requires well-labeled representative texts — a bootstrapping problem.
- Anchor vectors are opaque: hard to inspect, update, or reason about.
- A natural-language profile is writable in minutes, diffable in git, and self-documenting.
- The LLM pre-filter generates labeled data (relevance=0/1) as a byproduct — this data is the foundation for eventually computing cosine anchors (the bootstrapping cycle, documented in deferred items).

### 11.2 Profile File Structure

Profiles live at `config/profiles/{domain}_v{version}.yaml`. An active profile pointer per domain references the current version. Profile updates are git commits — the diff is the changelog.

```yaml
version: "1.0.0"
created_at: "2026-06-10"
domain: professional
label: "AI/ML Engineering — Professional"

# SHA-256 hash of the canonical rendered prompt string for this profile version.
# Computed when the profile is authored/updated, committed to git alongside the content.
# At batch time: render the profile → hash it → compare against this value.
# Mismatch (e.g., from serialization library drift) → abort batch, log, alert.
canonical_hash: "placeholder_compute_on_first_render"

changelog:
  - version: "1.0.0"
    date: "2026-06-10"
    note: "Initial profile"

# Injected as system prompt in Anthropic Batch API calls (pre-filter and Call 2 enrichment).
# This string must be rendered deterministically across all calls in a batch.
# SHA-256 hash stored on BatchRecord.profile_render_hash for audit.
# Once this profile grows to meet Anthropic's prompt caching minimum token threshold,
# prompt caching (cache_control blocks) will apply automatically, reducing input token cost
# further on top of the 50% Batch API discount.
context: |
  I am an Applied AI Engineer specializing in NLP, RAG systems, agentic workflows,
  LLM-based document intelligence, and production ML systems. I build these systems
  professionally. Judge relevance from the perspective of a practitioner who ships
  production-grade AI, not an academic reviewer.

# Evaluation principles
principles:
  - "Prefer practical applicability over theoretical novelty"
  - "Value production concerns: latency, reliability, cost, observability, failure modes"
  - "Value architectural patterns, tradeoffs, and engineering decisions"
  - "Deprioritize pure math papers without engineering application"
  - "Prioritize content actionable within a 6-month horizon"

# Domain anchors — specific interest areas with per-anchor rationale
anchors:
  - id: rag_retrieval
    label: "RAG and Retrieval Systems"
    rationale: >
      Core to current work. Hybrid retrieval, reranking, late chunking,
      embedding models, vector stores, knowledge graphs for retrieval.
    weight: 1.0

  - id: agentic_systems
    label: "Agentic Systems and Orchestration"
    rationale: >
      LangGraph, multi-agent patterns, state machines, tool use, planning,
      memory architectures, agent evaluation.
    weight: 1.0

  - id: llm_inference
    label: "LLM Inference and Serving"
    rationale: >
      Quantization, batching, latency/throughput tradeoffs, serving frameworks.
      Relevant for production deployment decisions.
    weight: 0.8

  - id: document_intelligence
    label: "Document Intelligence and Extraction"
    rationale: >
      Schema-bound extraction, structured output, document parsing pipelines.
      Directly relevant to Hermes-type systems.
    weight: 0.9

  - id: eval_observability
    label: "LLM Evaluation and Observability"
    rationale: >
      Evaluation frameworks, tracing, LLM-as-judge, production monitoring.
    weight: 0.7

# Hard exclusions
exclusions:
  - "Pure computer vision or robotics without LLM/NLP application"
  - "Market analysis or business news without technical substance"
  - "Tutorial content at introductory level (assume expert baseline)"
  - "Hardware-only content without ML application"

# Output contract — do not modify without updating the pre-filter prompt template
output:
  format: integer
  include_rationale: true
  rationale_max_tokens: 60
  instruction: >
    Respond with a JSON object: {"decision": 0 or 1, "rationale": "one sentence"}.
    No other output. No preamble.
```

### 11.3 Profile Versioning Contract

- Semver: `MAJOR.MINOR.PATCH`. Breaking changes (new anchors, changed context) bump MINOR. Wording tweaks bump PATCH.
- Every `ManifestEntry` and `Entry` carries `profile_version` — the version that produced the relevance decision.
- Entries enriched under an older profile have stale relevance scores. The operative default is to accept this and treat scores as comparable only within the same profile version. Re-enrichment on version bump is a documented future capability (see deferred items).
- The profile render function must produce a byte-identical string for the same profile version across all calls in a batch. **Implementation requirement:** the render function must use canonicalized serialization — load the YAML, serialize to JSON with sorted keys (`json.dumps(yaml_dict, sort_keys=True, ensure_ascii=True)`), and hash the resulting UTF-8 bytes. Do not hash raw YAML serialization output — YAML libraries do not guarantee field ordering across versions or environments, which means the same YAML file can produce different byte strings on different machines or after a library upgrade, causing spurious hash mismatches and batch aborts. JSON with sorted keys is deterministic and portable. Implement as: load YAML → convert to dict → `json.dumps(dict, sort_keys=True)` → SHA-256 hash of the UTF-8 encoded result. The hash is stored as `profile_render_hash` on the `BatchRecord` at batch creation time for retroactive audit. The **reference value** for drift detection is `canonical_hash` stored in the profile YAML file itself — computed when the profile is authored or updated and committed to git alongside the content change. At batch time: render → hash → compare against `canonical_hash` from the YAML. If they differ, abort the batch, log the mismatch, and alert. This design is self-contained: the canonical source of truth (the YAML file) carries its own expected hash, and git diff of any profile update shows both the content change and the hash update together.

---

## 12. Pre-filter Layer

### 12.1 Mechanism

LLM binary classification using Anthropic Batch API (`claude-haiku-4-5-20251001`). This consolidates all external LLM calls to a single provider (Anthropic), eliminating the need for a second API key, a second batch-polling flow, and a second provider dependency.

- **API:** Anthropic Batch API. 50% discount over standard Haiku pricing. Async by design — results available within 24 hours. This matches the non-urgent operational model exactly.
- **System prompt:** Rendered NL profile for the entry's domain. Identical string across all calls in the same batch. SHA-256 hash stored on BatchRecord as `profile_render_hash`. As the NL profile grows toward Anthropic's prompt caching minimum token threshold (via natural iteration and refinement), prompt caching via `cache_control` blocks becomes available, yielding additional input token cost reduction on top of the batch discount. Growing the profile to meet the caching threshold is the documented future path (Phase 1.5 of the bootstrapping cycle).
- **User prompt (dynamic per entry):** Title + abstract.
- **Output:** `{"decision": 0 or 1, "rationale": "one sentence"}`. Single integer minimizes response tokens.
- **Batch size:** 50 entries per batch (default; configurable). The Anthropic Batch API supports a maximum of 10,000 requests per batch — 50 is a conservative operational default chosen for manageable batch sizes and faster iteration, not for proximity to the cap. Adjustable empirically.
- **Model string:** `claude-haiku-4-5-20251001`. Pinned to the dated snapshot identifier. If an undated alias (`claude-haiku-4-5`) is not a supported stable alias, the Batch API returns HTTP 400 (Fatal → PERMANENTLY_FAILED), producing a 100% failure rate at pre-filter stage on first run. **Build checklist requirement:** before integrating any pipeline component against the Batch API, make one direct test call to the Anthropic Messages API (not Batch) using the model string to verify it resolves to a valid model. This gates all enrichment pipeline work.
- **Cadence:** Async. Pre-filter worker polls for DISCOVERED entries, assembles batches, submits. Batch-poller polls for results. No urgency; nothing is time-sensitive in this pipeline.
- **Cost reference:** At 100 entries/day with ~300 input tokens per entry (title + abstract + profile): ~30K tokens/day. At Haiku batch pricing (~$0.0125/1M input tokens), this is ~$0.0004/day. Cost is irrelevant at this scale — engineer for correctness.

### 12.2 Why Not Embedding Similarity

Addressed in 11.1. Short version: opaque, requires curated seed texts, expensive to update, produces no labeled data. LLM binary produces interpretable decisions, is trivially updatable (edit YAML), and generates training data for future cosine migration.

### 12.3 Bootstrapping Cycle (Documented, Not Implemented)

```
Phase 1 (current): LLM binary pre-filter via Anthropic Batch API
  → 50% batch discount, async, no caching yet (profile below caching threshold)
  → generates relevance-labeled entries as byproduct
  → pre_filter_rationale field captures decision reasoning

Phase 1.5 (organic, no implementation needed):
  → as NL profile is iterated and grows, it will eventually meet
     Anthropic's prompt caching minimum token threshold
  → prompt caching (cache_control blocks) applies automatically at that point
  → additional input token savings on top of batch discount, no code change required

Phase 2 (future, when N labeled entries accumulated):
  → embed the relevant subset
  → cluster or centroid-average per anchor domain
  → compute cosine thresholds from the distribution
  → validate against LLM labels (precision/recall check)
  → optionally switch hot path to local cosine similarity
  → keep LLM pre-filter as fallback or calibration check

Phase 3 (optional): LLM pre-filter demoted to edge cases
  → local cosine is primary
  → LLM fires only for borderline cases (cosine in ±0.05 of threshold)
```

Trigger for Phase 2: subjective — when you have enough labeled data to trust the cluster centroids. No hard N defined; assess from usage.

---

## 13. Enrichment Pipeline

### 13.1 Two-Call Architecture

Enrichment is split into two separate Anthropic Batch API submissions to keep context windows small and concerns separated.

**Call 1 — Factual Extraction.**
- Context: source-agnostic, no profile injected.
- Input: title + `content_raw` (truncated to 4,000 tokens maximum — see truncation policy below).
- Output fields: `summary`, `concepts`, `tags`, `entry_type`, `challenge_hooks`.
- Model: `claude-haiku-4-5-20251001` via Anthropic Batch API.
- Prompt design: structured JSON output with field definitions and hard taxonomy constraint (see taxonomy enforcement below).

**Call 2 — Evaluative / Profile-Aware.**
- Context: NL profile injected as system prompt (Anthropic prompt caching via `cache_control` blocks once profile meets minimum token threshold).
- Input: title + summary from Call 1 (not full content — summary is sufficient for evaluative judgment, keeps tokens low).
- Output fields: `relevance_score`, `relevance_reason`, `value_rationale`.
- Model: `claude-haiku-4-5-20251001` via Anthropic Batch API.
- Profile hash-verify discipline as documented in Section 11.3.

**Content Truncation Policy (Call 1).**

Token ceiling: 4,000 tokens for the `content_raw` payload in Call 1 (measured with tiktoken or equivalent before submission). Per-source-type truncation strategy:

- **Papers (arxiv, openreview, semantic_scholar):** Abstract in full + first 2,000 tokens of body text. Rationale: methodology and contribution typically appear in early body sections; introduction context is in the abstract.
- **Repositories (github):** README in full if under ceiling. If over ceiling: README header (first 500 tokens) + top-level file and directory structure listing. Rationale: README header and project structure reveal the repository's purpose better than truncated prose.
- **HuggingFace model entries (source=huggingface, entry_type=model):** Extract model card YAML metadata block (the `---` delimited YAML front-matter at document start, typically containing architecture, training data, eval results, license fields) + first 2,000 tokens of remaining markdown. Rationale: model card YAML concentrates the most relevant metadata at document start; the "beginning + end" articles strategy systematically truncates architecture and evaluation sections that appear mid-document, degrading `challenge_hooks` quality.
- **All other HuggingFace entries (datasets, spaces, non-model) and articles (lesswrong, paperswithcode):** Beginning 2,500 tokens + final 500 tokens. Rationale: lede and conclusion contain the core claims; middle sections often contain supporting detail.

This policy directly affects `challenge_hooks` quality, which is the most semantically load-bearing output field for Layer 2 retrieval. Prompt engineering for challenge_hooks should be validated against truncated content during e2e validation.

**Taxonomy Enforcement (Call 1 tags field).**

The Call 1 prompt instructs the model to use **only** tags from the controlled taxonomy (Section 20.7). This is a hard constraint, not a suggestion. Parser behavior on response: validate each tag against the taxonomy; strip any out-of-vocabulary tags from the entry; log stripped tags to a dedicated `oov_tags_log` table for taxonomy governance review. The entry is indexed with only validated tags — the enrichment call is not failed for OOV tags, only the specific tags are stripped. OOV tags logged over time are the signal for taxonomy expansion decisions.

### 13.2 Why Two Calls

- Prevents context saturation: Call 1 extracts facts from potentially long content; Call 2 makes judgments against a profile. Combining them into one call risks the evaluative judgment being influenced by noisy content rather than the structured summary.
- Separation of concerns: factual extraction is source-agnostic and reusable; evaluative judgment is profile-specific. If the profile changes, only Call 2 needs to be re-run.
- Independent failure isolation: Call 1 failure does not prevent a retry of Call 1 without losing Call 2 results and vice versa (once both calls have their own states in the state machine).

### 13.3 `challenge_hooks` — Generation Intent

This is the most semantically rich field in the schema and the primary driver of Layer 2 usefulness. The generation prompt for Call 1 must be carefully designed to produce hooks that are problem-shaped from the user's perspective, not topic labels.

Target output format: a list of 2-4 strings, each framing a problem that the entry addresses. Examples:
- "How to reduce latency in dense retrieval without sacrificing recall"
- "Designing an orchestration layer that recovers from tool-call failures"
- "When and how to use late chunking vs fixed-size chunking in RAG pipelines"

These are the strings that will be searched against at query time when the user is mid-spec. Prompt engineering for this field is high-stakes and should be iterated on during early usage.

### 13.4 Cost Reference

All LLM calls use Anthropic Batch API (50% discount on Haiku pricing). At 100 entries entering the pre-filter and 30 entries cleared per day (assuming ~30% pass rate through pre-filter):

- Pre-filter (100 entries/day): ~300 input tokens per entry × 100 = ~30K tokens/day → ~$0.0004/day
- Call 1 (30 entries/day, factual): ~600 input tokens + ~150 output tokens per entry → ~$0.003/day
- Call 2 (30 entries/day, evaluative): ~400 input tokens (summary + profile) + ~100 output tokens per entry → ~$0.002/day

Total estimated: ~$0.005–0.01/day at steady state. At backfill scale (10x volume): ~$0.05–0.10/day.

Cost is irrelevant at this scale. Engineer for correctness.

---

## 14. Error Handling and Dead-Letter

See Section 6.3 for failure classification. This section covers visibility and recovery.

### 14.1 Error Log

All failures are written to the `error_log` table (see Schema 7.4) by `state-worker` when it receives a failure POST. The log is queryable for debugging and pattern detection.

### 14.2 Escalation Panel

The UI `escalation panel` shows all entries in `ESCALATION_FLAGGED` state. For each entry:
- Title, source, URL
- Current state
- Error log: all attempts with timestamps, HTTP status, error class, message
- Actions: `Manual Retry` (resets state to the work-ready predecessor state), `Mark Permanently Failed`, `Mark Resolved`

**Manual retry target state mapping (S7).** `ESCALATION_FLAGGED` is reached from multiple failure paths. The retry target is derived from the entry's most recent `state_at_failure` in the `error_log` table, using this canonical mapping:

| `state_at_failure` | Manual retry target |
|---|---|
| `SCRAPE_QUEUED` or `SCRAPE_FAILED` | `RELEVANCE_PASSED` |
| `ENRICHMENT_STAGE1_QUEUED` or `ENRICHMENT_STAGE1_FAILED` | `SCRAPED` |
| `ENRICHMENT_STAGE2_CLAIMED` or `ENRICHMENT_STAGE2_FAILED` | `ENRICHMENT_STAGE2_QUEUED` |
| `VECTOR_WRITE_QUEUED` or `VECTOR_WRITE_FAILED` | `VECTOR_WRITE_QUEUED` |

State-worker reads the most recent `error_log` entry for the given `source_id` to determine `state_at_failure`, applies the table, and transitions to the work-ready predecessor. The retry also resets `retry_count` to 0 (manual retry is an explicit intervention, not a continuation of the automatic retry budget). This mapping table is also the canonical reference for the automatic retry sweep in Section 6.2.

### 14.3 Alert Definition (G2)

MVP alert behavior: alerts are structured log entries at `CRITICAL` log level with a designated `alert_type` field. They are written to the standard application log (queryable from file or Docker log output) and also written as records to the `error_log` table with a distinct `error_class = "ALERT"`. This makes alerts queryable alongside error history without a separate alerting infrastructure.

Alert conditions currently referenced in the spec: profile hash mismatch (Section 11.3), 48-hour batch timeout (Sections 5.4, 5.5), batch abort events. At MVP, there is no push notification, email, or pager integration — alerts are surfaced through log inspection and the escalation panel. Operational experience post-MVP defines whether alert fatigue warrants a push channel.

### 14.4 Dead-Letter

`PERMANENTLY_FAILED` entries are terminal. They remain in the manifest table for visibility but are never re-queued. The error_log carries the full history. Manual inspection of permanently failed entries after the system has been running for a while should inform whether any failure patterns indicate bugs in the adapters.

### 14.5 Failure Visibility

Failures are also surfaced in the batch summary view when a batch completes with `failed_count > 0`. The batch record carries `failed_count` and the top-level batch status captures whether any entries failed within the batch.

---

## 15. Rate Limiting and Failure Envelope

### 15.1 Per-Source Rate Limit Configuration

```python
@dataclass
class RateLimit:
    calls: int
    period_seconds: int
    backoff: Literal["exponential", "linear"]
    max_retries: int
    jitter: bool = True

SOURCE_RATE_LIMITS: dict[str, RateLimit] = {
    "arxiv":            RateLimit(calls=3,    period_seconds=1,    backoff="exponential", max_retries=4),
    "github":           RateLimit(calls=5000, period_seconds=3600, backoff="linear",      max_retries=5),
    "semantic_scholar": RateLimit(calls=100,  period_seconds=1,    backoff="exponential", max_retries=3),
    "huggingface":      RateLimit(calls=50,   period_seconds=1,    backoff="exponential", max_retries=3),
    "paperswithcode":   RateLimit(calls=20,   period_seconds=1,    backoff="exponential", max_retries=3),
    "openreview":       RateLimit(calls=10,   period_seconds=1,    backoff="exponential", max_retries=3),
    "lesswrong":        RateLimit(calls=5,    period_seconds=1,    backoff="exponential", max_retries=3),
}
```

### 15.2 Backoff Formula

Exponential: `delay = base_delay * (2 ** attempt) + random.uniform(-jitter, +jitter)`
Linear: `delay = base_delay * attempt + random.uniform(-jitter, +jitter)`
Base delay: 1 second. Jitter: ±0.2 * computed delay.

### 15.3 Rate Limiter Implementation

Use `asyncio-throttle` or a token bucket implementation per source. The rate limiter is instantiated per adapter instance and enforces the `calls/period_seconds` config. The failure envelope and the rate limiter are separate concerns: the rate limiter prevents hitting API limits; the failure envelope handles the case where limits are hit anyway (429).

---

## 16. Query Layer

### 16.1 Retrieval Stack

Two ranked retrieval channels combined via RRF fusion, with a third channel conditionally activated for problem-shaped queries. A metadata filter operates as a hard pre/post-filter, not as a ranked-list channel.

**Channel 1: BM25 (sparse, keyword-exact) — always active**
- Fields indexed: `title`, `summary`, `concepts`, `tags`, `challenge_hooks`
- Good for: concept names, author names, method names, exact technical terms
- Index: per-domain, persisted, updated at indexing time
- Implementation: loaded in-memory at `query-api` startup from persisted index

**Channel 2: Dense Semantic (LanceDB) — always active**
- Vector search over entry embeddings
- Good for: conceptual / problem-shaped queries, vocabulary mismatch
- Returns top-k by cosine similarity

**Channel 3: Challenge Hooks BM25 — conditionally active (problem-shaped queries only)**
- Separate per-domain BM25 index over `challenge_hooks` field only
- Activated when the query is classified as problem-shaped (see Section 16.3)
- Good for: "how do I handle X" queries that map to practitioner problem framings

**Metadata Filter (DuckDB) — hard pre/post-filter, not an RRF channel**
- Structured predicates: source, date range, tags, entry_type, min_relevance_score, domain, reading_status
- Applied as a hard filter before retrieval (reduces candidate set) or after fusion (post-filter on results)
- Does not participate in RRF scoring — it is not a ranked list
- Good for: "papers from last 30 days tagged RAG with relevance > 0.7"

### 16.2 Fusion — Reciprocal Rank Fusion (RRF)

RRF combines ranked lists from active retrieval channels without a model. Standard formula:

```
RRF_score(d) = Σ 1 / (k + rank(d, list_i))
where k = 60 (standard constant)
     rank(d, list_i) is the 1-indexed rank of document d in channel i's result list
```

**Channel activation per query:**
- Standard queries: 2-channel fusion (Channel 1: main BM25 + Channel 2: dense)
- Problem-shaped queries: 3-channel fusion (Channel 1: main BM25 + Channel 2: dense + Channel 3: challenge_hooks BM25)

**Absent-channel behavior.** A document absent from a given channel's ranked list is implicitly assigned rank ∞ — its contribution to the RRF sum for that channel is 0 (since 1/(k + ∞) = 0). This is the correct RRF behavior: channels that don't return a document don't penalize it, they simply contribute nothing. When Channel 3 is inactive (non-problem-shaped query), it contributes 0 for all documents — effectively a 2-channel computation. This means the formula is identical regardless of whether one writes it as a 2-channel or 3-channel sum; inactive channels are transparent.

Metadata filter is applied as a hard filter either before retrieval (reduces candidate set) or as a post-filter on the fused results, depending on query type. Interactive queries benefit from pre-filtering to reduce retrieval set; exploratory queries benefit from post-filtering to preserve recall.

### 16.3 Challenge Hooks Retrieval Path

When a query is classified as problem-shaped, run a dedicated BM25 pass over the `challenge_hooks` field (Channel 3) in addition to the standard 2-channel retrieval. Results from Channel 3 are included in the RRF fusion as described in Section 16.2.

**Problem-shaped query detection.** Applied at query-api dispatch time before any retrieval. A query is classified as problem-shaped if it matches any of the following heuristics:

*Prefix patterns:*
- Starts with any of: "how to", "how do i", "how do you", "how can i", "what approaches", "best way to", "strategies for", "when to", "why does", "when does"

*Content signals (anywhere in query):*
- Contains any of: "challenge", "problem", "issue", "error", "fail", "failure", "retry", "recover", "handle", "bottleneck", "tradeoff", "vs", "versus", "alternative"

This is a heuristic, not a semantic classifier. It is intentionally broad to avoid false negatives — the cost of unnecessarily running Channel 3 is a slightly wider retrieval set, not a degradation in quality. The challenge_hooks field contains practitioner problem framings; surfacing it on borderline queries is net positive. The heuristic can be tightened from usage observation without a spec change.

**Channel 3 is not activated on pure keyword or structured queries.** Examples: `"LangGraph"`, `"papers from last 30 days tagged RAG"`, `"arxiv 2024 hybrid retrieval"` — none trigger Channel 3. The challenge_hooks index adds noise on exact-lookup queries because its vocabulary is problem-shaped, not keyword-shaped.

### 16.4 Query Interface (CLI + API)

`query-api` exposes search endpoints consumed by the UI. A CLI wrapper using Typer can also call these endpoints for mid-workflow queries without opening a browser.

```bash
kb search "sparse graph retrieval" --type paper --days 60
kb search "schema-bound extraction" --tags NLP,RAG --min-relevance 0.7
kb recent --source arxiv --days 7
kb batch <batch_id>
kb escalations
```

### 16.5 Query Expansion (Deferred)

When retrieval quality shows gaps, add query expansion: generate 2-3 reformulations of the query at query time, retrieve for each, union the candidate sets before fusion. Trigger: observable retrieval misses during usage. Implementation: lightweight Haiku call at query time (250-500ms overhead, acceptable for interactive use). Until triggered, defer.

### 16.6 Reranker (Deferred)

Cross-encoder reranker (`ms-marco-MiniLM-L-6-v2`) scoring `(query, doc)` pairs for top-k re-ranking after RRF fusion. Trigger: RRF fusion results feel noisy during usage. Until triggered, defer.

---

## 17. Surface Layer and UI

### 17.1 MVP — Batch Summary

When any batch (pre-filter or enrichment_stage2) reaches `complete` status, its `BatchRecord` is surfaced in the UI. The batch summary view shows:
- Batch metadata: batch_id, batch_type, domain, profile_version, completed_at, entry_count, passed_count
- Ranked entry list (top 20 by relevance_score): title, summary, relevance_score, entry_type, tags
- Click-through to full entry detail: all enriched fields, content_raw (collapsible), pre_filter_rationale, value_rationale, challenge_hooks, reading_status controls

The batch_id is the canonical reference for "what came in this run." Batches are browsable and filterable by batch_type, domain, date range.

### 17.2 Daily Digest (Deferred)

A daily summary notification of net-new enriched entries from the last 24 hours, ranked by relevance. Deferred until the system is in steady-state operation (backfill complete, pipeline validated). Rationale: during the backfill phase, the "daily" digest would be hundreds of entries processed out of chronological order — not meaningful. The batch summary is the correct surface for the backfill phase.

### 17.3 UI Service

**Stack.** FastAPI backend (`query-api`) + HTMX frontend (`ui`). HTMX provides server-side rendering with hypermedia responses — minimal JavaScript, no build toolchain, easy iteration. The query patterns (search, filter, paginate, click-through) map cleanly to HTMX's model.

**Why not PyQt6.** Container context makes PyQt6 complex: display forwarding (X11/Wayland via DISPLAY env var, xvfb or XQuartz on host) is platform-dependent and adds non-trivial setup friction. A localhost web UI maps to a port-mapping in Docker Compose — zero display config. Knowledge base UIs also benefit from web's richer filtering and browsing primitives.

**Access.** `query-api` and `ui` are the only services with ports mapped to the host. All other services communicate over the internal Docker network only.

**Pages (MVP):**
1. Batch summary list (sorted by completed_at desc)
2. Batch detail (entry list ranked by relevance_score)
3. Entry detail (full enriched record)
4. Search (hybrid query interface)
5. DB explorer (filter by source, domain, tags, date, entry_type, reading_status)
6. Escalation panel (ESCALATION_FLAGGED entries, error logs, action buttons)

---

## 18. Backfill Strategy

### 18.1 Principles

- Backfill applies to all registered sources, not just ArXiv.
- Backfill runs after e2e validation on small batches — not on first deployment.
- Backfill is idempotency-safe: runs in batches, skips any source_id already in the manifest table.
- Backfill uses the same pipeline as steady-state operation — no special mode.

### 18.2 Per-Source Backfill Configuration

Each adapter has a `backfill_window_days` config value. Set per domain and source:

```python
BACKFILL_CONFIG: dict[str, BackfillConfig] = {
    "arxiv":            BackfillConfig(window_days=60,  categories=["cs.AI", "cs.CL", "cs.LG"]),
    "github":           BackfillConfig(window_days=30),
    "semantic_scholar": BackfillConfig(window_days=60),
    "huggingface":      BackfillConfig(window_days=30),
    "paperswithcode":   BackfillConfig(window_days=60),
    "openreview":       BackfillConfig(window_days=90), # covers last major conference cycle
    "lesswrong":        BackfillConfig(window_days=30),
}
```

These values are starting estimates. Adjust based on first-run volume and content quality assessment.

### 18.3 ArXiv Category Filtering

ArXiv categories must be explicitly scoped per adapter to avoid volume explosion. `cs.AI + cs.CL + cs.LG` is the core set. At ~500 papers/day combined, a 60-day backfill produces ~30,000 papers in the manifest — most will be rejected by the pre-filter. The pre-filter is the volume gate. The manifest table is cheap; enrichment is gated by relevance.

### 18.4 Backfill Chunking

Backfill does not run in a single large batch. It is chunked: fetch N days at a time, write to manifest, allow pre-filter to process before fetching the next chunk. This prevents the manifest table from growing uncontrollably before pre-filter catches up. Chunk size and inter-chunk delay are configurable.

### 18.5 Time-Decayed Retrieval Weights (Deferred)

The intuition is sound: newer content should rank higher for fast-moving domains. The engineering challenge is that age is not a proxy for relevance in all cases (foundational papers from 2020 are still highly relevant). Time decay as a retrieval signal is domain- and query-type-dependent. This is a meaningful retrieval improvement but requires careful design. Documented as deferred; trigger: retrieval feedback showing systematic preference for recent content.

---

## 19. Domain Routing

### 19.1 Design

Professional and personal domains share all infrastructure: state machine, storage, containers, worker logic. They are differentiated by configuration:

- **Source adapters** are tagged with a `domain` field. Each adapter belongs to one domain.
- **NL profiles** are per-domain YAML files. The pre-filter loads the profile matching the entry's domain.
- **BM25 indices** are per-domain (see Section 8.4).
- **Schema `domain` field** on `ManifestEntry` and `Entry` enables domain-scoped queries.
- **Workflow routing** in workers: workers can be configured to process only a specific domain, or all domains, via an environment variable.

### 19.2 Personal Domain (Deferred)

The personal domain (philosophy, psychology, cinema, general intellectual interests) requires:
- A separate NL profile YAML (professional profile anchors are irrelevant)
- Different source adapters (RSS feeds, Substack, PDF ingestion)
- Potentially different controlled vocabulary for tags
- A separate workflow config

Infrastructure is provisioned. Implementation is deferred. Schema supports it from day one via the `domain` field.

### 19.3 Cross-Domain Query (Deferred)

Querying across both professional and personal domains simultaneously (e.g., "what connections exist between stoic philosophy and distributed systems design?") requires unioning both BM25 indices and both LanceDB namespaces, then fusing results. Deferred until both domains are active.

---

## 20. Enumerations and Controlled Vocabularies

These are scaffolded for MVP and expected to be iterated on from usage. Values below are starting points, not final.

### 20.1 SourceEnum
```
arxiv | semantic_scholar | huggingface | paperswithcode | github | openreview | lesswrong
```

### 20.2 EntryTypeEnum
```
paper | model | dataset | repo | article | spec | idea | benchmark | other
```

### 20.3 DomainEnum
```
professional | personal
```
Note: `both` was removed. Cross-domain entries have undefined routing logic at MVP — which NL profile applies, which BM25 index receives the entry. Reintroduce `both` with explicit routing semantics documented when cross-domain entries become a real use case.

### 20.4 BatchTypeEnum
```
pre_filter | enrichment_stage1 | enrichment_stage2
```

### 20.5 BatchStatusEnum
```
pending | submitted | processing | complete | failed | batch_timed_out
```
Note: `batch_timed_out` is diagnostically distinct from `failed`. `failed` means the batch ran and errors occurred. `batch_timed_out` means the batch was submitted but never returned a result within the 48-hour maximum wait. This distinction matters for operational diagnosis and retry strategy.

### 20.6 ReadingStatusEnum
```
unread | reading | read | archived
```

### 20.7 OovReviewStatusEnum
```
pending | added_to_taxonomy | rejected
```

### 20.8 Tags (Controlled Taxonomy — MVP Scaffold)
```
NLP | RAG | agentic | multi-agent | LangGraph | inference | serving | evaluation |
observability | fine-tuning | document-intelligence | embeddings | vector-stores |
graph-retrieval | hybrid-retrieval | prompt-engineering | structured-output |
memory-architecture | tool-use | orchestration | dataset | benchmark | survey |
production | deployment | optimization | architecture | safety | alignment
```

Extend from usage. Unrecognized tags from enrichment are stripped by the parser, logged to `oov_tags_log` table, and reviewed before being added to the taxonomy. The `oov_tags_log` table is the governance mechanism for taxonomy evolution. Do not add tags to the taxonomy based solely on model output — validate against actual usage patterns first.

---

## 21. Cold Start and Bootstrapping

No special cold-start mode. The system starts with an empty database. The NL profile is initialized at v1.0.0 for the professional domain. On first run, source adapters use their `backfill_window_days` config for their `since` parameter.

**Sequence for first deployment:**
1. Bring up all containers.
2. Run Alembic migrations synchronously before starting the asyncio event loop: a sync SQLAlchemy engine opens the SQLite file, runs `alembic upgrade head`, closes. The asyncio event loop starts only after migrations complete successfully. This is required because Alembic is synchronous and cannot be run inside the state-worker's async context without a wrapper.
3. Initialize LanceDB and DuckDB stores (empty, created on first write).
4. Initialize BM25 index (empty, built incrementally from first entries indexed).
5. Verify `state-worker` is healthy and accepting POSTs.
6. **Query-api first-run initialization contract (G7).** On startup, query-api may attempt to load BM25, LanceDB, and DuckDB stores before any entries are indexed. Required graceful behavior: if the BM25 index directory does not exist, initialize an empty in-memory index (zero documents, queries return empty results). If the LanceDB table does not exist, skip the table open and serve empty results for vector search queries. If DuckDB tables do not exist, serve empty results for metadata queries without raising an error. Each missing store logs a `WARN`-level message. These conditions are normal on first deployment and resolve automatically as the pipeline begins indexing. Query-api must not crash on first deployment due to missing stores.
7. Run scraper against a single source (e.g., ArXiv cs.AI, last 7 days) as smoke test.
8. Verify entries flow through pre-filter → scrape → enrichment_stage1 → enrichment_stage2 → indexed.
9. Verify batch summaries appear in UI.
10. **Embedding model quality gate (mandatory before backfill).** Run 3–5 test queries against `challenge_hooks` in the indexed validation set using realistic mid-spec phrasings. If semantic search results are not intuitively correct, upgrade the embedding model to `nomic-embed-text` (768 dims via Ollama) before backfill. The index rebuild at this point is cheap. Proceeding to backfill with a failing quality gate is not acceptable — Layer 2 retrieval quality is the primary value proposition of the system.
11. Validate quality of pre-filter decisions and enrichment output. Iterate on NL profile if pre-filter recall or precision is off.
12. After e2e validation and quality gate passage, expand to all sources and enable backfill.

**Phase-gated deployment is mandatory.** Do not enable full backfill until the pipeline is validated e2e. Volume at backfill scale is an order of magnitude higher than steady-state. A bug in the enrichment prompt or the pre-filter that goes undetected at small scale will produce thousands of incorrectly enriched entries at backfill scale.

---

## 22. Build Checklist

Ordered by dependency. Each item should be considered a discrete unit of work.

### Foundation
- [ ] Repository structure and Docker Compose skeleton (all 9 services, volume mounts, internal network, port mappings for query-api and ui)
- [ ] `state-worker` must expose `GET /health` endpoint. All dependent services declare `depends_on: state-worker: condition: service_healthy` in Docker Compose. Without this, services start before state-worker is ready and fail immediately on their first POST.
- [ ] SQLite schema migration setup via Alembic (migration scripts for manifest, entries, batches, error_log, oov_tags_log, scraper_state tables). Migrations run synchronously via sync SQLAlchemy before the asyncio event loop starts — do not run inside the async context.
- [ ] State-worker service: async event loop (asyncio + aiosqlite), all state transition logic, atomic claim-and-transition on poll endpoints (VECTOR_WRITE_QUEUED exempt), scraper_state read/write endpoints, internal REST API endpoints, **lock-state recovery background sweep** (asyncio task, default 5-min sweep interval, 15-min stuck-entry threshold, resets RELEVANCE_QUEUED → DISCOVERED, SCRAPE_QUEUED → RELEVANCE_PASSED, ENRICHMENT_STAGE1_QUEUED → SCRAPED, ENRICHMENT_STAGE2_CLAIMED → ENRICHMENT_STAGE2_QUEUED), **retry sweep** (same asyncio task; scans _FAILED entries where `next_retry_at ≤ now` and `retry_count < RETRY_MAX_ATTEMPTS`; configurable constant default 3; separate scope from adapter per-source `max_retries`; re-enqueues per Section 6.2 retry mapping table), **multi-step write transactions** (COMPLETE + field writes + next QUEUED must execute in explicit `BEGIN`/`COMMIT`/`ROLLBACK` — not `async with conn` — see Section 6.2 H3 requirement), **`GET /batches?status=submitted,processing`** endpoint for batch-poller startup scan, **SUBMITTED→FAILED normalization** in ErrorLog write path for batch result failures (Section 9.1)
- [ ] Enum definitions and Pydantic model definitions (ManifestEntry, Entry, BatchRecord, ErrorLog, OovTagsLog, ScraperState, OovReviewStatusEnum)

### Source Adapters
- [ ] SourceAdapter abstract base class
- [ ] ADAPTER_REGISTRY and scraper loop (reads `last_run` per adapter via `GET /scraper-state/{source}` at the start of each adapter's fetch — not a single global timestamp; POSTs update to `POST /scraper-state/{source}` after successful manifest batch; see Section 10.3 pseudocode)
- [ ] Failure envelope (with per-source RateLimit config, retry logic, failure classification)
- [ ] ArxivAdapter (highest priority, most volume)
- [ ] HuggingFaceAdapter
- [ ] PapersWithCodeAdapter
- [ ] SemanticScholarAdapter
- [ ] GitHubAdapter
- [ ] OpenReviewAdapter
- [ ] LessWrongAdapter (verify API availability first)

### Pre-filter Layer
- [ ] **Model string verification (H2, prerequisite for all LLM pipeline work):** before building any component that calls the Anthropic API, make one direct test call to the Anthropic Messages API using model `claude-haiku-4-5-20251001` to verify it resolves to a valid model. HTTP 400 on this call means the model string is invalid — all enrichment pipeline work is blocked until the correct identifier is confirmed. This is a 60-second check; do not skip it.
- [ ] NL profile YAML for professional domain (v1.0.0)
- [ ] **Compute and commit `canonical_hash` for `professional_v1.0.0.yaml`:** after writing the profile content, run the render function (load YAML → `json.dumps(dict, sort_keys=True)` → SHA-256 hash of UTF-8 bytes), write the resulting hash string into the `canonical_hash` field of the YAML file, then commit the YAML file with both content and hash in a single git commit. If this step is skipped or the hash is left as `"placeholder_compute_on_first_render"`, the first pre-filter batch will fail the hash verification check and abort. Do not compute the hash separately from the render function used at batch time — the hash must be produced by the exact same serialization path.
- [ ] Profile renderer (YAML → canonical prompt string, deterministic, SHA-256 hash function, hash stored on BatchRecord)
- [ ] Pre-filter worker: atomic claim via poll endpoint, batch assembly (default 50), Anthropic Batch API submission (Haiku), response parsing
- [ ] Batch-poller: Anthropic batch polling for pre-filter batches, 48hr timeout enforcement, result POST to state-worker; **startup scan on service init** — call `GET /batches?status=submitted,processing` on state-worker, re-register all returned BatchRecords in the active polling queue before beginning normal poll loop
- [ ] State transitions: DISCOVERED → RELEVANCE_QUEUED (atomic) → RELEVANCE_PASSED / RELEVANCE_REJECTED

### Content Scraping
- [ ] Content-scraper service: atomic claim via poll endpoint (→ SCRAPE_QUEUED), calls adapter.fetch_content, POSTs to state-worker
- [ ] State transitions: RELEVANCE_PASSED → SCRAPE_QUEUED (atomic) → SCRAPED

### Enrichment Pipeline
- [ ] Enrichment Call 1 prompt template (factual extraction: summary, concepts, tags with hard taxonomy constraint, entry_type, challenge_hooks with truncation policy applied)
- [ ] Content truncation helper: per-source-type strategy, tiktoken-based 4,000 token ceiling
- [ ] OOV tag parser: validate Call 1 tags against taxonomy, strip and log OOV tags to oov_tags_log table
- [ ] Enrichment-batcher service: atomic claim for SCRAPED entries (→ ENRICHMENT_STAGE1_QUEUED), Anthropic Batch API submission (Call 1)
- [ ] Batch-poller service: polls Anthropic for Call 1 completion, 48hr timeout enforcement, parses results, POSTs to state-worker
- [ ] State transitions: SCRAPED → ENRICHMENT_STAGE1_QUEUED (atomic) → ENRICHMENT_STAGE1_SUBMITTED → ENRICHMENT_STAGE1_COMPLETE → ENRICHMENT_STAGE2_QUEUED
- [ ] Enrichment Call 2 prompt template (evaluative: relevance_score, relevance_reason, value_rationale; profile as system prompt with cache_control blocks)
- [ ] Enrichment-batcher Stage 4b: atomic claim poll (ENRICHMENT_STAGE2_QUEUED → ENRICHMENT_STAGE2_CLAIMED), Anthropic Batch API submission, POST ENRICHMENT_STAGE2_SUBMITTED signal to state-worker
- [ ] Batch-poller: polls Anthropic for Call 2 completion, 48hr timeout enforcement, parses results
- [ ] State transitions: ENRICHMENT_STAGE2_QUEUED → ENRICHMENT_STAGE2_CLAIMED (atomic) → ENRICHMENT_STAGE2_SUBMITTED → ENRICHMENT_STAGE2_COMPLETE → VECTOR_WRITE_QUEUED

### Indexing
- [ ] Embedding model setup: `sentence-transformers/all-MiniLM-L6-v2` in-process (384 dimensions, pinned — do not change without planned index rebuild)
- [ ] Vector-writer service: check-before-write idempotency for LanceDB and BM25; INSERT OR REPLACE for DuckDB; file lock acquisition before BM25 write; no atomic claim on VECTOR_WRITE_QUEUED poll (exemption documented in Section 6.2)
- [ ] BM25 index initialization, persistence, incremental update logic, file lock implementation (`filelock` library) — applies to both main index and challenge_hooks index; vector-writer acquires a single per-domain lock covering both indices in the same write operation; directory layout: `~/bishop_data/bm25/{domain}/main/` and `~/bishop_data/bm25/{domain}/challenge_hooks/`
- [ ] BM25 in-memory reload in query-api: configurable interval (default 5 min), applies to both main and challenge_hooks indices
- [ ] State transitions: VECTOR_WRITE_QUEUED → INDEXED
- [ ] **Embedding quality gate:** after first entries indexed, run 3–5 mid-spec test queries against challenge_hooks. If semantic results are not intuitively correct, upgrade to `nomic-embed-text` (768 dims) before backfill (see Section 8.4 and cold-start step 9).

### Query Layer
- [ ] query-api: FastAPI service, BM25 channel, dense channel (LanceDB), metadata filter (DuckDB opened **`read_only=True`** — required to avoid exclusive lock conflict with vector-writer), graceful cold-start initialization (empty index handling per Section 21 step 6)
- [ ] RRF fusion implementation
- [ ] Challenge hooks BM25 channel (separate per-domain index over challenge_hooks field; activated only on problem-shaped query detection per Section 16.3 heuristic; contributes as Channel 3 in 3-channel RRF fusion)
- [ ] Problem-shaped query classifier: prefix and content-signal heuristic as specified in Section 16.3
- [ ] Query endpoints: search, recent, batch detail, escalations
- [ ] CLI wrapper (Typer) over query-api endpoints

### UI
- [ ] ui service: HTMX frontend, batch summary list, batch detail, entry detail, search, DB explorer, escalation panel
- [ ] Reading status update interactions
- [ ] Manual retry / permanent-fail actions on escalation panel

### Validation and Backfill
- [ ] E2E smoke test on a single source, small batch
- [ ] Pre-filter quality validation (sample 20 decisions, assess recall/precision against manual judgment)
- [ ] Enrichment quality validation (sample 10 entries, assess challenge_hooks and value_rationale quality)
- [ ] Iterate NL profile if quality is off
- [ ] Enable all sources
- [ ] Configure and run backfill (chunk by chunk, monitor volume)

---

## 23. Deferred Items (Documented, Not Scheduled)

Each item below is explicitly deferred — not forgotten. Trigger conditions are noted where relevant.

| Item | Trigger / Condition |
|---|---|
| **Graph layer** (Kuzu, citation traversal via `references`/`cited_by` fields) | Schema is graph-ready from day one. Implement when flat retrieval shows gaps in "what builds on this" or "what does this cite" queries. |
| **Daily digest surface** | After backfill completes and system is in steady-state. The batch summary is sufficient during backfill. |
| **Cosine anchor migration** (Phase 2 bootstrapping cycle) | When sufficient labeled entries (pre_filter_rationale + decision=1) accumulate to trust cluster centroids. Assess subjectively from usage. |
| **Personal domain** (scrapers, NL profile, workflow config) | When professional domain is stable and the infrastructure is proven. Architecture is provisioned. |
| **Cross-domain query** | When both professional and personal domains are active. |
| **Reranker** (`ms-marco-MiniLM-L-6-v2`) | When RRF fusion results feel noisy in practice. Not needed at launch. |
| **Query expansion** (2-3 reformulations at query time) | When retrieval quality shows systematic vocabulary mismatch. Implement as a lightweight Haiku call at query time. |
| **Interest profile re-enrichment on version bump** | When the NL profile has changed enough that old relevance scores are misleading. Implement as a batch job that re-runs Call 2 for entries tagged with an older profile_version. |
| **Local 9B enrichment path** (Qwen 2.5 7B or Llama 3.1 8B via Ollama) | If volume spikes to thousands/day and API costs become meaningful. Currently ~$0.02-0.04/day — not warranted. |
| **Time-decayed retrieval weights** | When retrieval feedback shows systematic preference for recent content that isn't being reflected in results. Non-trivial to engineer correctly; don't generalize to all entry types. |
| **Reading history analytics** | When enough entries have been read to produce meaningful patterns. Dashboard feature. |
| **Redis queue upgrade** | If state-worker becomes a throughput bottleneck. SQLite WAL + asyncio is sufficient at current projected volume. |
| **Postgres state store upgrade** | If concurrent read/write patterns outgrow SQLite. Not anticipated at current scale. |
| **LessWrong GraphQL** | Verify API availability and stability before implementing. Lower priority than core sources. |

---

## 24. Rejected Items and Rationale

These options were evaluated and explicitly rejected. Documented to avoid relitigating.

| Item | Rejected In Favor Of | Rationale |
|---|---|---|
| **PyQt6 UI** | Localhost web (FastAPI + HTMX) | PyQt6 in Docker requires display forwarding (X11/Wayland) — platform-dependent, high setup friction. Web maps to a port mapping in Docker Compose — zero config. Knowledge base UIs benefit from web's filtering and browsing primitives. |
| **HuggingFace as primary paper source** | ArXiv as primary, HF as one adapter among many | HF daily papers feed is a downstream, community-curated layer on top of ArXiv. Lossy on coverage. ArXiv is the ground truth for ML preprints. HF wins for model/dataset/space metadata. |
| **Content hash for dedup** | Source ID (canonical per source) | Content hashing requires fetching full content before dedup — defeats the purpose of a lightweight manifest pass. Source IDs (`arxiv:2301.xxxxx`, `github:owner/repo`) are canonical, stable, and available from the lightweight manifest scrape. |
| **Semantic anchor embeddings as MVP pre-filter** | LLM binary pre-filter with versioned NL profile | Anchors require curated seed texts (bootstrapping problem), are opaque to update, produce no labeled data, and are harder to maintain than a versioned NL description. LLM binary is interpretable, trivially updatable, generates training data. Cosine anchors remain as a future upgrade path. |
| **Gemini Flash for pre-filter** | Anthropic Batch API (Haiku) for all LLM calls | Gemini Flash context caching minimum (1,024 tokens for implicit caching) exceeds the initial NL profile size (~300-500 tokens). The caching benefit was not load-bearing given the cost profile (cents/day regardless), but consolidating to a single provider (Anthropic) eliminates a second API key, a second batch-polling flow, and a second provider dependency. Growing the NL profile will unlock Anthropic prompt caching organically. |
| **Redis + Celery** | SQLite state store + asyncio workers | Overkill at projected volume. Redis adds operational overhead without benefit at tens-to-hundreds entries/day. SQLite WAL + asyncio is sufficient. Upgrade path documented. |
| **Single container** | Multi-container Docker Compose | Single container violates atomicity and modularity. A scraper crash takes down the query API. Independent scaling is impossible. Rebuilding one service requires rebuilding all. Multi-container is the correct architectural choice despite higher initial complexity. |
| **Global BM25 index** | Per-domain BM25 indices | A global index mixes professional (ML papers) and personal (philosophy, cinema) content. Cross-domain noise degrades precision for each domain's queries. Per-domain indices are clean, independent, and consistent with the domain routing architecture. |
| **GPT-4o-mini for enrichment** | Anthropic Batch API (Haiku) | At projected volume, cost difference is negligible ($0.015 vs $0.025/day). Haiku produces better structured output adherence and schema fidelity for technical content. Batch API adds 50% discount and async-by-design behavior that matches the pipeline model. |
| **Synchronous state-worker** | Async event loop (asyncio + aiosqlite) | Synchronous state-worker receiving concurrent POSTs from 8 services creates a request queue even at moderate volume. Asyncio event loop handles concurrent POSTs without blocking. Critical implementation requirement, not an optional optimization. |

---

## 25. Key Design Decision Log

A narrative record of the most consequential architectural choices.

**Why hybrid storage (LanceDB + DuckDB + SQLite) over a single store.**
No single store handles all three requirements cleanly: SQLite is the right state machine store (ACID, single-writer discipline, simple to operate) but has no vector support. LanceDB handles vectors and metadata in a single local file but is not designed for OLAP-style aggregations. DuckDB handles analytical queries and integrates natively with LanceDB's Lance format, providing a unified query interface for structured data. The three stores are complementary, not redundant. Each owns its access pattern.

**Why the manifest table is separate from the entries table.**
The manifest table is the dedup layer — it holds all discovered entries, including those rejected by the pre-filter. Mixing rejected and accepted entries in one table creates query complexity and semantic confusion. The manifest is the ledger of everything seen; the entries table is the knowledge base of everything indexed. The two-table design keeps these concerns clean and enables independent querying of both.

**Why two enrichment calls instead of one.**
See Section 13.2. The key point: factual extraction (Call 1) is source-agnostic and profile-independent — it extracts what the content says. Evaluative judgment (Call 2) requires profile context — it judges the content against the user's interests. Combining them risks the evaluative judgment being contaminated by noisy content rather than the structured summary. Separation also enables Call 1 to be re-run without invalidating Call 2 results, and vice versa.

**Why multi-container with single-writer discipline on SQLite rather than a distributed state store.**
At projected volume, the operational overhead of Redis or Postgres is not justified. SQLite WAL mode with a single-writer discipline provides sufficient throughput. The single-writer discipline is enforced architecturally (only `state-worker` writes SQLite) rather than by database-level locking, which gives explicit and inspectable control over concurrency. If volume grows beyond what this handles, the upgrade path (Postgres container) is a contained change.

**Why the NL profile is the pre-filter instrument rather than embedding similarity.**
The core tension was: embedding similarity is cheap at query time but expensive to set up and maintain correctly (requires curated seed texts, opaque to update, no training data generated). A versioned NL profile is trivially updatable (edit YAML, bump version), produces interpretable decisions with rationale, and generates a labeled dataset as a byproduct — that dataset is the foundation for eventually computing cosine anchors. The LLM binary pre-filter is not the permanent architecture; it is the MVP instrument that bootstraps the data needed for a better instrument.

**Why BM25 indices are per-domain rather than global.**
Cross-domain mixing (ML papers and philosophy texts) produces noise in both directions: ML queries surface philosophy results and vice versa. Per-domain indices maintain retrieval precision within each domain. Cross-domain query (unioning both indices) is a documented deferred capability, not a day-one requirement.

---

## 26. Phase 2 Feedback Log

Per spec-artifact §5.21. Records all Phase 2 Engineering Foundation feedback items, their Phase 1 classification, and their disposition.

### Cycle 1 (v1.3.0 → v1.4.0) — phase2_verdict: BLOCKED

| Item | Title (abbreviated) | Classification | Disposition |
|---|---|---|---|
| H1 | Entry schema non-nullable enrichment fields | Design Flaw | Absorbed — enrichment fields marked `\| None` (Section 7.2) |
| H2 | claude-haiku-4-5 model string unverified | Ambiguity | Absorbed — pinned to `claude-haiku-4-5-20251001`; verification gate added (Sections 12.1, 22) |
| H3 | Multi-step result write atomicity | Design Flaw | Absorbed — single SQLite transaction required; COMPLETE states defined as transient (Section 6.2) |
| S1 | DuckDB multi-process access mode | Detail Gap | Absorbed — `read_only=True` for query-api (Section 8.3) |
| S2 | Automatic retry trigger absent | Detail Gap | Absorbed — retry sweep added to state-worker background task; mapping table added (Section 6.2) |
| S3 | Batch-poller restart recovery | Detail Gap | Absorbed — startup scan specified; `GET /batches?status=...` endpoint added (Section 9.1) |
| S4 | BM25 persistence wrapper atomicity | Design Flaw | Absorbed — atomic write semantics required (temp → fsync → rename); Section 8.4 |
| S5 | Four write endpoint schemas deferred | Detail Gap | Absorbed — all four schemas specified (Section 9.1) |
| S6 | GET /entries/poll response schema | Detail Gap | Absorbed — returns full Entry model (Section 9.1) |
| S7 | ESCALATION_FLAGGED manual retry mapping | Detail Gap | Absorbed — mapping table added (Section 14.2) |
| S8 | Section 8.1 vs. REST poll contradiction | Ambiguity | Absorbed — claiming vs. non-claiming access model corrected (Sections 8.1, 9 service map) |
| G1–G7 | Documented gap items (7) | Detail Gaps | All absorbed — inline notes added throughout |
| M1–M4 | Minor / factual corrections (4) | Detail Gaps | All absorbed |

### Cycle 2 (v1.4.0 → v1.5.0) — phase2_verdict: CONDITIONAL

| Item | Title (abbreviated) | Classification | Disposition |
|---|---|---|---|
| N1 | Embedding text input unspecified | Design Flaw | Absorbed — pinned to `title + "\n" + summary + "\n" + " ".join(challenge_hooks)` (Sections 5.6, 8.4) |
| N2 | Retry sweep max_retries source | Detail Gap | Absorbed — state-worker uses own `RETRY_MAX_ATTEMPTS` constant (default 3), distinct scope from adapter per-source retries (Section 6.2) |
| N3 | Manual retry mapping incomplete (SUBMITTED states) | Detail Gap | Absorbed — state-worker normalizes SUBMITTED→FAILED in ErrorLog write path; table operates on _FAILED states only (Sections 6.2, 9.1) |
| M1 | aiosqlite transaction syntax ambiguous | Detail Gap | Absorbed — explicit `BEGIN`/`COMMIT`/`ROLLBACK` pattern specified (Section 6.2) |
| M2 | Pre-filter provenance null assertion | Detail Gap | Absorbed — assertion required at Stage 3 Entry creation (Section 5.3) |
| M3 | GET /entries/poll content_raw at VECTOR_WRITE_QUEUED | Detail Gap | Absorbed — content_raw excluded from VECTOR_WRITE_QUEUED poll response (Section 9.1) |

---

## Appendix A: Enrichment Prompt Templates (Sketch)

These are design-intent sketches. Exact prompt wording is an implementation concern and should be iterated during validation.

### Call 1 — Factual Extraction

```
System:
You are a technical content analyst. Extract structured metadata from the provided content.
Respond only with a valid JSON object matching the schema below. No preamble, no explanation.

Schema:
{
  "summary": "string, 200-300 characters, dense technical summary",
  "concepts": ["string", ...],  // 5-8 key technical concepts
  "tags": ["string", ...],      // ONLY use tags from this exact list: [taxonomy list]
                                 // Do not invent or use tags outside this list.
  "entry_type": "one of: paper|model|dataset|repo|article|spec|idea|benchmark|other",
  "challenge_hooks": ["string", ...]  // 2-4 problem framings this content addresses,
                                       // written as problems a practitioner would search for
}

Note on tags: any tags not in the provided list will be stripped by the parser and logged
for taxonomy review. Use only the listed values.

User:
Title: {title}
Content: {content_truncated}
// content_truncated: per-source-type truncation applied (4,000 token ceiling)
// papers: abstract + first 2,000 tokens of body
// repos: README header + top-level structure
// articles: first 2,500 tokens + last 500 tokens
```

### Call 2 — Evaluative / Profile-Aware

```
System:
{rendered_nl_profile}  ← cached prefix, hash-verified

Evaluate the relevance of the provided content to the profile above.
Respond only with a valid JSON object matching the schema below.

Schema:
{
  "relevance_score": float,  // 0.0-1.0
  "relevance_reason": "string, one sentence, why this is or is not relevant",
  "value_rationale": "string, 1-2 sentences, what specific value this provides to the profile's owner"
}

User:
Title: {title}
Summary: {summary_from_call1}
```

---

## Appendix B: Source Rate Limit and Schedule Reference

**Rate limits:**

| Source | Calls | Period | Backoff | Max Retries | Auth Required |
|---|---|---|---|---|---|
| ArXiv | 3 | 1s | Exponential | 4 | No |
| GitHub | 5000 | 1hr | Linear | 5 | Token (header) |
| Semantic Scholar | 100 | 1s | Exponential | 3 | Optional API key |
| HuggingFace | 50 | 1s | Exponential | 3 | Token for private |
| Papers With Code | 20 | 1s | Exponential | 3 | No |
| OpenReview | 10 | 1s | Exponential | 3 | No |
| LessWrong | 5 | 1s | Exponential | 3 | No |

**Default scraper schedules (G3).** These are starting defaults. Adjust based on source freshness needs and observed rate-limit pressure.

| Source | Default Schedule | Rationale |
|---|---|---|
| ArXiv | Every 6 hours | High-volume source; new papers submitted throughout the day; 6-hour cadence captures daily output without excessive polling |
| GitHub | Every 12 hours | Trending repos move slower than paper submissions; 12-hour cadence is sufficient |
| Semantic Scholar | Every 24 hours | Citation graph data changes slowly; daily is sufficient |
| HuggingFace | Every 6 hours | Active model/dataset publishing cadence; mirrors ArXiv |
| Papers With Code | Every 24 hours | SOTA benchmark updates are infrequent; daily sufficient |
| OpenReview | Every 24 hours | Submission windows are periodic; daily catch-up adequate |
| LessWrong | Every 24 hours | Long-form content, low publish frequency |

---

## Appendix C: Error Classification Reference

| Condition | Classification | State Transition |
|---|---|---|
| HTTP 429 | Retriable | Retry with backoff |
| HTTP 500, 502, 503, 504 | Retriable | Retry with backoff |
| TimeoutError, ConnectionError | Retriable | Retry with backoff |
| httpx.TimeoutException, NetworkError | Retriable | Retry with backoff |
| HTTP 401, 403 | Escalatable | → ESCALATION_FLAGGED |
| HTTP 404 | Escalatable | → ESCALATION_FLAGGED |
| HTTP 422 | Escalatable | → ESCALATION_FLAGGED |
| HTTP 400 | Fatal | → PERMANENTLY_FAILED |
| HTTP 410 | Fatal | → PERMANENTLY_FAILED |
| Retriable + retry_count >= max_retries | Escalatable | → ESCALATION_FLAGGED |

---

*End of document. Version 1.5.0. Phase 2 cycle 2 review incorporated June 2026.*
*Next artifact: implementation workshop — repository structure, Docker Compose, state-worker scaffold.*
