# Decision log — T1-bis: continuation of T1, shared cache-block and rubric-asset contract

**Plan:** prompt-caching v1.1.0 (amendment round 1) · **Tier:** architectural · **Subtask:** T1-bis

## Chosen approach

T1 was dispatched, implemented its full DoD, and HALTed at the last step — §2 row 9's own falsifier
(`tests/test_prompt_cache.py::test_no_inline_cache_control_literals`) failed because
`bishop_shared/enrichment_prompts.py::build_call2_system_prompt` (live production code on the Call 2
wire path, outside T1's and T1-bis's Files to touch, owned by T7's row-5 migration) already inlines a
`cache_control` literal. T1's HALT report offered three forks; the orchestrator resolved with **fork 2**:
move the row-9 sweep-test *verification* timing from T1 to T10 (post T5/T6/T7 landing), without touching
the test's text and without expanding T1/T1-bis's scope into T7's territory. That amendment is what
produced this packet (T1-bis).

T1-bis's job was narrow: consume T1's existing uncommitted working tree as-is (no rewrite), re-verify
every kill criterion T1 had already satisfied still holds, run the row-9 test and confirm it fails with
*exactly* the one expected offender (not zero, not a different one), and commit — because T2, T3, T4, T8,
T9 all hard-depend on this commit existing before they can start.

Concretely, this subtask:

- Verified `bishop_shared/prompt_cache.py` (`HAIKU_CACHE_MIN_TOKENS`, `CACHE_TTL`, `cached_system_blocks`)
  and `bishop_shared/rubric_assets.py` (`RubricDocument`, `resolve_rubric_path`, `load_rubric`,
  `compute_rubric_hash`, `verify_rubric_hash`) match §2 rows 1/1a/2/7 exactly, with their tests green.
- Verified `render_profile_prompt`'s new `include_output` kwarg (§2 row 3) defaults to `True` with a
  byte-identical render to the pre-change baseline (pinned by length + SHA-256 in
  `tests/test_profile_renderer.py`).
- Verified both Anthropic-batch Dockerfiles bake `config/prompts` (§2 row 16) by running a real
  `docker build` against `services/pre-filter-worker/Dockerfile` (exit 0, `COPY config/prompts` layer
  present) rather than trusting the Dockerfile text alone.
- Verified `docker-compose.yml` has no mount targeting `/app/config/prompts` (row 16's other half,
  covered by `test_no_prompts_bind_mount`).
- Verified the `anthropic>=0.100` floor is what's actually installed in this environment
  (`anthropic.__version__ == "0.100.0"`, matching A1's planning-time confirmation) and that
  `CacheControlEphemeralParam` exposes `ttl` (row 1a).
- Ran the row-9 test in isolation and confirmed it fails with **exactly one** offender —
  `bishop_shared\enrichment_prompts.py` — matching the packet's stated expectation precisely (not zero
  hits, not a different file).
- Ran the full declared suite (`pytest tests/ -m "not heavy"`) and diffed it against the same suite run
  on this subtask's own diff *stashed out* (see "Assumptions made" below) to separate this subtask's
  effect on the suite from pre-existing environment noise.
- Committed all Files-to-touch paths plus this decision log and the CHANGELOG entry.

## Adversarial test-coverage micro-pass (§2.1)

**Named gap:** T1's `scripts/rubric_hash.py` stamping path assumes exactly one `canonical_hash:` line
exists to rewrite in place (`re.subn(..., count=1)`, then `if count != 1: raise SystemExit(...)`). T1's
own tests (`test_stamp_and_verify_round_trip`) only exercise the happy path where the line is present but
holds the wrong value. A rubric asset missing the `canonical_hash` front-matter field entirely — a
realistic authoring mistake when hand-writing a new rubric annex before ever running the stamp script —
was uncovered.

**Falsifier added:** `tests/test_rubric_assets.py::test_rubric_hash_cli_exits_nonzero_when_canonical_hash_line_missing`,
invoking the real CLI subprocess (the actual call path an author or CI hook would use) against an asset
with no `canonical_hash:` line, asserting nonzero exit. Mutation-checked: temporarily short-circuited the
`if count != 1: raise SystemExit(...)` guard in `scripts/rubric_hash.py` to `if False and count != 1`,
re-ran the test, observed it fail (the guard's specific message assertion caught the mutation — the script
still exits nonzero via an unrelated downstream `ValueError`, but the named guard's own behavior is what
the test pins), then reverted the mutation and re-confirmed green. Full T1-bis test-module run after
revert: `tests/test_rubric_assets.py` + `tests/test_prompt_cache.py` + `tests/test_profile_renderer.py`
→ 39 passed, 1 expected-red (row 9).

## Alternatives rejected

- **Re-scope row 9's falsifier to exempt the legacy call site** (T1's fork 1): rejected by the orchestrator
  before this packet was even written — T1-bis's packet explicitly forbids editing the test body ("the
  test text is frozen as T1 originally wrote it; only its pass-requirement owner changed"). Not
  re-litigated here.
- **Expand T1-bis's Files-to-touch to migrate `enrichment_prompts.py` / `anthropic_batch_client.py` now**
  (T1's fork 3): rejected by the orchestrator for the same reason T1's HALT report flagged it — that
  surface is T7's row-5 ownership, and absorbing it here would pre-empt T7's own contract obligations
  (row-9 verification is explicitly split by timing, author vs. verifier). The packet names this rejection
  explicitly under its own Non-goals section; T1-bis did not revisit it.
- **Treat the full-suite's 86 failures as this subtask's problem to fix**: rejected. A stash/restore
  differential run (see Assumptions) showed 85 of 86 failures and all 14 errors reproduce identically on
  the pre-T1-bis baseline tree — they are a pre-existing test-isolation/import-pollution issue in
  `state-worker`/`vector-writer`/`query-api` test modules, unrelated to anything in this subtask's Files to
  touch. Silently "fixing" them here would be scope creep into modules this subtask never touches; per the
  executor skill's hard prohibitions, a pre-existing break is signal to report, not something to patch
  inline. Recorded here as a known environment condition, not remediated.

## Assumptions made

- **A1 (SDK ttl support)** — confirmed at execution time: `anthropic==0.100.0` is what's actually installed
  in this environment, and `CacheControlEphemeralParam.__annotations__` contains `ttl`. If a future
  `pip install` in a clean environment resolved a lower floor despite the `>=0.100` pin (e.g. a stale
  lockfile), row 1a's test (`test_sdk_supports_1h_ttl`) is the standing regression guard.
- **A5 (CRLF/LF stability)** — this Windows checkout's rubric-hash tests (`test_crlf_and_lf_body_yield_same_hash`,
  `test_crlf_asset_on_disk_hashes_same_as_lf_asset`) pass, confirming `_normalize()`'s LF normalization
  holds on this host. Not re-derived here; inherited from T1's implementation, spot-checked green.
- **A7 (no compose bind mount over `/app/config/prompts`)** — confirmed by `test_no_prompts_bind_mount`
  parsing the live `docker-compose.yml`; also confirmed procedurally by the `docker build` run, which
  shows `config/prompts` populated from the image `COPY` layer (there is no compose service definition yet
  binding that path, since no rubric-consuming service change has landed).
- **Differential-suite method is valid evidence for "the other 85 failures pre-exist"**: this rests on a
  `git stash push -u` / `git stash pop` round-trip of exactly this subtask's Files-to-touch set, run twice
  (baseline tree: 85 failed / 723 passed / 14 errors; T1-bis tree: 86 failed / 743 passed / 14 errors — a
  net +1 failed / +20 passed, matching exactly the 20 new tests in `test_prompt_cache.py` +
  `test_rubric_assets.py` + the 3 new `test_profile_renderer.py` tests minus the 1 expected-red row-9 test).
  The stash/pop was verified restored via `git status --porcelain` before continuing. If this assumption is
  wrong — if some of those 85 failures were in fact caused by an interaction with this subtask's own
  changes that the stash didn't fully isolate — the evidence trail here (both raw counts, both terminal
  outputs) lets a future reader re-derive the same diff and check.

## Items deferred

- **Row 9 verification (green)** — deferred to **T10**, by explicit amendment. T1-bis's own scope ends at
  authoring the test and confirming it is red with exactly the one named, expected offender. T10 re-runs
  `tests/test_prompt_cache.py::test_no_inline_cache_control_literals` after T5/T6/T7 land and asserts zero
  offenders remain (per §2 row 9's amendment banner). Landing gate: T10's own closure sweep.
- **Pre-existing full-suite noise (85 failed / 14 errors, unrelated to this plan)** — not this subtask's
  scope to fix (none of the failing modules are in Files to touch). Landing gate: none named by this plan;
  this is inherited repo debt outside prompt-caching's scope, flagged here so a future reader does not
  mistake it for regression introduced by T1-bis. No follow-up ID assigned — outside this plan's charter.
- **Key A / mixed provenance (row 17, A7's sibling risk)** — not this subtask's concern; tracked as
  `FU-CACHE-MOUNT-01` per §2 row 17 in the plan, owner = operator. T1-bis did not touch this.
- **Spec staleness (`bishop_spec_0_6.md` §12.1/§12.3)** — per D6 / row 23, explicitly out of scope for
  every subtask in this plan including this one. Not touched, not banner-annotated (the file itself is
  frozen — row 20 — and untouched by this commit).
