Section:      architectural-patterns
Version:      1.0.1
Last updated: 2026-06-12

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

These require user confirmation and explicit falsifiers before auditor-review may consume this file.
