# T8-bis — Backfill enable + verify-m8 (amendment-2)

**Plan:** m8-hardening-scale v1.3 · **Date:** 2026-09-10

## Chosen approach

- **`ADAPTER_REGISTRY` merge (`services/scraper/app/adapters/registry.py`):**
  merged all seven registered sources into one list — `ArxivAdapter`,
  `GitHubAdapter`, `HuggingFaceAdapter`, `LessWrongAdapter`,
  `OpenReviewAdapter`, `PapersWithCodeAdapter`, `SemanticScholarAdapter`.
  `LessWrongAdapter` is included: `T4-openreview-lesswrong.md` records a
  live GraphQL-over-GET probe that **succeeded** (2026-09-10), which is the
  condition the plan's context-map flag 3 gates registration on. Every
  merged adapter has both `fetch_manifest` and `fetch_content` (grepped
  before merge — none were missing either method), so the packet's
  "adapter missing `fetch_content`" kill criterion does not fire.

- **§18.4 backfill chunking (`services/scraper/app/loop.py`):** added
  `compute_backfill_chunk_starts(window_days, chunk_days, now)` — a pure
  function returning ascending `since` boundaries stepping `chunk_days` at a
  time back to `window_days` before `now` — and `_run_backfill_chunks`,
  which calls it, fetches+posts one manifest batch per boundary, and
  `await asyncio.sleep(BISHOP_BACKFILL_INTER_CHUNK_DELAY_SEC)` between
  chunks (not after the last one). `_scrape_adapter` branches into this path
  only when **both** `last_successful_run_at is None` (cold start — no
  scraper_state row yet for this source) **and** `BISHOP_BACKFILL_ENABLED`
  is true; otherwise it takes the pre-existing single-call incremental path
  unchanged. This keeps the change live on the one call path `main.py`'s
  existing scheduler already drives (`run_scheduler` → `scrape_cycle` →
  `_scrape_adapter`) without touching `main.py`, which is not in
  Files-to-touch.

  **Known limitation, stated plainly:** the frozen `SourceAdapter.fetch_manifest`
  interface takes `since` only, no `until` — every adapter fetches
  `[since, now]`, not `[since, chunk_end]`. So later chunk boundaries in the
  loop are strict supersets-minus-earlier-days of earlier ones, not
  disjoint windows; a naive read of "N days at a time" chunking would
  expect non-overlapping ranges, and this does not deliver that. What it
  does deliver, matching the two concrete claims in spec §18.4 ("fetch N
  days at a time, write to manifest, allow pre-filter to process before
  fetching the next chunk"): (1) manifest rows land in bounded,
  chunk-sized writes rather than one unbounded backfill-window write, and
  (2) a real inter-chunk pause (`BISHOP_BACKFILL_INTER_CHUNK_DELAY_SEC`,
  default 300s) between those writes so pre-filter has time to drain before
  the next POST. Re-fetched overlap is not eliminated; the state-worker's
  existing manifest insert path (already exercised by
  `test_scrape_cycle_rerun_reports_skipped_idempotent_rows`) dedupes by
  `source_id` and reports it as `skipped`, so overlap shows up as bandwidth
  and `skipped` count, not as duplicate rows or duplicate downstream work.

- **Positive drift: `tests/test_scraper_config.py` (8 new tests).** Not in
  T8-bis's Files-to-touch, but §2 Contract bindings names exact test IDs in
  this file for all three new env keys
  (`test_backfill_enabled_default_false`, `test_backfill_chunk_days_default`,
  `test_backfill_inter_chunk_delay_default`). T3 established the identical
  pattern in this same plan for `GITHUB_TOKEN`/`SEMANTIC_SCHOLAR_API_KEY`
  ("Positive drift: config.py and tests/test_scraper_config.py touched for
  §2 token rows omitted from packet files-to-touch" — T3 CHANGELOG entry).
  Followed that precedent rather than either fabricating a config-keys-only
  claim of compliance with no falsifying test, or halting on a scope gap
  the plan itself has already resolved once. Only additive test functions
  were added; no existing test in the file was changed.

- **New env keys (`services/scraper/app/config.py`):**
  `BISHOP_BACKFILL_ENABLED` (bool, default `False`), `BISHOP_BACKFILL_CHUNK_DAYS`
  (int, default `7`), `BISHOP_BACKFILL_INTER_CHUNK_DELAY_SEC` (int, default
  `300`). Added `_bool_from_env` (`"1"/"true"/"yes"/"on"` case-insensitive →
  `True`; anything else, including `"0"`, → `False`) since no bool-env
  helper existed on this module before.

- **`scripts/verify-m8.sh` + `tests/test_verify_m8.py`:** runs the full M8
  scraper adapter/registry/config/backfill pytest slice in one process (no
  `app`-package collision observed when run together — verified live before
  writing the script), then `scripts/run-g5-quality-gate.sh` (T7 wrapper,
  fixture-only by default), then `tests/test_g6_prefilter_gold.py`
  (structural, landed `eval/prefilter_v1`), then **only** the two G6
  enrichment **structural** test IDs
  (`test_g6_enrichment_template_schema`, `test_g6_enrichment_template_entry_slots`).
  It never references `test_g6_enrichment_manual_checklist` and never sets
  `BISHOP_G6_MANUAL` — both are asserted by `tests/test_verify_m8.py`
  falsifiers (`test_runs_g6_enrichment_structural_tests_only`,
  `test_does_not_export_g6_manual_flag`) so a future edit that
  reintroduces either would fail CI, not just review.

- **`docker-compose.yml`:** added the three backfill env keys and
  `GITHUB_TOKEN`/`SEMANTIC_SCHOLAR_API_KEY`/`HUGGINGFACE_TOKEN` to the
  scraper service block (all default to off/empty via `${VAR:-default}`
  interpolation, so a bare `docker compose up` behaves identically to
  before this change).

## Alternatives rejected

- **Bumping `docker-compose.yml` image tags to `bishop/scraper:m8` and
  `bishop/ui:m8`, per the plan's Naming contract row.** Rejected for *this*
  packet — `tests/test_compose.py::test_image_tags_use_milestone_convention`
  hardcodes a `milestone_tags` dict (one entry per service) that every
  prior milestone bumped in the **same** commit as its own compose tag
  change (T3→pre-filter-worker/batch-poller m3, T6→vector-writer m6,
  T8→query-api/ui m7, etc.). `tests/test_compose.py` is **not** in T8-bis's
  Files-to-touch. Bumping only `docker-compose.yml` breaks that test
  (verified live: 25/26 `test_compose.py` cases pass, only the tag-mapping
  case fails, cleanly isolated to the two changed lines); editing
  `tests/test_compose.py` without it being declared in Files-to-touch
  would violate the "no files outside Files-to-touch" hard prohibition in
  the other direction. Reverted both tag lines back to `m2`/`m7` rather
  than either breaking the existing test or touching an undeclared file.
  See **Items deferred** below for the landing gate.
- **Running `scripts/run-g6-enrichment-sampling.sh` directly from
  `verify-m8.sh`** instead of naming the two structural pytest IDs
  explicitly. Rejected — that wrapper's own manual-checklist branch is
  gated on `BISHOP_G6_MANUAL` from the **calling shell's** environment, not
  something the wrapper sets itself; naming the two structural test IDs
  directly in `verify-m8.sh` is one fewer indirection to audit for the
  "never sets `BISHOP_G6_MANUAL=1`" kill criterion, and keeps `verify-m8.sh`
  self-contained about exactly which G6 checks it runs.
- **Triggering backfill chunking unconditionally on every `scrape_cycle`
  tick, keyed only on `BISHOP_BACKFILL_ENABLED`** (not gated on
  `last_successful_run_at is None`). Rejected — spec §18.4's own framing
  ("fetch N days at a time... allow pre-filter to process before fetching
  the next chunk") describes a one-time catch-up operation, not a
  steady-state per-cycle behavior; re-running full-window chunked fetches
  on every scheduled tick (every `SCRAPER_SCHEDULE_INTERVAL_SEC`, default
  6h) would make ordinary incremental operation indistinguishable from
  backfill and defeat the point of the existing 7-day incremental window.
  Cold-start-only (`last_successful_run_at is None`) is the natural signal
  already present in `_scrape_adapter` and requires no new state-worker
  surface.
- **Adding an `until` parameter to `SourceAdapter.fetch_manifest` and all
  seven adapters** to get true disjoint-window chunking. Rejected — none of
  the seven adapter files are in T8-bis's Files-to-touch; this would be a
  signature change to modules this packet does not own, which the executor
  skill's hard prohibitions bar outright ("No interface drift... need a
  signature change elsewhere? HALT."). Flagged as a real limitation above,
  not silently absorbed.

## Assumptions made

- **`last_successful_run_at is None` is a reliable proxy for "this source
  has never completed a scrape cycle."** True at both `ScraperStateSnapshot`
  call sites in the existing code (`state-worker` only sets it after a
  successful `post_scraper_state`) and unchanged by this diff. If a future
  change starts clearing this field for reasons other than "never run" (a
  manual reset, say), the backfill branch would silently re-trigger a full
  chunked fetch on the next cycle for that source — a latent coupling, not
  something this packet introduces but worth flagging since backfill now
  keys off it.
- **The state-worker's manifest insert path dedupes by `source_id` and
  reports duplicates as `skipped` rather than erroring.** Not re-verified
  end-to-end in this packet (state-worker is out of Files-to-touch); relied
  on the existing `test_scrape_cycle_rerun_reports_skipped_idempotent_rows`
  falsifier in `tests/test_scraper_loop.py`, which already exercises this
  exact contract and stayed green through this diff unmodified.
- **`BACKFILL_CONFIG` (from `bishop_shared/scraper_config.py`, landed by
  T1-bis) has an entry for every source in `ADAPTER_REGISTRY`.** True today
  (verified by reading the module — all seven `SourceEnum` values are
  keyed). `_run_backfill_chunks` defensively falls back to `window_days=0`
  (a single now-only chunk) via `BACKFILL_CONFIG.get(...)` if a future
  adapter is registered without a matching `BACKFILL_CONFIG` entry, rather
  than raising `KeyError` mid-cycle.

## Items deferred

- **Compose image tag bump `scraper:m2→m8`, `ui:m7→m8` (plan Naming
  contract).** Deferred — see Alternatives rejected above for why this
  packet does not make the edit. **Landing gate:** a follow-up packet or
  plan §7 amendment that names both `docker-compose.yml` **and**
  `tests/test_compose.py` in Files-to-touch together, so the tag and the
  test's `milestone_tags` dict move in the same commit, matching every
  prior milestone's pattern.
- **Non-overlapping (disjoint-window) backfill chunking** would need an
  `until` parameter added to `SourceAdapter.fetch_manifest` across all
  seven adapters. Deferred — out of Files-to-touch for this packet (see
  Alternatives rejected). **Landing gate:** a future packet that
  explicitly lists the adapter interface file (`adapters/base.py`) and all
  seven adapter modules in Files-to-touch, if the re-fetch/bandwidth cost
  of the current overlapping-window approach proves material at live
  backfill scale.
- **`.dev/architecture/bishop/` refresh is partial, not exhaustive.** This
  packet refreshed `module-map.md`, `known-coupling-surfaces.md`,
  `dependency-graph.md`, `changelog.md`, and `INDEX.md` to reflect the
  current M8 (T2–T8-bis) code state. `public-interface-inventory.md`,
  `data-contract-registry.md`, `integration-seams.md`,
  `external-input-sources.md`, `architectural-patterns.md`,
  `open-questions.md`, and `architectural-decisions-divergence.md` were
  **not** re-audited for M4–M8 surfaces (content-scraper,
  enrichment-batcher, vector-writer, query-api, ui, and this packet's own
  adapter/backfill/quality-gate additions) and are explicitly flagged stale
  in `INDEX.md`. **Landing gate:** next `project-architecture` skill pass
  or M9 kickoff, whichever comes first.
- **G6 `challenge_hooks` quality debt (three kept rejects:
  `arxiv:2606.09483`, `arxiv:2608.14509`, `arxiv:2606.27330`).** Not this
  packet's to fix — explicitly out of scope per the plan's frozen-adjacent
  Call 1 prompt row. Landing gate already named upstream: follow-up ID
  `g6-call1-hooks-iteration` (post-M8).

## Charter G4/G5/G6 status consumed by this packet (not re-litigated)

- **G4** — live `INDEXED` corpus (97 rows, 2026-09-10). Not re-verified here
  (would require live DB access outside Files-to-touch); consumed as given
  per packet Resolved inputs.
- **G5** — T7's fixture bind (`tests/test_g5_quality_gate.py`), run via
  `scripts/run-g5-quality-gate.sh` in `verify-m8.sh`. Optional live gate
  (`BISHOP_G5_LIVE=1`) remains operator-invoked, not part of the default
  `verify-m8.sh` run.
- **G6** — assessed 7/10 in `.dev/quality/g6-enrichment-template.md` (all
  10 `value_rationale` accepted; three `challenge_hooks` rejects kept, per
  owner waiver dated 2026-09-10). This packet's preflight check confirmed
  10/10 non-empty `source_id`s and no `null` acceptance flags before
  proceeding, and did **not** flip any flag or edit
  `bishop_shared/enrichment_prompts.py` / `config/profiles/professional_v1.0.0.yaml`
  (verified: neither file appears in `git status --porcelain` for this
  diff).

## Files changed

- `services/scraper/app/adapters/registry.py` (rewritten — full 7-source merge)
- `services/scraper/app/loop.py` (backfill chunking added)
- `services/scraper/app/config.py` (3 new env keys + `_bool_from_env`)
- `docker-compose.yml` (scraper env additions only — tag bump deferred, see above)
- `scripts/verify-m8.sh` (new)
- `tests/test_verify_m8.py` (new)
- `tests/test_scraper_backfill_chunking.py` (new)
- `tests/test_scraper_config.py` (positive drift, not in Files-to-touch — extended with 8 new tests for the 3 new env keys, per §2 Contract bindings and T3 precedent; no existing test changed)
- `.dev/architecture/bishop/module-map.md`, `known-coupling-surfaces.md`,
  `dependency-graph.md`, `changelog.md`, `INDEX.md` (partial refresh, see
  Items deferred)
- `CHANGELOG.MD` (this entry)
- `.dev/decision-logs/m8-hardening-scale/T8-backfill-enable.md` (this file)

Note: `tests/test_scraper_loop.py` was **not** modified — the existing
seven tests in that file pass unmodified against the new `_scrape_adapter`
branch (verified live) because `BISHOP_BACKFILL_ENABLED` defaults `False`
and none of those tests set it.
