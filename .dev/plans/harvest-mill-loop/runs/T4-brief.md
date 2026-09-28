**Subtask ID:** T4 · **Status:** complete

**Files changed:** `CHANGELOG.MD`, `harvest-pool-next.md`, `product-backlog.yaml`, `tests/test_product_backlog.py` (§2.2)

**Tests run + result:** `pytest tests/test_product_backlog.py tests/test_scraper_loop.py tests/test_scraper_config.py tests/test_harvest_github.py -q` → **57 passed**. Mutation-checked falsifiers: `test_pb011_is_shipped`, `test_pb012_status_remains_deferred`, `test_harvest_pool_next_status_no_longer_hitchhiker`, `test_changelog_t4_mill_bullet_is_in_exactly_one_dated_section` (each failed under mutation, then reverted).

**Commit SHA:** `dc90d83518402c87059c7144633d512369895e30`

**Changelog entry location:** `CHANGELOG.MD` → `## harvest-mill-loop — 2026-09-17` (T4 bullet)

**Decision log path:** n/a (standard tier). Cross-link target (T3 input): `.dev/decision-logs/ops/harvest-mill-loop.md`

**Kill-criterion evidence:**
- `config/harvest/economics.yaml` is absent from `git show --stat HEAD` (not in this commit; not staged).
- PB-012 `status` remains `deferred` (`test_pb012_status_remains_deferred`; mutation to `shipped` failed, then reverted).
- T4 mill-loop marker appears in exactly one dated section (`test_changelog_t4_mill_bullet_is_in_exactly_one_dated_section`; injecting it under `harvest-pool` failed, then reverted).

**Summary:** Closeout only — no mill/scraper code edits. Pickup status/next/cadence now describe `_mill_loop` as landed and uncoupled from `BISHOP_SCRAPER_SCHEDULE_INTERVAL_SEC`, with a cross-link to the T3 decision log; the PB-011 deferred bullet is gone (PB-012 / paper / mechanical-drops bullets left byte-identical); PB-011 is `shipped`. Interval is not described as a `.env`/compose knob. Deferred: `AGENTS.md` still says PB-011 is next code (out of files-to-touch; landing gate = auditor-review).
