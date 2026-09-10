# T1-bis — Adapter foundation (amendment-1)

**Plan:** m8-hardening-scale · **Date:** 2026-09-10

> Continuation of halted T1 (T1 produced no artifacts). Lands the T1-bis slice
> only: `BackfillConfig` / `BACKFILL_CONFIG` / `SOURCE_RATE_LIMITS` (all seven
> sources) / `SOURCE_SCHEDULE_INTERVAL_SEC`. T2–T4 adapters, T8
> `ADAPTER_REGISTRY` and backfill env keys are out of scope here.

## Chosen approach

- **New module `bishop_shared/scraper_config.py`:** frozen `BackfillConfig`
  dataclass (`window_days: int`, `categories: tuple[str, ...] = ()`) plus
  `BACKFILL_CONFIG: dict[str, BackfillConfig]` keyed by `SourceEnum.value` for
  all seven sources, populated from spec §18.2 verbatim (`arxiv=60` with
  `("cs.AI", "cs.CL", "cs.LG")`, `github=30`, `semantic_scholar=60`,
  `huggingface=30`, `paperswithcode=60`, `openreview=90`, `lesswrong=30`).
  Also `SOURCE_SCHEDULE_INTERVAL_SEC: dict[str, int]` from the Appendix B
  "Default scraper schedules" table, converted to seconds.
- **Expanded `services/scraper/app/rate_limit.py::SOURCE_RATE_LIMITS`:** added
  the remaining six sources' `RateLimit` rows verbatim from Appendix B
  ("Source Rate Limit and Schedule Reference") — github (5000/1hr, linear, 5
  retries), semantic_scholar (100/1s, exponential, 3), huggingface (50/1s,
  exponential, 3), paperswithcode (20/1s, exponential, 3), openreview (10/1s,
  exponential, 3), lesswrong (5/1s, exponential, 3). ArXiv's existing row is
  unchanged.
- **Flag 4 (binding):** `arxiv.py` and `app/config.py` were left **byte
  unchanged**. `resolve_effective_since(since=None)` still reads
  `ARXIV_BACKFILL_WINDOW_DAYS` (default 7) from `app/config.py`; nothing in
  this diff wires `BACKFILL_CONFIG["arxiv"].window_days=60` into that path.
  Added a falsifier test,
  `tests/test_scraper_arxiv_adapter.py::test_backfill_config_and_incremental_window_stay_independent`,
  that imports both constants side by side and asserts they stay 60 and 7
  respectively while calling the real `resolve_effective_since`. Mutation-
  checked: inlining `60` into `resolve_effective_since`'s fallback branch
  fails both this test and the pre-existing
  `test_resolve_effective_since_uses_backfill_window`; reverted after
  confirming the failure (`git diff` on `arxiv.py` is empty post-revert).
- **`apply_category_gate` / category-gate config:** not touched. No import,
  no wiring change in this diff — `arxiv.py`, `bishop_shared/source_config.py`,
  and `config/sources/arxiv.yaml` are frozen-adjacent and untouched (verified
  `git diff 5e048337b9b7262c604dfce04f3e565d33cf0f4a -- <frozen paths>` is
  empty for all of them, this subtask's diff included).

## Alternatives rejected

- **Wire `BACKFILL_CONFIG["arxiv"].categories` into `arxiv.py`'s
  `build_search_query` call, replacing `ARXIV_CATEGORIES`:** Rejected — the
  packet's flag 4 permits this ("ArXiv may import `BACKFILL_CONFIG` without
  replacing the incremental 7-day path") but does not require it, and doing
  so pulls `arxiv.py` into this diff for a value that is already identical
  (`("cs.AI", "cs.CL", "cs.LG")`) with zero behavior change today. Deferred to
  whichever subtask (T8) actually switches the incremental path to consume
  `BACKFILL_CONFIG` under `BISHOP_BACKFILL_ENABLED`; keeping `arxiv.py`
  untouched here minimizes surface area and keeps the frozen-adjacent-path
  audit trivial (empty diff).
- **Put `SOURCE_SCHEDULE_INTERVAL_SEC` in `services/scraper/app/config.py`
  instead of `bishop_shared`:** Rejected — contract bindings (§2) name
  `bishop_shared/scraper_config.py` explicitly, and the existing
  `app/config.py::SCRAPER_SCHEDULE_INTERVAL_SEC` is a *global* env-backed
  scalar consumed by `app/main.py`'s sleep loop; conflating it with a
  per-source dict under the same name would be a breaking rename outside
  Files-to-touch discipline (`app/main.py` is not in Files-to-touch).

## Assumptions made

- Appendix B's "1hr" period for GitHub is 3600 seconds and "1s" periods for
  the other five sources are 1 second — read literally, no rounding.
- Appendix B's per-source schedule cadences ("Every 6 hours" / "Every 12
  hours" / "Every 24 hours") map 1:1 to `SOURCE_SCHEDULE_INTERVAL_SEC`; no
  per-source env override exists yet (T8/T2-T4 scope if needed later).
- `SourceEnum.value` strings are the correct and only key space for both new
  dicts — verified against `bishop_shared/enums.py` (arxiv, semantic_scholar,
  huggingface, paperswithcode, github, openreview, lesswrong) and asserted by
  `test_backfill_config_matches_spec_defaults` / `test_schedule_defaults` /
  `test_all_source_rate_limits_match_appendix_b` (`set(...) == {member.value
  for member in SourceEnum}`).

## Items deferred

- **Wiring `BACKFILL_CONFIG` and `SOURCE_SCHEDULE_INTERVAL_SEC` into runtime
  code** (scraper loop, per-source scheduler, backfill chunking): T8, behind
  `BISHOP_BACKFILL_ENABLED` / chunk env keys. This subtask only lands the
  typed config and its tests.
- **`ADAPTER_REGISTRY` expansion and per-adapter `SOURCE_RATE_LIMITS` lookups
  at call time** for huggingface/paperswithcode/semantic_scholar/
  github/openreview/lesswrong adapters: T2–T4 (adapters) and T8 (registry).
  `SOURCE_RATE_LIMITS` now has all seven keys so those subtasks will not hit
  a `KeyError` when they wire `self.rate_limit = SOURCE_RATE_LIMITS[...]` for
  their adapter's `SourceEnum` value (per Filtered 5.4 coupling row).
