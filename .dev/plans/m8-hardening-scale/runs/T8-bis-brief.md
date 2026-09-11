# T8-bis brief

**Subtask ID · Status:** T8-bis · **complete**

- **Files changed:**
  - `services/scraper/app/adapters/registry.py` — merged all 7 sources (ArXiv, GitHub, HuggingFace, LessWrong, OpenReview, PapersWithCode, Semantic Scholar) into `ADAPTER_REGISTRY`
  - `services/scraper/app/loop.py` — `compute_backfill_chunk_starts` + `_run_backfill_chunks`; `_scrape_adapter` branches into chunked backfill only when cold-start (`last_successful_run_at is None`) **and** `BISHOP_BACKFILL_ENABLED`
  - `services/scraper/app/config.py` — `BISHOP_BACKFILL_ENABLED`/`BISHOP_BACKFILL_CHUNK_DAYS`/`BISHOP_BACKFILL_INTER_CHUNK_DELAY_SEC` + `_bool_from_env`
  - `docker-compose.yml` — scraper env additions (backfill knobs + `GITHUB_TOKEN`/`SEMANTIC_SCHOLAR_API_KEY`/`HUGGINGFACE_TOKEN`); image-tag bump to `m8` **deferred** (see below)
  - `scripts/verify-m8.sh`, `tests/test_verify_m8.py` — new M8 gate (adapter+loop+backfill pytest, G5 fixture, G6 structural-only; never sets `BISHOP_G6_MANUAL`)
  - `tests/test_scraper_backfill_chunking.py` — new, 7 tests
  - `tests/test_scraper_config.py` — 8 new tests (positive drift, following T3's precedent for the same file)
  - `.dev/architecture/bishop/{module-map,known-coupling-surfaces,dependency-graph,changelog,INDEX}.md` — partial refresh for M4–M8 drift
  - `CHANGELOG.MD`, `.dev/decision-logs/m8-hardening-scale/T8-backfill-enable.md`

- **Tests run:** Full scraper adapter/loop/config/backfill/verify-m8/compose/G5/G6-structural slice — 134 passed, 2 skipped (expected: LessWrong live probe, G6 manual checklist), 1 deselected (G5 heavy live). `tests/test_scraper_loop.py`'s 7 pre-existing tests pass unmodified.

- **Commit SHA:** `43a8bc4` ("T8-bis: merge ADAPTER_REGISTRY (7 sources), land backfill chunking, verify-m8") — scoped path-list commit; pre-existing staged/unstaged files from before this run (plan/packet files, `g6-enrichment-template.md`) were left untouched.

- **Changelog entry location:** `CHANGELOG.MD` under `## m8-hardening-scale — 2026-09-10`

- **Decision log path:** `.dev/decision-logs/m8-hardening-scale/T8-backfill-enable.md`

- **Kill-criterion evidence:**
  - G6 preflight (≥10 filled slots, no null flags): confirmed by reading the template before touching code — not fired.
  - "Halt if setting the 3 hook rejects true / editing prompts": did neither — `git diff` shows no touch to `enrichment_prompts.py`/`professional_v1.0.0.yaml`/the template.
  - "Halt if any T2–T4 adapter missing `fetch_content`": grepped all 6 adapters before merging — all present.
  - "Halt if `verify-m8.sh` exports `BISHOP_G6_MANUAL=1`": asserted negatively by `test_does_not_export_g6_manual_flag`, passing.
  - "Halt if `BISHOP_BACKFILL_ENABLED=1` in compose without chunking landed": chunking landed in the same commit; compose defaults the flag to `0`.
  - Frozen-adjacent paths: `git diff 5e04833... -- <14 paths>` empty, both before and after this diff.

- **Summary:** T8-bis merges the six remaining scraper adapters into a single `ADAPTER_REGISTRY` (including `LessWrongAdapter`, whose live probe succeeded per T4's decision log), lands §18.4 chunked backfill that only activates on a source's first-ever scrape when `BISHOP_BACKFILL_ENABLED=1`, and adds `scripts/verify-m8.sh` as a structural-only M8 gate that respects the G6 owner waiver. One contract line — bumping compose image tags to `scraper:m8`/`ui:m8` — was deliberately **not** done: it would break `tests/test_compose.py`, which isn't in this packet's Files-to-touch, so it's recorded as a deferred item with a named landing gate (a follow-up packet naming both files together) rather than silently fixed or force-committed.
