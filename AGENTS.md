# Agent entry

Bishop is a local-first ingest pipeline (scrape → pre-filter → enrich → index → query). The README is M0 compose only.

## Windows file tools (Cursor Write)

This host is Windows. Rule: `.cursor/rules/windows-file-tools.mdc`. Use **forward slashes** (prefer workspace-relative paths). Never backslash-escape `Write` / `StrReplace` paths — that truncates the call at `path`. Large files: skeleton Write, then `StrReplace` in sections.

## SQLite (read this first if you need data)

- Rule: `.cursor/rules/bishop-sqlite.mdc`
- Ops note: `.dev/sqlite.md`
- Live DB: `${BISHOP_DATA_ROOT}/sqlite/bishop.db` — this host `C:/Users/Ale/bishop_data/sqlite/bishop.db`
- Single writer: `state-worker`. Query read-only. There is no `processed` column.

## Operator UI

- Rule: `.cursor/rules/bishop-ui.mdc`
- Folder: `.dev/ui/` (index `README.md`, live map `agent-reference.md`)
- Host: `http://localhost:8081`. Query-api only; templates/CSS are baked into `bishop/ui:m8` (rebuild after edits).
- Landing page is `/dashboard` (`GET /stats/overview`). Architecture folder still says `/batches` — trust `.dev/ui/`.

## Source notes (taste + intel)

- Folder: `config/source-notes/` — one file per adapter. Read the source’s file before changing fetch, window, shape law, or overlay.
- Rule: `.cursor/rules/bishop-source-notes.mdc`
- These notes are **not** a second profile pin and **not** per-source routing. One gate-1 pin until an eval earns a split.
- GitHub pickup: `repo-gate-next.md`. GitHub stamps/intel: `eval/github_repo_gate_v0/` + `config/source-notes/github.md`.
- Harvest pool pickup: `harvest-pool-next.md`. Decision log: `.dev/decision-logs/ops/harvest-pool-first-landing.md`. Sidecar `${BISHOP_DATA_ROOT}/harvest/ledger.sqlite` (not `bishop.db`). Next is PB-011 mill loop, not cutover.

## MCP / agent tool (not built)

- Notes: `mcp-agent-tool-notes.md` (v1 read-only wrap of query-api search / get_entry / recent)
- Write-up: `.dev/decision-logs/ops/mcp-consumer-extraction.md` — consumers extract and apply; Bishop does not. PB-010.
- Do not treat MCP as a write surface into SQLite or the VDB.

## Eval / relevance calibration

- Shared-gate gold: `eval/prefilter_v0/` (`contract.json`, `items.json`, `labels.json`)
- Suggested (not gold): `eval/prefilter_v0/suggested.json`
- Profile under test for that gold set: `config/profiles/professional_v1.0.0.yaml`
- Live overlay pin: `config/profiles/professional_v1.2.0_soft_launch.yaml`
- GitHub quality spotcheck (not a second gold set): `eval/github_repo_gate_v0/`
- Do not bump the profile or scrape a new live batch until replay metrics exist for a labeled slice.
- Cross-source operator log: `relevance_log.md`

## Architecture (stale after 2026-07-13 — verify against code)

`.dev/architecture/bishop/` — module map, contracts, couplings. Flag drift; do not silently “fix” the folder.
