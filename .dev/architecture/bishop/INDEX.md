Project:          bishop
Purpose:          Local-first knowledge intelligence pipeline — SQLite state kernel, seven-source discovery and content scrape, Anthropic pre-filter/enrichment batches with cached system prefixes, LanceDB/DuckDB/BM25 indexing, query API, UI.
Primary language: Python 3.12
Key frameworks:   FastAPI, uvicorn, Pydantic, Alembic, aiosqlite, httpx, anthropic, PyYAML, sentence-transformers, LanceDB, DuckDB, rank-bm25, Docker Compose, pytest
Repository:       c:\Users\Ale\Documents\Repos\BISHOP
Document version: 1.8.0
Last constructed: 2026-06-10
Last verified:    2026-09-16
Stale after:      2026-10-16

Files:
  module-map.md                    1.5.0   2026-09-13
  public-interface-inventory.md    1.4.0   2026-09-13
  data-contract-registry.md        1.3.0   2026-09-13
  dependency-graph.md              1.5.0   2026-09-13
  integration-seams.md             1.3.1   2026-09-16
  external-input-sources.md        1.4.1   2026-09-16
  architectural-patterns.md        1.0.3   2026-09-13   candidates only — pending user confirmation
  failure-taxonomy.md              1.0.0   2026-06-10   verified no drift; cause classes still pending owner confirmation
  known-coupling-surfaces.md       1.7.0   2026-09-16
  open-questions.md                1.7.0   2026-09-16
  changelog.md                     —       (append-only; not versioned)

Sidecar (not in the project-architecture file schema): `architectural-decisions-divergence.md` — execution-time spec drift log; updated 2026-09-13.

2026-09-16 MCP consumer/extraction split (PB-010): documented, no code. See `.dev/decision-logs/ops/mcp-consumer-extraction.md`. `open-questions.md` 1.7.0.

2026-09-16 ingest-content-risk seed (OPEN-023): documented untrusted public text through LLM gates and UI; no code change. See `.dev/decision-logs/ops/ingest-content-risk-seed.md`. `failure-taxonomy.md` still has no cause classes (owner names not minted).

2026-09-13 landing-gate refresh: completed the 2026-09-10 M8 T8-bis deferred re-audit of M4–M8 surfaces and folded prompt-caching (2026-09-12), the soft-launch precision overlay (2026-09-11), sqlite snapshot/integrity/named-volume ops, and the T12 scraper/ui m8 image-tag bump. `failure-taxonomy.md` was verified and left unchanged.
