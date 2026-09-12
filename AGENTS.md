# Agent entry

Bishop is a local-first ingest pipeline (scrape → pre-filter → enrich → index → query). The README is M0 compose only.

## SQLite (read this first if you need data)

- Rule: `.cursor/rules/bishop-sqlite.mdc`
- Ops note: `.dev/sqlite.md`
- Live DB: `${BISHOP_DATA_ROOT}/sqlite/bishop.db` — this host `C:/Users/Ale/bishop_data/sqlite/bishop.db`
- Single writer: `state-worker`. Query read-only. There is no `processed` column.

## Eval / relevance calibration

- Gold set: `eval/prefilter_v0/` (`contract.json`, `items.json`, `labels.json`)
- Suggested (not gold): `eval/prefilter_v0/suggested.json`
- Profile under test: `config/profiles/professional_v1.0.0.yaml`
- Do not bump the profile or scrape a new live batch until replay metrics exist for a labeled slice.

## Architecture (stale after 2026-07-13 — verify against code)

`.dev/architecture/bishop/` — module map, contracts, couplings. Flag drift; do not silently “fix” the folder.
