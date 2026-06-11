Section:      architectural-patterns
Version:      1.0.0
Last updated: 2026-06-10

none at this time — pending user input (2026-06-10)

Patterns will be recorded after Phase 8 interview confirmation. Code-derived candidates (not yet confirmed as architectural contracts):

- Constants single-source: service names, volumes, and ports live in `bishop_shared.constants` and are asserted by pytest (falsifier: `tests/test_constants.py`, `tests/test_compose.py`)
- Repo-root Docker build context: all service Dockerfiles require `context: .` (falsifier: `tests/test_compose.py::test_repo_root_build_context_for_bishop_shared`)
- No port literals in stub source: HTTP stubs import ports from constants (falsifier: `tests/test_service_stubs.py::PORT_LITERAL_PATTERN`)
- state-worker health-only at M0: only `/health` route registered (falsifier: `tests/test_state_worker_health.py::test_only_health_route_exposed`)

These require user confirmation and explicit falsifiers before auditor-review may consume this file.
