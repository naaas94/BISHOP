# T6 — Enrichment Call 1 wiring (cache key B)

**Plan:** prompt-caching v1.2.0 · **Tier:** architectural · **Depends on:**
T1-bis (`8d9af01`), T3 (`c6d9f80`)

## Chosen approach

Converted `bishop_shared/enrichment_prompts.py::build_call1_system_prompt` from
returning a plain `str` to returning a two-block `list[dict[str, object]]`:
block 0 is the schema/taxonomy instruction text (byte-identical to the
pre-caching string — verified by diff, not just by test), block 1 (last) is
the `call1_rubric_v1.md` annex body. Both blocks are produced by
`cached_system_blocks()` (T1-bis), which is the only place a `cache_control`
literal is written — this function calls `load_rubric(resolve_rubric_path(
"call1_rubric")).body` directly (no hash verification at this call site; see
"Alternatives rejected" below for why).

`services/enrichment-batcher/app/anthropic_batch_client.py::AnthropicBatchClient.
build_requests` needed **no signature change** — contract row 5 pins it at
`(*, entries: list[Stage1BatchEntry])` — because it already called
`build_call1_system_prompt()` internally and assigns whatever it returns
straight into `params["system"]`. Renamed the local variable
`system_prompt` → `system_blocks` for readability; this is the only edit to
that file.

Gave stage 1 a rubric hash-or-abort path it did not have (row 12/13).
`stage1_loop.py::_verify_rubric_hash` mirrors pre-filter's
`_verify_rubric_hash` (load, recompute, compare) but stops at `logger.error`
— no `logger.critical` / CRITICAL alert — preserving the row 12 asymmetry
inherited from the M5 T4 deferral (only pre-filter alerts; stage 1 and stage
2 log only). `stage1_cycle` gained an optional `rubric_path: Path | None =
None` kwarg mirroring the existing `profile_path` override, resolved via
`rubric_path or resolve_rubric_path("call1_rubric")`. The check is placed
right before the (pre-existing) G3 check, after the min-batch/hold gate, so a
mismatch aborts with the same discipline already established for the G3
abort: a plain early `return` that leaves `_pending_entries` and
`_hold_started_at` untouched, so a persistent mismatch cannot push the hold
deadline forward and starve the gate (C9).

`_profile_render_hash` is byte-for-byte unchanged — still
`load_profile(path).canonical_hash`, no recompute — per row 13's explicit
kill criterion. Added a regression test asserting this directly, plus a
guard asserting `stage1_loop` does not import `compute_profile_hash` at all
(the specific symbol a future recompute would need).

## Alternatives rejected

- **Threading rubric verification (and its returned body) into
  `build_call1_system_prompt` via a parameter, then having `stage1_loop`
  pass the verified body down into `build_requests`.** Rejected: row 5 pins
  `build_requests`'s signature to `entries` only — there is no channel to
  pass a verified body through it. The two call sites (the loop's
  hash-or-abort gate, and the builder's own text assembly) therefore load
  the rubric file independently. This is a small, accepted duplication (one
  extra file read per batch build) forced by the frozen signature, not an
  oversight — the abort gate's job is to refuse to submit, not to hand the
  builder its text.
- **Giving `build_call1_system_prompt` a `rubric_path` override parameter
  for testability.** Considered, but `build_requests`'s frozen signature
  means production code can never pass an override through anyway — the
  parameter would only exist for tests, which is exactly what
  `monkeypatch.setattr(rubric_assets_mod, "PROMPTS_CONTAINER_DIR", ...)`
  already achieves without adding an unused-in-production parameter to a
  builder function. Chose the monkeypatch fixture instead (added as an
  autouse fixture in both `tests/test_enrichment_prompts.py` and
  `tests/test_enrichment_batcher_stage1_loop.py`), which also matches the
  Windows dev-machine reality that `/app/config/prompts` resolves to
  `C:\app\config\prompts` and does not contain the baked rubric assets
  outside the Docker image.
- **A single combined integration test importing the real
  `app.stage2_loop` module to prove the `asyncio.gather` risk mitigation.**
  Rejected after a first attempt: importing `app.stage2_loop` after
  `_load_enrichment_batcher_stack()` has already restored `sys.path` /
  `sys.modules` either fails or silently creates a second, disconnected
  `app.stage1_loop` module instance (stage2_loop's own `from
  app.stage1_loop import ensure_g3_verified` triggers a fresh import). The
  risk this test needs to prove — that stage 1's abort is a plain `return`,
  not a raise, so it cannot cancel a sibling `asyncio.gather` task — does
  not require the real stage2 module at all. Used a trivial stand-in
  coroutine gathered alongside the real `stage1_cycle` instead; it exercises
  the actual `asyncio.gather` semantics this risk is about without the
  fragile double-import.

## Assumptions made

- **The rubric file read inside `build_call1_system_prompt` and the hash
  verification inside `stage1_loop._verify_rubric_hash` reading the same
  file twice per batch is an acceptable cost.** If this ever needs to become
  a single read (e.g. for a future perf pass), the signature freeze on
  `build_requests` (row 5) would need to be relaxed first — that is an
  orchestrator-level contract change, not something this subtask can do
  unilaterally.
- **T3's `call1_rubric_v1.md` heading text ("Call 1 Extraction Rubric —
  Annex") is stable enough to use as a test fixture-free assertion anchor**
  (`test_call1_system_is_two_block_list_with_rubric_annex_last`). If T3's
  annex is ever re-authored with a different heading, that one assertion —
  not the hash-or-abort logic — would need updating; it does not gate
  behavior.
- **Row 9's "single emitter" test staying red is expected, not a regression
  introduced here.** Confirmed by diff: the sole offender
  (`build_call2_system_prompt`'s inline `cache_control` literal) is
  untouched by this subtask; verified the full-suite failure/error counts
  are identical with and without this diff (88 failed / 14 errors both
  ways), with exactly this subtask's 10 new tests as the only net-new
  passes.

## Items deferred

- **Row 9 ("single emitter") closure.** Not this subtask's scope —
  `build_call2_system_prompt` is T7's file-section to migrate. Landing gate:
  **T10**, which re-runs `tests/test_prompt_cache.py::
  test_no_inline_cache_control_literals` after T7 lands and expects it
  green.
- **Row 8 (token-floor proof for the wired key-B prefix).** T3's decision
  log already measured the annex body (4,619 `cl100k_base` tokens) and the
  pre-wiring schema/taxonomy text (267 tokens) separately, estimating a
  combined prefix of 4,886 tokens — above the 4,506 target. This subtask
  does not re-measure the now-actually-wired prefix with a dedicated
  point-literal test; that is **T10**'s row-8 closure gate
  (`tests/test_prompt_cache_token_floor.py`), not a T6 file.
- **Live confirmation that Anthropic actually caches key B**
  (`cache_creation_input_tokens > 0` from a real batch). Named in row 8 as a
  semantic gap no proxy-tokenizer test can close; T8's poller observability
  fields make this checkable once T10/G1 run against a live batch. Not this
  subtask's scope.
- **The duplicated rubric-file read** (see Assumptions) is not optimized in
  this subtask. No landing gate named — flagged, not silently accepted, in
  case a future perf-focused subtask needs to know why the read happens
  twice per batch.
