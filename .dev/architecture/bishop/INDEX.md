Project:          bishop
Purpose:          Local-first knowledge intelligence pipeline — M1-M8: SQLite state kernel, multi-source discovery scraper (7 sources), Anthropic pre-filter/enrichment batch pipeline, LanceDB/DuckDB/BM25 indexing, query API, UI.
Primary language: Python 3.12
Key frameworks:   FastAPI, uvicorn, Pydantic, Alembic, aiosqlite, httpx, anthropic, PyYAML, Docker Compose, pytest
Repository:       c:\Users\Ale\Documents\Repos\BISHOP
Document version: 1.3.0
Last constructed: 2026-06-10
Last verified:    2026-09-10
Stale after:      2026-10-10

Files:
  module-map.md                    1.3.0   2026-09-10
  public-interface-inventory.md    1.2.0   2026-06-13   NOT re-audited for M4-M8 — see module-map.md "Deferred in this refresh"
  data-contract-registry.md        1.2.0   2026-06-13   NOT re-audited for M4-M8 — see module-map.md "Deferred in this refresh"
  dependency-graph.md              1.3.0   2026-09-10
  integration-seams.md             1.2.0   2026-06-13   NOT re-audited for M4-M8 — see module-map.md "Deferred in this refresh"
  external-input-sources.md        1.2.0   2026-06-13   NOT re-audited for M4-M8 — see module-map.md "Deferred in this refresh"
  architectural-patterns.md        1.0.2   2026-06-13   NOT re-audited for M4-M8 — see module-map.md "Deferred in this refresh"
  failure-taxonomy.md              1.0.0   2026-06-10
  known-coupling-surfaces.md       1.3.0   2026-09-10
  open-questions.md                1.2.0   2026-06-13   NOT re-audited for M4-M8 — see module-map.md "Deferred in this refresh"
  changelog.md                     —       (append-only; not versioned)

M8 T8-bis partial refresh (2026-09-10): only module-map.md, known-coupling-surfaces.md,
dependency-graph.md, and this file were re-verified against current code. The files
flagged "NOT re-audited" above predate M4 (content-scraper, enrichment-batcher,
vector-writer) and M7 (query-api, ui) landing and should not be trusted for those
services' surfaces. Landing gate: next project-architecture skill pass or M9 kickoff.
