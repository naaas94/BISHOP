Section:      architectural-patterns
Version:      1.0.2
Last updated: 2026-06-13

none at this time — pending user input (2026-06-10)

Patterns will be recorded after Phase 8 interview confirmation. Code-derived candidates (not yet confirmed as architectural contracts):

**M0 candidates (unchanged):**

- Constants single-source: service names, volumes, and ports live in `bishop_shared.constants` (falsifier: `tests/test_constants.py`, `tests/test_compose.py`)
- Repo-root Docker build context: all service Dockerfiles require `context: .` (falsifier: `tests/test_compose.py::test_repo_root_build_context_for_bishop_shared`)
- No port literals in stub source: HTTP stubs import ports from constants (falsifier: `tests/test_service_stubs.py::PORT_LITERAL_PATTERN`)

**M1 candidates:**

- Transition engine sole mutator: all state changes go through `transitions.py`, not routers directly (falsifier: grep routers for SQL outside `_db_conn` delegation — manual; contract tests exercise paths)
- Migrations before serve: `run_migrations()` in lifespan before `init_pool()` (falsifier: `tests/test_state_worker_main.py` lifespan ordering)
- G2 contract gate: charter-critical behaviors asserted in `tests/test_state_worker_contract.py` run by `verify-g2.sh` (falsifier: `scripts/verify-g2.sh` + `tests/test_verify_g2.py`)
- Alert dual-write: M1 triggers emit CRITICAL log + ALERT `error_log` row via `emit_alert()` (falsifier: `tests/test_state_worker_alerts.py` — note: not yet in verify-g2.sh per F-014)

**M2 candidates:**

- Cross-service enum drift guard: `bishop_shared.enums` literals must match state-worker §20 enums (falsifier: `tests/test_shared_enums.py`)
- Adapter registry bootstrap: scrape loop iterates `ADAPTER_REGISTRY` only; no ad-hoc adapter instantiation (falsifier: grep `loop.py` / `tests/test_scraper_loop.py`)
- Rate limit before HTTP: token-bucket `acquire()` precedes outbound ArXiv request (falsifier: inspection of `arxiv.py`; plan §5.4 dedicated unit test overstated per M2 audit F-006)
- fetch_content deferred: default `SourceAdapter.fetch_content` raises `NotImplementedError("M4")` (falsifier: `tests/test_scraper_adapters.py`)
- Milestone image tags: compose images use `bishop/<service>:m<N>` matching implemented milestone (falsifier: `tests/test_compose.py::test_image_tags_use_milestone_convention`)

**M3 candidates:**

- G3 model-string gate: `ANTHROPIC_MODEL_PREFILTER` verified before first Anthropic submit; HTTP 400 is fatal (falsifier: `scripts/verify-g3.sh`, `tests/test_verify_g3.py`, `tests/test_prefilter_loop.py`)
- Profile hash integrity: runtime `compute_profile_hash` must match YAML `canonical_hash` before batch submit (falsifier: `tests/test_profile_renderer.py`, pre-filter hash mismatch alert path)
- Anthropic custom_id join: batch item `custom_id` equals manifest `source_id` (falsifier: `tests/test_m3_integration.py`, `tests/test_prefilter_anthropic_client.py`)
- Batch type isolation: batch-poller processes only `pre_filter` batch_type (falsifier: `tests/test_batch_poller_loop.py` enrichment rejection)
- M3 verification gate: `verify-m3.sh` chains G2 → G3 → M3 pytest modules (falsifier: `tests/test_verify_m3.py`)
- Transition engine batch mutations: batch register/patch/timeout/results go through `transitions.py` (falsifier: `tests/test_state_worker_batches_register.py`)

These require user confirmation and explicit falsifiers before auditor-review may consume this file.
