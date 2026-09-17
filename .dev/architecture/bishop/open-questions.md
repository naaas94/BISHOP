Section:      open-questions
Version:      1.7.0
Last updated: 2026-09-16

```
Question:     Should QUERY_API_HOST_PORT and UI_HOST_PORT be documented in .env.example alongside BISHOP_DATA_ROOT?
Impact:       docker-compose.yml, developer onboarding, G1 verification on non-default ports
Closes when:  Decision recorded in decision log; .env.example updated or explicitly rejected with rationale
```

```
Question:     Is tilde expansion of BISHOP_DATA_ROOT=~/bishop_data reliable on all Windows Docker Desktop setups?
Impact:       Volume bind paths, G1 writability checks, init-volumes scripts
Closes when:  Verified on target Windows environments, or a decision log records that the .env.example Windows explicit-path mandate is sufficient
Note:         Partially addressed in prose — `.env.example` tells Windows users to use an explicit path (Docker Desktop does not expand ~). Not closed: no verification log that every target setup is covered.
```

```
Question:     Should the per-service volume matrix move from tests/test_compose.py into bishop_shared or a dedicated config module?
Impact:       bishop_shared, docker-compose.yml, T1 coupling surface, future mount additions
Closes when:  A pre-plan or refactor decision chooses a single encoding location
```

```
Question:     Should tests/test_state_worker_alerts.py be included in scripts/verify-g2.sh (M1 audit F-014)?
Impact:       G2 gate coverage, §14.3 alert dual-write regression detection
Closes when:  Gate script updated or explicit waiver recorded in committed handoff
```

```
Question:     When will bishop_shared.enums subsume all §20 enums currently duplicated in state-worker/app/enums.py?
Impact:       bishop_shared, state-worker models, drift guard scope
Closes when:  Refactor lands or decision records intentional split (ProcessingState stays state-worker-local)
```

```
Question:     When will personal domain profile YAML and pre-filter routing be added (professional-only gates remain)?
Impact:       config/profiles/, pre-filter-worker domain gate, charter scope
Closes when:  Charter slice or explicit deferral recorded in decision log
```

```
Question:     Should bishop_shared re-export profile_renderer, anthropic_config, prompt_cache, and rubric_assets from __init__.py?
Impact:       import conventions across workers, tests
Closes when:  Refactor or explicit decision to keep direct submodule imports only
```

```
Question:     Should the nine services keep a shared top-level `app` package, or isolate pytest via conftest / per-service package names?
Impact:       Every tests/test_* that inserts services/*/ onto sys.path; monolithic `pytest tests/` hygiene (OPEN-002)
Closes when:  A decision log picks harness isolation (save-restore-and-pop + empty __init__.py on state-worker/vector-writer) versus renaming packages
Note:         2026-09-14: query-api regular package wins over state-worker/vector-writer namespace packages. Entry/stats tests are the leaky poisoners; search/UI already isolate correctly.
```

```
Question:     How should Bishop bound prompt injection from public ingest (Gate 1, Call 1, Call 1→Call 2 hop) — frozen adversarial eval first, prompt delimiters/fences first, or both?
Impact:       pre-filter-worker user_message, enrichment_prompts Call 1/Call 2 user builders, rubrics, vector-writer embeddings, eval harness
Closes when:  A decision log picks the order of work and a packet owns it (OPEN-023). Seed map: .dev/decision-logs/ops/ingest-content-risk-seed.md
```

```
Question:     Should ingest persist an http(s) allowlist on manifest.url and cap content_raw at the wire (and/or HTTP response size), independent of LLM work?
Impact:       scraper ManifestIngestEntry.url, state-worker ContentPostRequest, UI href on entry_detail/parked, SQLite TEXT growth
Closes when:  Decision recorded (allowlist + max_length, one of them, or explicit reject). Seed I-5 / I-6.
```

```
Question:     Is unauthenticated host publish of query-api and ui acceptable for this operator box, or should they bind localhost / require a shared secret?
Impact:       docker-compose host ports, UI promote/retry/permanent-fail, LAN read of the corpus
Closes when:  Explicit local-first acceptance, or a packet changes bind/auth (OPEN-023 I-7)
```

```
Question:     Should value extraction and action stay per-consumer, with Bishop only providing retrieval (and later a visit/scout sidecar), or should Bishop own a generalized extract into the VDB?
Impact:       future MCP bind, processing_state vs consumption sidecar, N1 embed text, value-scout routing
Closes when:  A few real hand-scouts exist and a decision log records artifact-vs-task density (PB-010). Seed: .dev/decision-logs/ops/mcp-consumer-extraction.md
```

**Closed 2026-09-13:** OPEN-001 escalations test hygiene — assertion is `len(error_log) == 2`. `.dev/known-test-failures.md` OPEN-001 marked closed 2026-09-14.
