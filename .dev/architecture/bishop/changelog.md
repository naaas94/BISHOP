[MINOR] 1.0.0 — 2026-06-10 — Initial construction (M0 codebase snapshot).
[MINOR] module-map.md 1.1.0 — 2026-06-12 — Added M1 state-worker submodules and M2 scraper package tree; updated milestone notes. Trigger: new module or package.
[MINOR] public-interface-inventory.md 1.1.0 — 2026-06-12 — Added §9.1 routes, transition engine symbols, scraper adapter/client surface, SQLITE_DB_PATH, shared enums. Trigger: schema change, new module or package.
[MINOR] data-contract-registry.md 1.1.0 — 2026-06-12 — Added §7 SQLite tables, domain/HTTP models, scraper wire DTOs, ArXiv Atom contract; STATE_WORKER_URL now consumed. Trigger: schema change.
[MINOR] dependency-graph.md 1.1.0 — 2026-06-12 — Added scraper→state-worker HTTP, enum drift guard, Alembic/aiosqlite/httpx; export.arxiv.org external dep. Trigger: new external dependency, new module or package.
[MINOR] integration-seams.md 1.1.0 — 2026-06-12 — Added scraper↔state-worker REST, SQLite file seam, ArXiv Atom export API. Trigger: new integration seam.
[MINOR] external-input-sources.md 1.1.0 — 2026-06-12 — Added ArXiv Atom feed, scraper env vars, internal manifest batch ingress. Trigger: new external input source.
[PATCH] architectural-patterns.md 1.0.1 — 2026-06-12 — Expanded M1/M2 code-derived pattern candidates from audits and CHANGELOG. Trigger: staleness window elapsed (partial — patterns still pending user confirmation).
[MINOR] known-coupling-surfaces.md 1.1.0 — 2026-06-12 — Added milestone image tags, SQLITE_DB_PATH, enum drift guard, source_id format, domain wire, G2 gate module list, start_period 30s. Trigger: schema change, new module or package.
[MINOR] open-questions.md 1.1.0 — 2026-06-12 — Removed resolved Phase 2 spec question; added G2 alerts coverage and enum consolidation questions. Trigger: open question resolved.
[MINOR] module-map.md 1.2.0 — 2026-06-13 — Added M3 pre-filter-worker and batch-poller app trees, bishop_shared profile_renderer/anthropic_config, config/profiles. Trigger: new module or package.
[MINOR] public-interface-inventory.md 1.2.0 — 2026-06-13 — Added batch lifecycle routes, transition symbols, pre-filter-worker and batch-poller clients, bishop_shared M3 symbols. Trigger: schema change, new module or package.
[MINOR] data-contract-registry.md 1.2.0 — 2026-06-13 — Added m3_001 source_ids, batch register/patch/timeout, pre-filter results, ProfileDocument, Anthropic custom_id contract. Trigger: schema change.
[MINOR] dependency-graph.md 1.2.0 — 2026-06-13 — Added pre-filter/batch-poller HTTP and profile volume coupling; anthropic and PyYAML external deps. Trigger: new external dependency, new module or package.
[MINOR] integration-seams.md 1.2.0 — 2026-06-13 — Added pre-filter-worker and batch-poller state-worker routes; Anthropic Batches API seam. Trigger: new integration seam.
[MINOR] external-input-sources.md 1.2.0 — 2026-06-13 — Added NL profile YAML, worker env vars, Anthropic batch result parsing. Trigger: new external input source.
[PATCH] architectural-patterns.md 1.0.2 — 2026-06-13 — Added M3 code-derived pattern candidates (G3 gate, profile hash, custom_id join). Trigger: staleness window elapsed (partial).
[MINOR] known-coupling-surfaces.md 1.2.0 — 2026-06-13 — Added m3 image tags, G3/model string, profile hash, custom_id, batch_type, verify-m3 chain. Trigger: schema change, new module or package.
[MINOR] open-questions.md 1.2.0 — 2026-06-13 — Added personal domain deferral and bishop_shared re-export questions. Trigger: new module or package.
[PATCH] open-questions.md 1.3.0 — 2026-06-13 — Added OPEN-001 escalations test hygiene question; see .dev/known-test-failures.md. Trigger: full-suite verification.
