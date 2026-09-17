Section:      architectural-patterns
Version:      1.0.3
Last updated: 2026-09-13

none at this time — pending user input (2026-06-10)

Patterns will be recorded after Phase 8 interview confirmation. Code-derived candidates (not yet confirmed as architectural contracts):

**M0 candidates:**

- Constants single-source: service names, volumes, and ports live in `bishop_shared.constants` (falsifier: `tests/test_constants.py`, `tests/test_compose.py`)
- Repo-root Docker build context: all service Dockerfiles require `context: .` (falsifier: `tests/test_compose.py::test_repo_root_build_context_for_bishop_shared`)
- No port literals in leftover stubs: HTTP stubs import ports from constants (falsifier: `tests/test_service_stubs.py::PORT_LITERAL_PATTERN`) — stubs are not Docker CMDs

**M1 candidates:**

- Transition engine sole mutator: all state changes go through `transitions.py`, not routers directly (falsifier: grep routers for SQL outside `_db_conn` delegation; contract tests)
- Integrity then migrations before serve: `enforce_integrity()` then `run_migrations()` then `init_pool()` (falsifier: `tests/test_state_worker_integrity_gate.py`, `tests/test_state_worker_main.py`)
- G2 contract gate: charter-critical behaviors in `tests/test_state_worker_contract.py` run by `verify-g2.sh` (falsifier: `scripts/verify-g2.sh` + `tests/test_verify_g2.py`)
- Alert dual-write: M1 triggers emit CRITICAL log + ALERT `error_log` row via `emit_alert()` (falsifier: `tests/test_state_worker_alerts.py` — still not in `verify-g2.sh` per F-014)

**M2 candidates:**

- Cross-service enum drift guard: `bishop_shared.enums` literals must match state-worker §20 enums (falsifier: `tests/test_shared_enums.py`)
- Adapter registry bootstrap: scrape loop iterates `ADAPTER_REGISTRY` only (falsifier: `tests/test_scraper_loop.py`)
- Rate limit before HTTP: token-bucket `acquire()` precedes outbound requests (falsifier: per-adapter tests)
- Milestone image tags: compose images use `bishop/<service>:m<N>` (falsifier: `tests/test_compose.py::test_image_tags_use_milestone_convention`)

**M3 candidates:**

- G3 model-string gate: `ANTHROPIC_MODEL_PREFILTER` verified before first Anthropic submit; HTTP 400 is fatal (falsifier: `scripts/verify-g3.sh`, `tests/test_verify_g3.py`)
- Profile hash integrity: runtime `compute_profile_hash` must match YAML `canonical_hash` before batch submit (falsifier: `tests/test_profile_renderer.py`)
- Batch type isolation: batch-poller tracks only declared `TRACKED_BATCH_TYPES` (falsifier: `tests/test_batch_poller_loop.py`, `tests/test_batch_poller_enrichment.py`)
- M3 verification gate: `verify-m3.sh` chains G2 → G3 → M3 pytest modules (falsifier: `tests/test_verify_m3.py`)

**M4–M8 candidates:**

- Content-scraper poll-claim on `RELEVANCE_PASSED` → `fetch_content` → POST `/entries/content` (falsifier: `tests/test_content_scraper_loop.py`, `tests/test_m4_integration.py`)
- Provenance gate before entry creation (falsifier: `tests/test_m4_provenance_contract.py`)
- Vendored `scraper_app` in content-scraper image (falsifier: `services/content-scraper/Dockerfile`)
- Two-stage enrichment batches (falsifier: `tests/test_m5_integration.py`)
- Gate-split profile pins: prefilter filename ≠ enrichment filename (falsifier: `tests/test_profile_renderer.py`)
- Triple-store index write: LanceDB + dual BM25 + DuckDB mirror (falsifier: `tests/test_m6_integration.py`)
- SQLite read-only URI for query-api (`mode=ro`) (falsifier: `tests/test_query_api_routes_entry.py::test_read_entry_opens_sqlite_read_only`)
- Write-proxy pattern: UI → query-api → state-worker; UI never opens SQLite or STATE_WORKER_URL (falsifier: `tests/test_ui_routes.py`, `tests/test_compose.py::test_ui_query_api_url_env`)
- RRF multi-channel search (falsifier: `tests/test_query_api_search_orchestrator.py`, `tests/test_m7_integration.py`)
- G7 cold-start: missing stores → empty channels, no crash (falsifier: `tests/test_query_api_cold_start.py`)
- Seven-source `ADAPTER_REGISTRY` sole merger (falsifier: `services/scraper/app/adapters/registry.py`, `tests/test_scraper_loop.py`)
- Chunked backfill when `BISHOP_BACKFILL_ENABLED=1` (falsifier: `tests/test_scraper_backfill_chunking.py`)

**Prompt-caching candidates:**

- Single cache breakpoint on last system block via `cached_system_blocks` (falsifier: `tests/test_prompt_cache.py`)
- Token floor keys A/B/C ≥ 4506 cl100k_base (10% over 4096 API floor) (falsifier: `tests/test_prompt_cache_token_floor.py`)
- Rubric hash-or-abort mirrors profile discipline (falsifier: `tests/test_rubric_assets.py`)
- Batch-level `cache_usage` aggregation logged on completion, not persisted (falsifier: `tests/test_batch_poller_loop.py`)

**Ops / overlay candidates:**

- Soft-launch `RELEVANCE_PARKED` for peripheral pass (falsifier: `tests/test_state_worker_transitions.py`, `tests/test_ui_parked.py`)
- SQLite integrity gate before migrations (falsifier: `tests/test_state_worker_integrity_gate.py`)
- Host snapshot with `integrity_check` gate (falsifier: `tests/test_sqlite_snapshot.py`, `tests/test_sqlite_restore.py`)
- state-worker sole SQLite writer (falsifier: `tests/test_sqlite_wal_concurrency.py`)

**Stale M2 candidate (do not treat as current):** `fetch_content` deferred `NotImplementedError("M4")` — all seven registered adapters implement `fetch_content`; the ABC default still raises.

These require user confirmation and explicit falsifiers before auditor-review may consume this file.
