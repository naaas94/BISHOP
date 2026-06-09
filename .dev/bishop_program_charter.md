# BISHOP Program Charter

**Version:** 0.1.0
**Author:** Alejandro Garay Frontini
**Date:** 2026-06-09
**Status:** Active

---

## 1. Program Identity

### Mission

Bishop is a local-first knowledge intelligence pipeline that discovers, filters, enriches, indexes, and serves AI/ML/engineering content from multiple sources. The system operates in two layers: an asynchronous ingest pipeline (scrape → pre-filter → enrich → index) and an interactive read path (hybrid BM25 + dense semantic + metadata query). The charter governs the sequential construction of that pipeline as a series of vertical milestone slices, each ending in a runnable checkpoint, so that every intermediate state of the program is coherent and testable.

Derived from `bishop_spec_0_6.md` §1 (L39–53) and §2 (L55–79).

### Normative Artifact

| Field | Value |
|-------|-------|
| **Path** | `bishop_spec_0_6.md` |
| **Version** | 1.5.0 |
| **Status** | `phase1_approved`; Phase 2 cycle 3 re-review pending (`phase2_verdict: CONDITIONAL`) |
| **Role** | Architecture spec · design rationale · implementation checklist · deferred/rejected registry |
| **Orch rule** | Must be a tracked repo path before any M-plan §2 cites it as binding |

The spec is the source of truth. The charter is the index. No M-plan summarizes, duplicates, or supersedes spec prose — it references by section number and line range.

**Phase 2 note.** `phase2_verdict: CONDITIONAL` (cycle 3 re-review scoped to N1–N3 resolution). This does **not** block M0 or M1. N1–N3 and M1–M3 feedback items are fully absorbed in v1.5.0 per §26 (L1590–1623).

---

## 2. Operating Model

### Per-Milestone Workflow

```
┌─────────────────────────────────────────────────────────────────┐
│  For each milestone M<n>:                                        │
│                                                                  │
│  1. PRE-PLAN EXPLORATION                                         │
│     Input:  charter §M<n> spec refs + prior M<n-1> §8 handoff   │
│             + architecture folder at HEAD SHA                    │
│     Output: .dev/plans/<m-plan>/context-map.md                  │
│                                                                  │
│  2. ORCH PLANNING                                                │
│     Input:  context-map.md + charter §M<n>                      │
│     Output: .dev/plans/<m-plan>/plan.md                         │
│             .dev/plans/<m-plan>/packets/T<n>.md  (4–7 packets)  │
│                                                                  │
│  3. EXECUTOR SUBTASKS                                            │
│     Each packet: code + tests + tiered changelog                 │
│     Output: committed diffs + .dev/decision-logs/<m-plan>/      │
│                                                                  │
│  4. AUDITOR REVIEW                                               │
│     Input:  all packets + diffs + contracts                      │
│     Output: §8 handoff (clean tree, SHA, verification result)   │
│                                                                  │
│  5. POST-MILESTONE HOUSEKEEPING                                  │
│     See §7 checklist                                             │
└─────────────────────────────────────────────────────────────────┘
```

**Rule.** The next milestone's pre-plan **must** consume the prior milestone's §8 auditor handoff plus the `.dev/architecture/` folder at the handoff SHA. Pre-plan must not begin without both.

### Artifact Conventions

| Artifact | Path |
|----------|------|
| Context map | `.dev/plans/<m-plan-name>/context-map.md` |
| Orch plan | `.dev/plans/<m-plan-name>/plan.md` |
| Executor packets | `.dev/plans/<m-plan-name>/packets/T<n>.md` |
| Architecture folder | `.dev/architecture/` (project-architecture skill output) |
| Decision logs | `.dev/decision-logs/<m-plan-name>/` |
| Milestone changelog | `.dev/changelogs/M<n>-<name>.md` |
| Auditor §8 handoff | `.dev/plans/<m-plan-name>/handoff.md` |

M-plan name convention: `m<n>-<slug>`, e.g., `m0-workshop`, `m1-state-kernel`.

---

## 3. Milestone Registry

---

### M0 — Implementation Workshop

**Intent.** Stand up the Docker Compose skeleton with all 9 services defined, volumes mounted, internal network configured, and `state-worker /health` passing. No application logic — only the structural skeleton that all subsequent milestones build on.

**Runnable checkpoint.** `docker compose up` exits healthy. All 9 service containers start. `state-worker` responds `200` on `GET /health`. `query-api` and `ui` are reachable on their host ports. All volume mount directories exist. Docker internal network resolves service hostnames. No application code beyond health endpoint and process entry points.

**§22 mapping.** Foundation: "Repository structure and Docker Compose skeleton" and "`state-worker` must expose `GET /health`" (L1450–1451).

**Services touched.** All 9 services: `scraper`, `state-worker`, `pre-filter-worker`, `content-scraper`, `enrichment-batcher`, `batch-poller`, `vector-writer`, `query-api`, `ui`.

**Contract surfaces extended.** Volume layout (§8.5): `~/bishop_data/sqlite`, `lancedb`, `duckdb`, `bm25`, `profiles`, `logs`. Service names and internal hostnames. Host port assignments for `query-api` and `ui`. Docker Compose `depends_on` health check chain anchored on `state-worker`.

**Entry gate.** Spec committed and tracked in repo (`bishop_spec_0_6.md` present at HEAD). Program gate G0.

**Exit gate.** G1: `docker compose up` → all containers running → `curl http://localhost:<state-worker-port>/health` returns `200`. Volume directories exist and are writable. No container restart loops.

**Parallelism.** All Dockerfiles and service stubs may be authored in parallel. Compose file itself is sequential (single file). Volume and network config: sequential, in compose file.

**Explicit non-goals.** No application logic. No Alembic migrations. No database initialization. No REST endpoints beyond `/health`. No source adapters. Defer all §23 and §24 items.

---

#### M0 Spec Reference Block

**Primary (read):**
- `bishop_spec_0_6.md` L597–612 (§9 service table — names, responsibilities, write/read targets)
- L580–595 (§8.5 volume mounts — exact paths for Compose)
- L1449–1451 (§22 Foundation: compose skeleton + health check)

**Adjacent (read, do not implement):**
- L39–53 (§1 system overview — context)
- L55–79 (§2 design principles — constraints)
- L105–160 (§4 architecture diagram — understand inter-service flow)
- L16–37 (§0 document meta — status, verdict)

**Gates:**
- Entry: G0 — spec committed and tracked in repo
- Exit: G1 — `docker compose up` healthy; all 9 containers running; `state-worker /health` returns 200

**Pre-plan stub:** See §6.

---

### M1 — State Kernel

**Intent.** Implement the complete `state-worker` service: Alembic migrations, full SQLite schema, all enums and Pydantic models, all state transition logic, atomic poll-and-claim endpoints, lock-state recovery sweep, retry sweep, multi-step write transactions, and all REST endpoints. After M1, the state machine is the contract anchor for every subsequent milestone.

**Runnable checkpoint.** `state-worker` container starts, runs Alembic migrations synchronously, exposes all REST endpoints defined in §9.1. Calling `POST /manifest/batch` with a sample payload creates rows in the manifest table with `processing_state = DISCOVERED`. Calling `GET /manifest/poll?state=DISCOVERED` atomically transitions entries to `RELEVANCE_QUEUED` and returns them. `GET /batches?status=submitted,processing` returns empty list. Background sweeps are running (observable via logs). Schema matches §7 exactly.

**§22 mapping.** Foundation: Alembic migration setup, state-worker service (full), enum definitions, Pydantic models (L1452–1454).

**Services touched.** `state-worker` exclusively.

**Contract surfaces extended.**
- `ProcessingState` enum — full definition (§6.1)
- `ManifestEntry`, `Entry`, `BatchRecord`, `ErrorLog`, `OovTagsLog`, `ScraperState` Pydantic models (§7)
- All §9.1 REST endpoints (L613–760)
- Atomic claim semantics: `DISCOVERED → RELEVANCE_QUEUED`, `RELEVANCE_PASSED → SCRAPE_QUEUED`, `SCRAPED → ENRICHMENT_STAGE1_QUEUED`, `ENRICHMENT_STAGE2_QUEUED → ENRICHMENT_STAGE2_CLAIMED`
- `VECTOR_WRITE_QUEUED` explicit poll-no-claim exemption
- Lock-state recovery sweep: `RELEVANCE_QUEUED → DISCOVERED`, `SCRAPE_QUEUED → RELEVANCE_PASSED`, `ENRICHMENT_STAGE1_QUEUED → SCRAPED`, `ENRICHMENT_STAGE2_CLAIMED → ENRICHMENT_STAGE2_QUEUED`
- Retry sweep: `_FAILED` → work-ready mapping per §6.2
- Multi-step write atomicity: `BEGIN` / `COMMIT` / `ROLLBACK` aiosqlite pattern (H3)
- SUBMITTED → FAILED normalization in ErrorLog write path (N3)
- `content_raw` exclusion at `VECTOR_WRITE_QUEUED` poll (M3)

**Entry gate.** G1 (M0 checkpoint passed — `docker compose up` healthy).

**Exit gate.** G2: contract test suite passes for all §9.1 endpoints. Specifically: `POST /manifest/batch` idempotency; `GET /manifest/poll` atomic claim (double-poll returns empty second time); `POST /entries/enrichment-stage1-results` transaction atomicity; background sweep resets stuck `RELEVANCE_QUEUED` entries. Alembic migration runs clean from empty DB.

**Parallelism.** Schema migrations and Pydantic model definitions can be authored in parallel. State transition logic must be sequential (models must exist first). REST endpoints may be developed per-group in parallel once core transition logic is stable. Sweep task is independent and can be developed after endpoint skeleton is in place.

**Explicit non-goals.** No scraper. No pre-filter-worker. No batch-poller. No enrichment. No vector-writer. No query-api logic. Defer §23, §24.

---

#### M1 Spec Reference Block

**Primary (read):**
- `bishop_spec_0_6.md` L259–354 (§6 state machine — complete enum, transition rules, atomic claim, sweep, retry, atomicity H3)
- L355–505 (§7 schema — all models)
- L509–523 (§8.1 SQLite — WAL, migration pattern, aiosqlite startup)
- L613–760 (§9.1 REST API — all endpoints, request/response schemas)
- L1452–1454 (§22 Foundation: Alembic, state-worker, enums)

**Adjacent (read, do not implement):**
- L55–79 (§2 design principles — single-writer, idempotency)
- L1104–1146 (§14 error/escalation — failure classification, `ESCALATION_FLAGGED` routing)
- L1369–1422 (§20 enums/tags — `SourceEnum`, `DomainEnum`, `BatchTypeEnum`, `BatchStatusEnum`, `EntryTypeEnum`, `ReadingStatusEnum`, `OovReviewStatusEnum`)

**Gates:**
- Entry: G1 — M0 checkpoint; `state-worker /health` responds
- Exit: G2 — all §9.1 contract tests pass; atomic claim double-poll verified; sweep task verified via logs; Alembic migration clean from empty DB

**Pre-plan stub:** See §6.

---

### M2 — Discovery Slice

**Intent.** Implement the `scraper` service with `SourceAdapter` ABC, adapter registry, failure envelope, scraper loop, and the ArXiv adapter only. Entries from ArXiv reach `DISCOVERED` state in the manifest table, with `scraper_state` persisted per source.

**Runnable checkpoint.** `scraper` container starts. Scraper loop calls `ArxivAdapter.fetch_manifest(since=last_run)`, reads `scraper_state` from `GET /scraper-state/arxiv`, POSTs batch to `POST /manifest/batch`, updates `POST /scraper-state/arxiv`. Manifest table contains ArXiv entries at `DISCOVERED`. No other adapter implemented.

**§22 mapping.** Source Adapters: abstract base, registry, failure envelope, ArXivAdapter (L1456–1460).

**Services touched.** `scraper`.

**Contract surfaces extended.**
- `SourceAdapter` ABC: `fetch_manifest`, `fetch_content`, `make_source_id` signatures (§10.1)
- `ADAPTER_REGISTRY` — single entry at M2: ArXiv
- Scraper loop per-adapter `last_run` reads via `GET /scraper-state/{source}` (§10.3)
- `POST /scraper-state/{source}` called after successful manifest batch
- Failure envelope: per-source `RateLimit` config, retry classification per §6.3/§15

**Entry gate.** G2 (M1 `state-worker` contract tests pass — manifest and scraper-state endpoints functional).

**Exit gate.** Observable: ArXiv entries appear at `DISCOVERED` in manifest table after scraper run. `scraper_state.last_successful_run_at` updated. Failure envelope absorbs simulated HTTP 429 without crashing scraper. No duplicate source_ids on re-run (idempotency gate).

**Parallelism.** `SourceAdapter` ABC and registry can be developed first. Failure envelope and rate-limiting infrastructure can be built in parallel with the ArXiv adapter. Scraper loop (scheduler + main loop) is sequential after both adapter and failure envelope exist.

**Explicit non-goals.** HuggingFaceAdapter, PapersWithCodeAdapter, SemanticScholarAdapter, GitHubAdapter, OpenReviewAdapter, LessWrongAdapter — all deferred to M8. Domain routing §19.2–19.3 deferred. Personal domain §3.2 deferred. Appendix C adapters deferred. `fetch_content` on adapters not needed until M4.

---

#### M2 Spec Reference Block

**Primary (read):**
- `bishop_spec_0_6.md` L762–873 (§10 source adapter pattern — ABC, registry, loop pseudocode §10.3)
- L81–103 (§3 source stack — ArXiv as primary; §3.1 details)
- L1147–1182 (§15 rate limiting — per-source config, `RateLimit` class, retry logic)
- L1456–1460 (§22 Source Adapters: ABC, registry, failure envelope, ArXiv)

**Adjacent (read, do not implement):**
- L164–172 (§5.1 Stage 1 discovery flow)
- L494–505 (§7.6 `ScraperState` schema)
- L613–760 (§9.1 — `POST /manifest/batch`, `GET/POST /scraper-state/{source}` already landed in M1)
- L1341–1368 (§19 domain routing §19.1 only — understand `domain` field; defer §19.2–19.3)
- L1682–1709 (Appendix B — scraper schedule defaults; reference only)
- L1710–1729 (Appendix C — adjacent adapter patterns; reference only, do not implement)

**Gates:**
- Entry: G2 — M1 state-worker contract tests pass; `/manifest/batch` and `/scraper-state` endpoints verified
- Exit: ArXiv entries at `DISCOVERED` in manifest after scraper run; `scraper_state` updated; idempotency confirmed on re-run; failure envelope absorbs simulated 429

**Pre-plan stub:** See §6.

---

### M3 — Pre-filter Slice

**Intent.** Implement the NL profile system (v1.0.0), profile renderer, `pre-filter-worker`, and `batch-poller` v1 (pre-filter batch types only). Entries move from `DISCOVERED` through `RELEVANCE_QUEUED` to `RELEVANCE_PASSED` or `RELEVANCE_REJECTED`. The Anthropic model string is verified before any LLM call is made.

**Runnable checkpoint.** `pre-filter-worker` polls `GET /manifest/poll?state=DISCOVERED`, assembles batches of ≤50, submits to Anthropic Batch API (`claude-haiku-4-5-20251001`). `batch-poller` polls Anthropic, posts decisions to `POST /manifest/pre-filter-results`. State-worker transitions entries to `RELEVANCE_PASSED` or `RELEVANCE_REJECTED`. `BatchRecord` created with `batch_type = pre_filter`, `profile_render_hash` populated. `batch-poller` performs startup scan on init. A 20-entry sample batch completes end-to-end with decisions visible in the manifest table.

**§22 mapping.** Pre-filter Layer (L1468–1475): model string verification gate, NL profile YAML, canonical_hash, profile renderer, pre-filter worker, batch-poller v1, state transitions.

**Services touched.** `pre-filter-worker`, `batch-poller` (v1).

**Contract surfaces extended.**
- `NL profile v1.0.0` YAML at `config/profiles/professional_v1.0.0.yaml` with `canonical_hash` computed and committed
- Profile renderer: YAML → canonical prompt string, `json.dumps(dict, sort_keys=True)` → SHA-256
- `BatchRecord.batch_type = pre_filter`; `profile_render_hash` field populated
- `batch-poller` startup scan: `GET /batches?status=submitted,processing` → re-register in-flight batches
- 48-hour timeout enforcement for `batch_timed_out` transition

**Entry gate.** G2 (M1 state-worker contract tests pass). G3: Anthropic model string verified — one direct test call to `claude-haiku-4-5-20251001` via Anthropic Messages API returns non-400 before any pipeline work proceeds.

**Exit gate.** G3 verified (model string confirmed). 20-entry sample batch: decisions written to manifest, `RELEVANCE_PASSED` and `RELEVANCE_REJECTED` entries present. `BatchRecord` created with correct `batch_type` and `profile_render_hash`. Startup scan re-registers in-flight batches on poller restart (verified via kill-restart test).

**Parallelism.** NL profile YAML authoring and `canonical_hash` computation can proceed in parallel with profile renderer development. Pre-filter worker and batch-poller are otherwise sequential (worker submits; poller polls). Model string verification must complete before either submits to Anthropic.

**Explicit non-goals.** Enrichment batch types in batch-poller deferred to M5. `batch-poller` startup scan for enrichment batches deferred to M5. Content scraping, enrichment, vector indexing. All §23 deferrals.

---

#### M3 Spec Reference Block

**Primary (read):**
- `bishop_spec_0_6.md` L173–185 (§5.2 Stage 2 pre-filter flow)
- L874–987 (§11 NL profile system — design rationale, YAML structure, versioning, `canonical_hash`)
- L988–1037 (§12 pre-filter layer — worker logic, batch assembly, hash verification)
- L1468–1475 (§22 Pre-filter Layer — model string gate, profile, renderer, worker, batch-poller v1)
- L1469 (model string gate: `claude-haiku-4-5-20251001`)

**Adjacent (read, do not implement):**
- L259–324 (§6.2 atomic claims, sweeps — already landed in M1; read to understand poll contract)
- L437–459 (§7.3 `BatchRecord` schema)
- L613–760 (§9.1 — `/manifest/poll`, `/manifest/pre-filter-results`, `/batches?status=...` already landed in M1)
- L238–258 (§5.7 batch record lifecycle)
- L597–612 (§9 service table row for `batch-poller`)

**Gates:**
- Entry: G2 (M1 contract tests); G3 (model string verified — blocks all Anthropic work)
- Exit: 20-entry sample batch → `RELEVANCE_PASSED`/`RELEVANCE_REJECTED`; `BatchRecord` with correct fields; startup scan verified; model string confirmed via direct API call

**Pre-plan stub:** See §6.

---

### M4 — Content Slice

**Intent.** Implement the `content-scraper` service and the `ArxivAdapter.fetch_content` method. Entries move from `RELEVANCE_PASSED` through `SCRAPE_QUEUED` to `SCRAPED`, with `content_raw` populated. The `Entry` record is created at state-worker with pre-filter provenance null assertion enforced.

**Runnable checkpoint.** `content-scraper` polls `GET /manifest/poll?state=RELEVANCE_PASSED`, calls `ArxivAdapter.fetch_content(entry)`, POSTs content to `POST /entries/content`. State-worker creates `Entry` record (identity + `content_raw`, enrichment fields null, pre-filter provenance asserted non-null), transitions manifest entry to `SCRAPED`. Observable: `entries` table contains rows at `SCRAPED` with non-null `content_raw`.

**§22 mapping.** Content Scraping (L1477–1479): content-scraper service, state transitions.

**Services touched.** `content-scraper`. `scraper` (ArXiv adapter receives `fetch_content` implementation).

**Contract surfaces extended.**
- `SourceAdapter.fetch_content` for ArXiv: returns full content string
- `POST /entries/content` interaction: pre-filter provenance null assertion enforced at state-worker (§5.3 M2 note)
- `Entry` record creation: all enrichment fields `None` at creation; provenance fields asserted non-None

**Entry gate.** G4 (first-source e2e smoke): M3 checkpoint — at least one `RELEVANCE_PASSED` entry in manifest (pre-filter ran successfully on ArXiv entries).

**Exit gate.** `entries` table contains rows at `SCRAPED` with `content_raw` populated. State-worker pre-filter provenance assertion fires cleanly (no null provenance on any `SCRAPED` entry). `SCRAPE_FAILED` path tested: simulated `fetch_content` failure produces `ErrorLog` entry and manifests as `SCRAPE_FAILED` with correct `is_retriable` flag.

**Parallelism.** `fetch_content` for ArXiv can be developed independently of content-scraper service scaffolding. State-worker `POST /entries/content` endpoint logic (already partially specified in M1) needs final confirmation of provenance assertion; this is a state-worker amendment, not a new service.

**Explicit non-goals.** `fetch_content` for non-ArXiv adapters deferred to M8. Enrichment. Vector indexing.

---

#### M4 Spec Reference Block

**Primary (read):**
- `bishop_spec_0_6.md` L186–193 (§5.3 Stage 3 content scrape — atomic claim, `fetch_content`, Entry creation, provenance assertion M2)
- L762–873 (§10 — `fetch_content` abstract method §10.1, ArXiv implementation §10.2)
- L1477–1479 (§22 Content Scraping)

**Adjacent (read, do not implement):**
- L385–435 (§7.2 `Entry` schema — progressive population model, SQLite list[str] storage M2)
- L613–660 (§9.1 — `POST /entries/content` request/response schema already in M1)
- L326–344 (§6.3 failure classification — `SCRAPE_FAILED` routing)
- L81–103 (§3.1 ArXiv — understand what `fetch_content` must return)

**Gates:**
- Entry: G4 — at least one `RELEVANCE_PASSED` entry in manifest; M3 pre-filter verified e2e
- Exit: `entries` table rows at `SCRAPED` with non-null `content_raw`; provenance assertion clean; `SCRAPE_FAILED` path exercised

**Pre-plan stub:** See §6.

---

### M5 — Enrichment Slice

**Intent.** Implement `enrichment-batcher` (dual asyncio tasks for Stage 4a and Stage 4b), enrichment prompt templates, content truncation helper, OOV tag parser, and `batch-poller` v2 (all batch types + startup scan for enrichment types). Entries move from `SCRAPED` through both enrichment stages to `VECTOR_WRITE_QUEUED`.

**Runnable checkpoint.** `enrichment-batcher` Task A polls `SCRAPED` entries, submits Call 1 batch. `batch-poller` polls Anthropic, posts results to `POST /entries/enrichment-stage1-results`. State-worker transitions `SCRAPED → ENRICHMENT_STAGE1_QUEUED → ENRICHMENT_STAGE1_SUBMITTED → ENRICHMENT_STAGE1_COMPLETE → ENRICHMENT_STAGE2_QUEUED` (atomic multi-step). Task B polls `ENRICHMENT_STAGE2_QUEUED`, submits Call 2. Batch-poller posts results to `POST /entries/enrichment-stage2-results`. State-worker transitions to `VECTOR_WRITE_QUEUED`. Observable: entries at `VECTOR_WRITE_QUEUED` with all enrichment fields populated; OOV tags logged in `oov_tags_log`; `BatchRecord` rows for both `enrichment_stage1` and `enrichment_stage2` types.

**§22 mapping.** Enrichment Pipeline (L1481–1491): Call 1 prompt, truncation helper, OOV parser, enrichment-batcher, batch-poller v2, state transitions.

**Services touched.** `enrichment-batcher`, `batch-poller` (v2 — extended to cover enrichment batch types).

**Contract surfaces extended.**
- Call 1 prompt template: `summary`, `concepts`, `tags` (taxonomy-constrained), `entry_type`, `challenge_hooks`
- Call 2 prompt template: `relevance_score`, `relevance_reason`, `value_rationale`; NL profile as system prompt with `cache_control` blocks
- Content truncation helper: per-source-type strategy, tiktoken-based 4,000 token ceiling (§13.1)
- OOV tag parser: validates against taxonomy, logs to `oov_tags_log` table
- `ENRICHMENT_STAGE2_CLAIMED` as lock state for Stage 4b atomic claim
- `batch-poller` extended: polls all three batch types; startup scan re-registers enrichment in-flight batches
- 48-hour timeout for both enrichment stages (`batch_timed_out` → `_FAILED`)
- SUBMITTED → FAILED normalization in ErrorLog (N3) — already landed in M1; must be exercised here

**Entry gate.** G3 (model string verified — blocks all Anthropic enrichment work). M4 checkpoint — entries at `SCRAPED` with `content_raw` populated.

**Exit gate.** 5-entry sample set proceeds from `SCRAPED` to `VECTOR_WRITE_QUEUED` with all enrichment fields populated. `oov_tags_log` table receives entries. `BatchRecord` rows exist for both stage types. `ENRICHMENT_STAGE2_CLAIMED` lock state verified (double-poll returns empty second time). Startup scan re-registers enrichment in-flight batches on poller restart.

**Parallelism.** Call 1 and Call 2 prompt templates can be drafted in parallel. Truncation helper and OOV parser are independent utilities. Task A and Task B in `enrichment-batcher` are implemented as separate asyncio tasks — Task B depends on Task A's output type but can be coded in parallel. Batch-poller v2 extension is sequential after batch-poller v1 (M3) is understood.

**Explicit non-goals.** Vector writing, LanceDB, DuckDB, BM25 indexing. Query path. UI. Backfill. All §23 deferrals. Cross-domain enrichment (personal domain deferred per §3.2).

---

#### M5 Spec Reference Block

**Primary (read):**
- `bishop_spec_0_6.md` L195–215 (§5.4–5.5 Stage 4a and 4b enrichment flows)
- L1038–1103 (§13 enrichment pipeline — prompt design §13.2, truncation §13.1, challenge_hooks §13.3)
- L238–258 (§5.7 batch lifecycle — `batch_timed_out`, partial batch behavior)
- L1481–1491 (§22 Enrichment Pipeline)
- L1625–1681 (Appendix A — enrichment prompt templates, design-intent sketches)

**Adjacent (read, do not implement):**
- L437–459 (§7.3 `BatchRecord` — `batch_type` enum values for enrichment stages)
- L479–492 (§7.5 `OovTagsLog` schema)
- L613–760 (§9.1 — enrichment result POST endpoint schemas already in M1)
- L1369–1422 (§20 enums/tags — tag taxonomy, `EntryTypeEnum`; constrain Call 1 output)
- L259–324 (§6.2 — `ENRICHMENT_STAGE2_CLAIMED` atomic claim, H3 multi-step atomicity; already in M1)

**Gates:**
- Entry: G3 (model string verified); M4 checkpoint (entries at `SCRAPED`)
- Exit: 5-entry sample set → `VECTOR_WRITE_QUEUED` with all enrichment fields populated; OOV logs present; startup scan re-registers enrichment batches on restart

**Pre-plan stub:** See §6.

---

### M6 — Indexing Slice

**Intent.** Implement `vector-writer`: embedding generation, LanceDB write with idempotency check, BM25 index (main + challenge_hooks) with file lock and atomic persistence, DuckDB mirror upsert, and `POST /entries/indexed` signaling. Entries reach `INDEXED` (terminal success). Embedding quality gate must pass before M7 proceeds.

**Runnable checkpoint.** `vector-writer` polls `GET /entries/poll?state=VECTOR_WRITE_QUEUED` (no atomic claim), embeds entries using `sentence-transformers/all-MiniLM-L6-v2` (384 dims), writes to LanceDB (after check), updates both BM25 indices with file lock, upserts to DuckDB, posts to `POST /entries/indexed`. State-worker transitions to `INDEXED`. Observable: `INDEXED` entries in DB; LanceDB table contains vectors; BM25 files on host volume; DuckDB rows present.

**§22 mapping.** Indexing (L1493–1499): embedding model setup, vector-writer, BM25 initialization/persistence/locking, DuckDB, state transitions, embedding quality gate.

**Services touched.** `vector-writer`.

**Contract surfaces extended.**
- Embedding model pinned: `sentence-transformers/all-MiniLM-L6-v2`, 384 dims
- Embedding text pinned (N1): `title + "\n" + summary + "\n" + " ".join(challenge_hooks)`
- LanceDB check-before-write on `source_id`
- BM25 main index: per-domain, `~/bishop_data/bm25/{domain}/main/`
- BM25 challenge_hooks index: per-domain, `~/bishop_data/bm25/{domain}/challenge_hooks/`
- File lock: single per-domain lock covering both BM25 indices in same write operation
- Atomic BM25 persistence: temp file → `fsync` → `os.replace` (S4)
- DuckDB `INSERT OR REPLACE` (read-write mode in vector-writer)
- `POST /entries/indexed` → state-worker transitions to `INDEXED`

**Entry gate.** M5 checkpoint — entries at `VECTOR_WRITE_QUEUED` with all enrichment fields populated.

**Exit gate.** G5 (embedding quality gate): 3–5 test queries against `challenge_hooks` return intuitively correct semantic results. If quality gate fails, upgrade to `nomic-embed-text` (768 dims) before M7. `INDEXED` entries present in all three stores. BM25 file lock contention tested (simulated concurrent write). DuckDB opened `read_only=True` from a separate process without lock conflict.

**Parallelism.** Embedding + LanceDB write, BM25 indexing, and DuckDB mirror can be developed in parallel as separate functions within the vector-writer service. File lock acquisition is shared and must be integrated carefully. Atomic BM25 persistence wrapper is independent utility.

**Explicit non-goals.** Query API. UI. Backfill. BM25 reload in `query-api` (deferred to M7). DuckDB analytics queries (deferred to M7). LanceDB cosine anchor migration (§12.3 Phase 2+ deferred per §23). Reranker (§23 deferred).

---

#### M6 Spec Reference Block

**Primary (read):**
- `bishop_spec_0_6.md` L217–237 (§5.6 Stage 5 vector indexing — idempotency contract, embedding text N1, INDEXED terminal state)
- L525–535 (§8.2 LanceDB — role, format, DuckDB integration nuance)
- L537–541 (§8.3 DuckDB — `read_only=True` requirement, `INSERT OR REPLACE`)
- L543–578 (§8.4 BM25 — single-instance write discipline, atomic persistence S4, challenge_hooks index, directory naming, embedding model pin, quality caveat, quality gate)
- L1493–1499 (§22 Indexing)

**Adjacent (read, do not implement):**
- L580–595 (§8.5 volumes — mount paths for LanceDB, DuckDB, BM25)
- L700–707 (§9.1 `POST /entries/indexed` — already in M1)
- L259–298 (§6.2 — `VECTOR_WRITE_QUEUED` exemption note, `INDEXED` terminal state guarantee; already in M1)
- L1437 (§21 step 9–10 — embedding quality gate procedure)

**Gates:**
- Entry: M5 checkpoint (entries at `VECTOR_WRITE_QUEUED`)
- Exit: G5 — 3–5 quality test queries pass; `INDEXED` entries in all three stores; file lock test clean; DuckDB concurrent access verified

**Pre-plan stub:** See §6.

---

### M7 — Read Path

**Intent.** Implement `query-api` (RRF fusion, challenge_hooks channel, graceful cold-start), Typer CLI wrapper, and minimal UI (batch summary list and search). The read path is queryable from the CLI and browser against `INDEXED` entries.

**Runnable checkpoint.** `query-api` starts with graceful cold-start (empty stores return empty results, not crashes). `GET /search?q=<query>` returns RRF-fused results from BM25 + dense channels. Problem-shaped queries activate Channel 3 (challenge_hooks BM25). CLI `bishop search "hybrid retrieval for sparse graphs"` returns results. UI batch summary list shows completed batches. UI search bar executes queries.

**§22 mapping.** Query Layer (L1501–1507): query-api, RRF, challenge_hooks channel, problem-shaped classifier, endpoints, CLI. UI (subset, L1509–1512): batch summary, search, entry detail.

**Services touched.** `query-api`, `ui`.

**Contract surfaces extended.**
- RRF formula: `Σ 1/(k + rank(d, list_i))`, k=60; 2-channel standard; 3-channel problem-shaped
- Problem-shaped query classifier: prefix and content-signal heuristic (§16.3)
- BM25 reload: copy-on-write pattern, configurable interval (default 5 min), covers both main and challenge_hooks indices (G5 reload atomicity)
- DuckDB opened `read_only=True` in query-api (S1 — already specified in M1; must be implemented here)
- Cold-start contract (G7): empty BM25 → empty in-memory index; empty LanceDB table → empty results; empty DuckDB tables → empty results; all log `WARN`, none crash
- Query endpoints: `search`, `recent`, `batch detail`, `escalations`
- CLI: Typer wrapper over query-api endpoints

**Entry gate.** G5 passed (embedding quality gate) and G6 verified (pre-filter + enrichment quality sampling on a 20-entry sample set). At least one round-trip e2e smoke run completed (M1→M2→M3→M4→M5→M6) producing `INDEXED` entries.

**Exit gate.** G4 (§21 steps 7–8): entries flow from scraper through to `INDEXED` in a single e2e run. CLI search returns results. UI loads batch list. Problem-shaped query produces different (Channel 3 active) results than standard query. Cold-start: empty-store startup does not crash.

**Parallelism.** BM25 retrieval, dense retrieval, and DuckDB metadata filter can be developed in parallel as separate retrieval functions. RRF fusion is sequential (depends on all three). Problem-shaped classifier is an independent utility. CLI and UI can be developed in parallel with the query-api backend.

**Explicit non-goals.** Full UI (escalation panel manual retry/permanent-fail, reading status updates — deferred to M8). Reranker (§23). Query expansion (§23). Cross-domain query (§23). Daily digest (§23). All non-ArXiv adapters.

---

#### M7 Spec Reference Block

**Primary (read):**
- `bishop_spec_0_6.md` L1183–1266 (§16 query layer — retrieval stack §16.1, RRF §16.2, challenge hooks §16.3, cold-start G7 §16.4+)
- L1267–1299 (§17 UI — batch summary, search, entry detail, escalation panel; implement MVP subset only)
- L1423–1444 (§21 cold start — G7 graceful init contract, step 6; §21 steps 7–8 for e2e gate)
- L1501–1512 (§22 Query Layer + UI)

**Adjacent (read, do not implement):**
- L537–541 (§8.3 DuckDB `read_only=True` — critical for query-api)
- L543–578 (§8.4 BM25 reload atomicity G5, challenge_hooks index reload)
- L525–535 (§8.2 LanceDB query path)
- L1104–1146 (§14 error/escalation — `ESCALATION_FLAGGED` panel; read for context; full manual retry deferred to M8)
- L1300–1339 (§18 backfill — context for G7 cold-start at backfill scale; do not implement)

**Gates:**
- Entry: G5 (quality gate passed); G6 (pre-filter + enrichment quality sampling); at least one full e2e round-trip at `INDEXED`
- Exit: G4 (§21 steps 7–8 e2e smoke); CLI search verified; UI batch list loads; cold-start clean

**Pre-plan stub:** See §6.

---

### M8 — Hardening and Scale

**Intent.** Implement remaining source adapters (HuggingFace, PapersWithCode, SemanticScholar, GitHub, OpenReview; LessWrong pending API verification), complete UI (escalation panel with manual retry/permanent-fail, reading status updates), run full e2e validation across all sources, and enable backfill after quality gates pass.

**Runnable checkpoint.** All adapters registered and producing `DISCOVERED` entries. Full UI functional including escalation panel. 20-entry sample pre-filter quality gate: precision/recall assessed against manual judgment. 10-entry enrichment quality gate: `challenge_hooks` and `value_rationale` assessed. NL profile iterated if quality off. All-sources backfill enabled, chunked, monitored.

**§22 mapping.** Source Adapters (remaining, L1461–1466). UI (full, L1509–1512). Validation and Backfill (L1514–1520).

**Services touched.** `scraper` (new adapters), `ui` (full), `state-worker` (escalation manual retry/permanent-fail endpoints exercised).

**Contract surfaces extended.**
- `ADAPTER_REGISTRY` expanded: HuggingFace, PapersWithCode, SemanticScholar, GitHub, OpenReview, LessWrong (if verified)
- `fetch_manifest` + `fetch_content` per new adapter (per §10.2 and Appendix B per-source details)
- Escalation panel: `GET /escalations`, manual retry action (`POST /entries/retry`), permanent-fail action
- Reading status update: `ReadingStatusEnum` transitions via UI
- Backfill config: per-source `backfill_window_days` from §18.2

**Entry gate.** G4 (e2e smoke on single source complete). G5 (embedding quality gate). G6 (pre-filter + enrichment quality sampling). G7 (backfill enable gate): passage of G5 + quality validation + all-sources test. All program gates G0–G6 must be satisfied.

**Exit gate.** G7 (backfill enabled): all-sources e2e verified; pre-filter and enrichment quality gates passed; backfill running and producing `INDEXED` entries without pipeline errors. Escalation panel: `ESCALATION_FLAGGED` entries reachable, manual retry produces state transition.

**Parallelism.** All non-ArXiv adapters can be implemented in parallel (each is independent). UI escalation panel and reading status updates can proceed in parallel with adapter work. Backfill configuration is sequential after all adapters pass verification.

**Explicit non-goals.** All §23 deferred items (graph layer, daily digest, cosine anchor migration, personal domain, cross-domain query, reranker, query expansion, local enrichment path, time-decayed weights, reading history analytics, Redis/Postgres upgrades). All §24 rejected items. `DomainEnum.both` (removed).

---

#### M8 Spec Reference Block

**Primary (read):**
- `bishop_spec_0_6.md` L1300–1339 (§18 backfill — principles, per-source config, ArXiv category filtering, chunking)
- L1461–1466 (§22 Source Adapters: remaining adapters)
- L1509–1512 (§22 UI: full)
- L1514–1520 (§22 Validation and Backfill)
- L1423–1444 (§21 cold start steps 9–12 — quality gates, backfill enable sequence)

**Adjacent (read, do not implement):**
- L81–103 (§3 source stack — all adapters, §3.2 personal domain stay deferred)
- L762–873 (§10 source adapter pattern — §10.2 per-source implementation notes)
- L1682–1709 (Appendix B — per-source schedule defaults and backfill configs)
- L1267–1299 (§17 UI — escalation panel, reading status, manual retry §17.2 manual retry; defer personal domain UI)
- L1104–1146 (§14 error/escalation — ESCALATION_FLAGGED routing, manual retry mapping table §14.2)
- L1524–1546 (§23 deferred — confirm all non-goals; do not implement anything here)

**Gates:**
- Entry: G4, G5, G6 all satisfied; all prior M-plans at auditor-verified §8 handoff
- Exit: G7 — backfill running; quality gates passed; all adapters producing `DISCOVERED` entries; escalation panel functional

**Pre-plan stub:** See §6.

---

## 4. Cross-Milestone Contract Registry

These symbols are program-level persistent contracts. Any change mid-milestone requires an orch §7 amendment. A new stage requires a new M-plan entry.

### Persistent Symbols

| Symbol | Defined In | Owner Milestone | Consumers |
|--------|-----------|-----------------|-----------|
| `ProcessingState` enum (complete) | §6.1 L261–288 | M1 | M2–M8 |
| `ManifestEntry` Pydantic model | §7.1 L357–383 | M1 | M2, M3, M4 |
| `Entry` Pydantic model | §7.2 L385–435 | M1 | M4–M8 |
| `BatchRecord` Pydantic model | §7.3 L437–459 | M1 | M3, M5 |
| `ErrorLog` Pydantic model | §7.4 L461–477 | M1 | M2–M8 |
| `ScraperState` Pydantic model | §7.6 L494–505 | M1 | M2 |
| All §9.1 REST endpoints | §9.1 L613–760 | M1 | M2–M8 |
| Volume layout paths | §8.5 L580–595 | M0 | M1–M8 |
| `SourceAdapter` ABC | §10.1 L764–795 | M2 | M4, M8 |
| NL profile schema + `canonical_hash` | §11.2 L885–987 | M3 | M5, M8 |
| Embedding model + text pin | §8.4 L572–574, §5.6 L222–225 | M6 | M7, M8 |
| BM25 directory layout | §8.4 L565–570 | M6 | M7 |
| RRF formula (k=60, 3-channel) | §16.2 L1211–1228 | M7 | M8 |

### Amendment Rules

- **Contract change mid-milestone** → orch §7 amendment; document in `.dev/decision-logs/<m-plan>/`.
- **New stage added** → new M-plan entry; do not extend existing M-plan scope.
- **Staleness rule**: if the context map SHA does not match the prior milestone §8 handoff SHA, re-run pre-plan exploration before re-plan.

### Contract Hub Restriction

1. **`state-worker`** — sole SQLite writer. Only one active M-plan may extend its REST surface at a time. If two milestones would both add endpoints, serialize them into sequential M-plans or gate with an explicit handoff.
2. **`batch-poller`** — introduced in M3 (pre-filter batch types), extended in M5 (enrichment batch types + startup scan for enrichment). Must not be split across unrelated plans without a named owner subtask.

---

## 5. Program Gates (Ordered)

| Gate | Condition | Blocks |
|------|-----------|--------|
| **G0** | `bishop_spec_0_6.md` committed and tracked in repo at a stable SHA | M0 pre-plan |
| **G1** | `docker compose up` → all 9 containers running → `state-worker GET /health` returns 200 | M1 pre-plan |
| **G2** | All §9.1 `state-worker` contract tests pass; atomic claim double-poll verified; sweep task verified | M2 pre-plan |
| **G3** | Direct test call to Anthropic Messages API with model `claude-haiku-4-5-20251001` returns non-400 | M3 Anthropic work (blocks all LLM pipeline components) |
| **G4** | §21 steps 7–8 e2e smoke: ArXiv entries flow from `DISCOVERED` → `INDEXED` in a single run | M8 full source expansion |
| **G5** | §21 step 9–10: 3–5 mid-spec test queries against `challenge_hooks` return intuitively correct semantic results | Backfill enable (G7) |
| **G6** | Pre-filter quality sampling (20 decisions, precision/recall vs. manual judgment acceptable) + enrichment quality sampling (10 entries, `challenge_hooks` and `value_rationale` assessed) | Backfill enable (G7) |
| **G7** | G5 + G6 + all-sources e2e verified → backfill enabled, chunked, monitored | Program complete |

**G3 detail.** Per §22 L1469: before building any component that calls the Anthropic API, make one direct test call to Anthropic Messages API using model `claude-haiku-4-5-20251001`. HTTP 400 = model string invalid; all enrichment pipeline work blocked. This is a 60-second check; do not skip.

**G5 detail.** Per §8.4 L576: if the quality gate fails, upgrade to `nomic-embed-text` (768 dims via Ollama) before backfill. Index rebuild at validation scale is cheap; at post-backfill scale it is expensive. Do not proceed to G7 if G5 fails.

---

## 6. Pre-plan / Orch Invocation Stubs

Copy and paste these into a pre-plan or orch session. Replace `[prior handoff path]` with the actual `.dev/plans/<m-plan>/handoff.md` path.

---

### M0 — Implementation Workshop

```
Milestone: M0 — Implementation Workshop
Intent: Docker Compose skeleton; 9 services defined; state-worker /health; volumes; network; host ports for query-api + ui only.

Spec slices to read (only these, not the full spec):
  bishop_spec_0_6.md L597–612   (§9 service table)
  bishop_spec_0_6.md L580–595   (§8.5 volume mounts)
  bishop_spec_0_6.md L1449–1451 (§22 Foundation: compose + health)
  bishop_spec_0_6.md L39–53     (§1 overview — adjacent context)
  bishop_spec_0_6.md L105–160   (§4 architecture diagram — adjacent)

Prior handoff: none (first milestone)
Architecture folder: none yet (initialize after M0 completes)

Non-goals: No application logic, no migrations, no DB init, no endpoints beyond /health.
Expected subtask count: 4–5 (Dockerfiles, Compose file, volume config, health endpoint, smoke test)
```

---

### M1 — State Kernel

```
Milestone: M1 — State Kernel
Intent: Full state-worker — Alembic, schema, enums, models, all state transitions, REST API, sweeps, atomic claims.

Spec slices to read (only these):
  bishop_spec_0_6.md L259–354   (§6 state machine — complete)
  bishop_spec_0_6.md L355–505   (§7 schema — all models)
  bishop_spec_0_6.md L509–523   (§8.1 SQLite — WAL, migration, aiosqlite startup)
  bishop_spec_0_6.md L613–760   (§9.1 REST API — all endpoints)
  bishop_spec_0_6.md L1452–1454 (§22 Foundation: state-worker, enums, models)
  bishop_spec_0_6.md L1369–1422 (§20 enums/tags — adjacent)
  bishop_spec_0_6.md L1104–1146 (§14 error/escalation — adjacent)

Prior handoff: .dev/plans/m0-workshop/handoff.md
Architecture folder: .dev/architecture/ at M0 handoff SHA

Non-goals: No scraper, no workers, no query-api. Defer §23, §24.
Expected subtask count: 5–7 (migrations, models, transition logic, poll endpoints, result endpoints, sweeps, contract tests)
```

---

### M2 — Discovery Slice

```
Milestone: M2 — Discovery Slice
Intent: SourceAdapter ABC, ADAPTER_REGISTRY, failure envelope, scraper loop, ArXiv adapter only → entries DISCOVERED.

Spec slices to read (only these):
  bishop_spec_0_6.md L762–873   (§10 source adapter pattern — complete)
  bishop_spec_0_6.md L81–103    (§3 source stack — ArXiv §3.1)
  bishop_spec_0_6.md L1147–1182 (§15 rate limiting)
  bishop_spec_0_6.md L164–172   (§5.1 Stage 1 discovery — adjacent)
  bishop_spec_0_6.md L494–505   (§7.6 ScraperState — adjacent)
  bishop_spec_0_6.md L1456–1460 (§22 Source Adapters: subset)

Prior handoff: .dev/plans/m1-state-kernel/handoff.md
Architecture folder: .dev/architecture/ at M1 handoff SHA

Non-goals: Non-ArXiv adapters, fetch_content, enrichment, indexing. §19.2–19.3 deferred. §3.2 deferred.
Expected subtask count: 4–5 (ABC + registry, failure envelope, rate limiting, ArXiv manifest, scraper loop + scheduler)
```

---

### M3 — Pre-filter Slice

```
Milestone: M3 — Pre-filter Slice
Intent: NL profile v1.0.0, renderer, pre-filter-worker, batch-poller v1 → RELEVANCE_PASSED/REJECTED. G3 required.

Spec slices to read (only these):
  bishop_spec_0_6.md L173–185   (§5.2 Stage 2 pre-filter)
  bishop_spec_0_6.md L874–987   (§11 NL profile system)
  bishop_spec_0_6.md L988–1037  (§12 pre-filter layer)
  bishop_spec_0_6.md L238–258   (§5.7 batch lifecycle — adjacent)
  bishop_spec_0_6.md L437–459   (§7.3 BatchRecord schema — adjacent)
  bishop_spec_0_6.md L1468–1475 (§22 Pre-filter Layer)

Prior handoff: .dev/plans/m2-discovery/handoff.md
Architecture folder: .dev/architecture/ at M2 handoff SHA

Entry requirement: G3 (model string verification) must complete before any Anthropic API call.
Non-goals: Enrichment batch types in batch-poller, content scraping, indexing. §23 deferred.
Expected subtask count: 4–6 (model string gate, NL profile + canonical_hash, renderer, pre-filter worker, batch-poller v1 + startup scan, state transitions)
```

---

### M4 — Content Slice

```
Milestone: M4 — Content Slice
Intent: content-scraper + ArxivAdapter.fetch_content → entries SCRAPED with content_raw populated.

Spec slices to read (only these):
  bishop_spec_0_6.md L186–193   (§5.3 Stage 3 content scrape)
  bishop_spec_0_6.md L762–873   (§10 — fetch_content §10.1, ArXiv implementation)
  bishop_spec_0_6.md L385–435   (§7.2 Entry schema — adjacent)
  bishop_spec_0_6.md L326–344   (§6.3 failure classification — adjacent)
  bishop_spec_0_6.md L1477–1479 (§22 Content Scraping)

Prior handoff: .dev/plans/m3-prefilter/handoff.md
Architecture folder: .dev/architecture/ at M3 handoff SHA

Entry requirement: At least one RELEVANCE_PASSED entry in manifest (M3 pre-filter ran).
Non-goals: fetch_content for non-ArXiv adapters, enrichment, indexing. §23 deferred.
Expected subtask count: 4 (ArXiv fetch_content, content-scraper service, provenance null assertion verification, SCRAPE_FAILED path test)
```

---

### M5 — Enrichment Slice

```
Milestone: M5 — Enrichment Slice
Intent: enrichment-batcher dual tasks, Call 1 + Call 2 prompts, truncation, OOV parser, batch-poller v2 → VECTOR_WRITE_QUEUED.

Spec slices to read (only these):
  bishop_spec_0_6.md L195–215   (§5.4–5.5 enrichment stages 4a and 4b)
  bishop_spec_0_6.md L1038–1103 (§13 enrichment — truncation §13.1, prompt design §13.2, challenge_hooks §13.3)
  bishop_spec_0_6.md L238–258   (§5.7 batch lifecycle)
  bishop_spec_0_6.md L437–459   (§7.3 BatchRecord — batch_type enrichment values)
  bishop_spec_0_6.md L479–492   (§7.5 OovTagsLog schema)
  bishop_spec_0_6.md L1369–1422 (§20 tag taxonomy — constrains Call 1)
  bishop_spec_0_6.md L1625–1681 (Appendix A — prompt sketches)
  bishop_spec_0_6.md L1481–1491 (§22 Enrichment Pipeline)

Prior handoff: .dev/plans/m4-content/handoff.md
Architecture folder: .dev/architecture/ at M4 handoff SHA

Entry requirement: G3 (model string verified). SCRAPED entries with content_raw.
Non-goals: Vector writing, indexing, query path, UI. §23 deferred.
Expected subtask count: 5–7 (Call 1 prompt + OOV parser, Call 2 prompt + cache_control, truncation helper, enrichment-batcher Task A, enrichment-batcher Task B, batch-poller v2 extension, state transition tests)
```

---

### M6 — Indexing Slice

```
Milestone: M6 — Indexing Slice
Intent: vector-writer — embed (all-MiniLM-L6-v2), LanceDB idempotency, BM25 (main + challenge_hooks, file lock, atomic persistence), DuckDB upsert → INDEXED. G5 quality gate required.

Spec slices to read (only these):
  bishop_spec_0_6.md L217–237   (§5.6 Stage 5 vector indexing)
  bishop_spec_0_6.md L525–535   (§8.2 LanceDB)
  bishop_spec_0_6.md L537–541   (§8.3 DuckDB)
  bishop_spec_0_6.md L543–578   (§8.4 BM25 — complete)
  bishop_spec_0_6.md L580–595   (§8.5 volumes — adjacent)
  bishop_spec_0_6.md L1437      (§21 step 9–10 quality gate)
  bishop_spec_0_6.md L1493–1499 (§22 Indexing)

Prior handoff: .dev/plans/m5-enrichment/handoff.md
Architecture folder: .dev/architecture/ at M5 handoff SHA

Entry requirement: VECTOR_WRITE_QUEUED entries with all enrichment fields populated.
Exit requirement: G5 — embedding quality gate must pass before M7 proceeds.
Non-goals: Query API, UI, backfill, BM25 reload in query-api. §23 deferred.
Expected subtask count: 4–6 (embedding + LanceDB write, BM25 main index, BM25 challenge_hooks index, file lock + atomic persistence, DuckDB upsert, quality gate test)
```

---

### M7 — Read Path

```
Milestone: M7 — Read Path
Intent: query-api (RRF, challenge_hooks channel, cold-start G7), Typer CLI, minimal UI (batch summary + search).

Spec slices to read (only these):
  bishop_spec_0_6.md L1183–1266 (§16 query layer — complete)
  bishop_spec_0_6.md L1267–1299 (§17 UI — read for MVP subset: batch summary, search, entry detail)
  bishop_spec_0_6.md L1423–1444 (§21 cold start — G7 graceful init, §21 steps 7–8 e2e gate)
  bishop_spec_0_6.md L543–578   (§8.4 BM25 reload atomicity G5 — adjacent)
  bishop_spec_0_6.md L537–541   (§8.3 DuckDB read_only=True — adjacent)
  bishop_spec_0_6.md L1501–1512 (§22 Query Layer + UI subset)

Prior handoff: .dev/plans/m6-indexing/handoff.md
Architecture folder: .dev/architecture/ at M6 handoff SHA

Entry requirement: G5 passed. G6 pre-filter + enrichment quality sampling done. INDEXED entries present.
Non-goals: Full UI escalation panel (M8), reranker (§23), query expansion (§23), cross-domain (§23).
Expected subtask count: 5–6 (BM25 retrieval + reload, dense retrieval, DuckDB metadata filter, RRF fusion, problem-shaped classifier, CLI + minimal UI)
```

---

### M8 — Hardening and Scale

```
Milestone: M8 — Hardening and Scale
Intent: Remaining adapters, full UI (escalations, manual retry), e2e all sources, quality gates, backfill enable.

Spec slices to read (only these):
  bishop_spec_0_6.md L1300–1339 (§18 backfill — complete)
  bishop_spec_0_6.md L762–873   (§10 — per-adapter implementation notes)
  bishop_spec_0_6.md L1682–1709 (Appendix B — per-source schedule defaults)
  bishop_spec_0_6.md L1267–1299 (§17 UI — full; escalation panel, manual retry)
  bishop_spec_0_6.md L1104–1146 (§14 error/escalation — manual retry mapping §14.2)
  bishop_spec_0_6.md L1423–1444 (§21 steps 9–12 — quality gates, backfill sequence)
  bishop_spec_0_6.md L1461–1466 (§22 Source Adapters: remaining)
  bishop_spec_0_6.md L1514–1520 (§22 Validation and Backfill)
  bishop_spec_0_6.md L1524–1546 (§23 deferred — confirm non-goals)

Prior handoff: .dev/plans/m7-read-path/handoff.md
Architecture folder: .dev/architecture/ at M7 handoff SHA

Entry requirement: G4, G5, G6 all satisfied. INDEXED entries from ArXiv e2e run.
Exit requirement: G7 — backfill running; all adapters verified; quality gates passed.
Non-goals: §23 full list; §24 rejected items; personal domain §3.2.
Expected subtask count: 5–7 (HF adapter, PwC adapter, SS adapter, GitHub adapter, OpenReview adapter, full UI, backfill config + validation)
```

---

## 7. Post-Milestone Housekeeping Checklist

After each M-plan reaches *Auditor §8 handoff*:

- [ ] **Update `.dev/architecture/`** — re-run project-architecture skill; update `module-map.md`, `public-interface-inventory.md`, `data-contract-registry.md`, `known-coupling-surfaces.md`. Commit with message `arch: post-M<n> architecture folder update`.
- [ ] **Append milestone changelog** — create or append to `.dev/changelogs/M<n>-<name>.md`. Include: what was built, what was deferred to next milestone, any decisions made during implementation that are not yet in the spec.
- [ ] **Decision logs** — for any subtask that extended a contract-anchor surface (`state-worker` REST API, `ProcessingState` enum, Pydantic models, volume layout), ensure a decision log exists at `.dev/decision-logs/<m-plan>/<subtask>.md`. If an earlier decision log was superseded, mark it `status: superseded` with a pointer to the new log.
- [ ] **Record §8.1 verification** — add to `.dev/plans/<m-plan>/handoff.md`: the HEAD SHA at handoff, the `docker compose up` command and its output, the exact verification command run, and its result. Format:
  ```
  SHA: <git rev-parse HEAD>
  Command: docker compose up -d && curl http://localhost:<port>/<endpoint>
  Result: <HTTP status and response snippet>
  ```
- [ ] **Pin "landed contracts" summary** — in `.dev/plans/<m-plan>/handoff.md`, list all contract surfaces extended during this milestone (symbol names, file paths, spec sections). This is the §0 input for the next milestone's orch plan.
- [ ] **Verify clean tree** — `git status` shows no uncommitted changes before handoff is recorded.

---

## 8. Non-Goals (Program Level)

The following are explicitly not planned in M0–M8 and must not appear in any M-plan scope. They are tracked in the spec at §23 (L1524–1545) and §24 (L1547–1564).

**Deferred (§23):** Graph layer (Kuzu, citation traversal), daily digest, cosine anchor migration (§12.3 Phase 2+), personal domain scrapers and NL profile (§3.2, §19.2), cross-domain query (§19.3), reranker (`ms-marco-MiniLM-L-6-v2` §16.6), query expansion (§16.5), interest profile re-enrichment on version bump, local enrichment path (Qwen/Llama via Ollama), time-decayed retrieval weights, reading history analytics, Redis queue upgrade, Postgres state store upgrade, LessWrong (pending API verification).

**Rejected (§24):** PyQt6 UI, HuggingFace as primary paper source, content hash for dedup, semantic anchor embeddings as MVP pre-filter, Gemini Flash for pre-filter, Redis + Celery, single container, global BM25 index, GPT-4o-mini for enrichment, synchronous state-worker.

Every M-plan §1 non-goals section **must** include: *"All items in §23 and §24 of bishop_spec_0_6.md are non-goals for this plan."*

---

*Charter version 0.1.0 — 2026-06-09 — Alejandro Garay Frontini*
