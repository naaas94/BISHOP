# T1 brief

**Subtask ID:** T1  
**Status:** halted

## HALT Report — T1

- **Subtask ID:** T1

- **HALT reason:** `Implementation needs files outside Files to touch` (compounded by `Existing tests break and the break is not clearly because the test was wrong (vs. your correct change)` and `You find coupling to another subtask [or untouched baseline] the DAG did not declare`).

- **What you discovered:**
  The packet's Scope requires: *"Update ArXiv adapter to consume shared `BACKFILL_CONFIG` for window resolution."* `BACKFILL_CONFIG` is contract-bound (§2) to be populated *"per §18.2 (all seven source keys)"* of `bishop_spec_0_6.md`, which pins `arxiv: BackfillConfig(window_days=60, categories=["cs.AI", "cs.CL", "cs.LG"])`.

  The window-resolution function is `resolve_effective_since()` in `services/scraper/app/adapters/arxiv.py` — it currently falls back to `app.config.ARXIV_BACKFILL_WINDOW_DAYS` (default `7`, an M2-era placeholder) when `since` is `None`. Rewiring it to `BACKFILL_CONFIG["arxiv"].window_days` (per spec, `60`) changes its numeric output.

  `tests/test_scraper_arxiv_adapter.py::test_resolve_effective_since_uses_backfill_window` pins the old value exactly:

  ```
  def test_resolve_effective_since_uses_backfill_window() -> None:
      arxiv = _load_arxiv_stack()
      now = datetime(2026, 6, 12, 12, 0, 0, tzinfo=UTC)
      resolved = arxiv.resolve_effective_since(None, now=now)
      assert resolved == datetime(2026, 6, 5, 12, 0, 0, tzinfo=UTC)  # exactly now - 7 days
  ```

  Baseline pytest of that test passed (2 passed). Wiring the adapter to `BACKFILL_CONFIG["arxiv"].window_days = 60` would break the 7-day assertion.

- **Files-to-touch conflict (exact paths):**
  - Required by Scope: `services/scraper/app/adapters/arxiv.py` (in Files-to-touch)
  - Blocking, **not** in Files-to-touch: `tests/test_scraper_arxiv_adapter.py`
  - T1 declared Files-to-touch: `bishop_shared/scraper_config.py`, `services/scraper/app/rate_limit.py`, `services/scraper/app/config.py`, `services/scraper/app/adapters/arxiv.py`, `tests/test_scraper_config_shared.py`, `tests/test_scraper_rate_limit.py`, `tests/test_scraper_config.py`, `CHANGELOG.MD`, `.dev/decision-logs/m8-hardening-scale/T1-adapter-foundation.md`

- **Partial work:** None. No files created or modified.

- **Files changed:** none
- **Tests run + result:** `pytest tests/test_scraper_arxiv_adapter.py -k resolve_effective_since -v` → 2 passed (baseline, read-only)
- **Commit SHA:** not committed — HALT before first edit
- **Changelog entry location:** none
- **Decision log path:** none (not written)
- **Kill-criterion evidence:** HALT fired on Files-to-touch / existing-test coupling; no T1 code landed
- **Summary:** T1 stopped before edits because consuming `BACKFILL_CONFIG["arxiv"].window_days=60` for `resolve_effective_since` would break an unlisted baseline test that pins 7 days.
