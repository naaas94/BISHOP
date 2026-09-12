# T9-bis — batch amortization, minimum volume and maximum hold

**Plan:** prompt-caching · **Amendment:** round 2 (v1.2.0) · **Supersedes:** T9 (HALTed, no code landed)

## Chosen approach

Each of the three Anthropic batch loops (`prefilter_cycle`, `stage1_cycle`, `stage2_cycle`) now
holds entries claimed from state-worker in an in-process, module-level buffer
(`_pending_entries: list[object]`) across polling cycles, instead of submitting whatever a single
poll returns. A cycle only proceeds to Anthropic submission once the buffer's size reaches the
gate's `*_MIN_BATCH_SIZE`, or once `*_MAX_HOLD_MINUTES` has elapsed since the first entry in the
current hold window arrived (`_hold_started_at`, a `time.monotonic()` timestamp captured through
an indirection function `_now()` so tests can inject a fake clock).

The hold-start timestamp is set exactly once per accumulation window — when `_pending_entries`
transitions from empty to non-empty — and is only cleared (reset to `None`, buffer cleared) once
an Anthropic submission is actually *attempted* (whether Anthropic accepts or fatally rejects the
batch). Any earlier return path (empty poll, unsupported domain, rubric/profile hash-mismatch
abort, closed G3 gate, missing-summary abort in stage 2) leaves both the buffer and the timestamp
untouched. This is deliberate: it is what makes the maximum-hold deadline **reachable** even when
every submission attempt keeps failing the same way (kill criterion 1), and it is what stops a
hash-or-G3 abort from **extending** the deadline indefinitely (kill criterion 2 / coupling C9) —
since the abort branch never touches `_hold_started_at`, a second, third, or Nth abort all measure
elapsed time from the same original arrival, not from the moment of the latest failed attempt.

Config: nine new env-backed keys, three per gate, added to each service's existing
`_int_from_env`-based `config.py` (no new parsing idiom, no `getattr` defaults):

| Gate | Batch size (existing → new default) | Min batch size (new) | Max hold minutes (new) |
|---|---|---|---|
| Pre-filter | 50 (unchanged) | `BISHOP_PREFILTER_MIN_BATCH_SIZE` = 25 | `BISHOP_PREFILTER_MAX_HOLD_MINUTES` = 120 |
| Enrichment stage 1 | 10 → 50 | `BISHOP_ENRICHMENT_STAGE1_MIN_BATCH_SIZE` = 10 | `BISHOP_ENRICHMENT_STAGE1_MAX_HOLD_MINUTES` = 120 |
| Enrichment stage 2 | 10 → 50 | `BISHOP_ENRICHMENT_STAGE2_MIN_BATCH_SIZE` = 10 | `BISHOP_ENRICHMENT_STAGE2_MAX_HOLD_MINUTES` = 120 |

The register-body fields (`source_ids`, `entry_count`, `domain`, `profile_version`) are all
recomputed from the accumulated `entries_to_submit` snapshot at the point of submission, not from
the last poll's `poll.entries` — the pre-existing code read `poll.entries` directly in three
places per loop, which would have silently under-counted a held/amortized batch.

## Amendment round 2 (v1.2.0) — HALT resolution

T9's original dispatch HALTed before writing any code because raising the enrichment defaults
10 → 50 would break two point-literal assertions (`test_enrichment_stage1_batch_size_default`,
`test_enrichment_stage2_batch_size_default`) in a pre-existing test file
(`tests/test_enrichment_batcher_config.py`) that was not in T9's declared Files to touch — editing
it would have been an out-of-scope file touch. This packet (T9-bis) adds that file to Files to
touch, scoped narrowly: only those two assertions change (`== 10` → `== 50`); the other four tests
in the file (`_env_override` ×2, poll-interval ×2, `test_state_worker_url_default`) are untouched,
per the packet's explicit non-goal. Verified: `pytest tests/test_enrichment_batcher_config.py` —
6 passed.

Two further pre-existing test files needed narrow updates as a direct consequence of the
`ENRICHMENT_STAGE1_BATCH_SIZE`/`ENRICHMENT_STAGE2_BATCH_SIZE` default bump, both already in this
packet's declared Files to touch: `test_poll_scraped_entries_uses_scraped_state` and
`test_poll_stage2_queued_entries_uses_stage2_state` each asserted the default poll `limit` was
`"10"`; both now assert `"50"`, matching the raised default they were pinning.

## Alternatives rejected

- **Persist the hold clock in `BatchRecord` or a new table.** Rejected — row 20 (frozen surfaces)
  and D8 explicitly exclude any `BatchRecord` schema change / Alembic revision for this plan's
  observability surface, and a persisted clock is the same class of change. The in-process clock
  resetting on restart is accepted as a documented tradeoff, not solved.
- **Reset the hold clock on every failed submission attempt (including hash/G3 aborts).**
  Rejected — this is exactly the starvation failure mode named by coupling C9: a single
  persistently-wrong rubric or profile hash would then push the deadline forward on every cycle,
  and the held entries would never be given an amortized submission even after human intervention
  fixed the underlying hash mismatch, because the *next* cycle's deadline would already have been
  pushed out again by the same broken hash. Mutation-tested: reverting to "reset on any abort"
  makes the new negative test fail (see below), confirming the chosen behavior is load-bearing.
- **Re-poll for more entries within the same cycle when under the minimum**, instead of returning
  and waiting for the next scheduled poll. Rejected — state-worker's poll endpoint already claims
  and transitions entries out of the source state on every call; a same-cycle re-poll would not
  surface additional not-yet-discovered/scraped entries any faster than the loop's own poll
  interval, and would add poll traffic with no amortization benefit.
- **Apply the missing-summary check (stage 2) before the min/hold gate.** Rejected — this would
  let one bad entry's data-quality problem short-circuit the volume-accumulation decision for
  entries that have nothing to do with it. Kept the check where it already lived: after the
  min/hold gate has decided to proceed, evaluated over the full accumulated batch.

## Assumptions made

- **The three loops are invoked periodically by a long-lived process** (each service's `main.py`,
  not touched by this packet) that calls `prefilter_cycle` / `stage1_cycle` / `stage2_cycle`
  repeatedly on a poll-interval timer. The hold buffer's value depends entirely on this — a
  one-shot script invocation would just accumulate into `_pending_entries` and exit without ever
  submitting a sub-minimum batch (other than via the max-hold deadline on a *later* invocation of
  the same long-lived process). If this assumption is wrong for any deployment path, the hold
  buffer silently loses claimed-but-unsubmitted entries at process exit — the existing
  `main.py` loop structure was read (not modified) to confirm this holds for all three services.
- **Claimed-but-held entries incur no additional state-worker cost or visibility gap beyond what
  already existed.** A poll transitions entries to a "queued"/"claimed" state; if this cycle then
  holds them (does not submit), they remain in that transitional state until a later cycle submits
  them or the process restarts (in which case the in-process buffer is lost and those entries are
  stuck in the claimed state with no owner — a pre-existing gap this plan does not create, since
  the single-poll-single-submit code before this subtask had the identical exposure between a
  successful poll and a failed/skipped submit).
- **Stage 1 and stage 2 hold clocks are independent and safe to run concurrently.** `app.main`
  (not in Files to touch) runs `stage1_cycle` and `stage2_cycle` under `asyncio.gather`; each
  loop's hold state lives in its own module (`app.stage1_loop` / `app.stage2_loop`), so there is no
  shared mutable state between them. Confirmed by reading both modules' final diffs — no import of
  one loop's `_pending_entries`/`_hold_started_at` from the other.

## Items deferred

- **Restart resets the hold clock and loses buffered (claimed) entries' amortization progress.**
  Named explicitly in the packet's Risks & mitigations as an accepted tradeoff, not solved here — a
  persisted clock would require the `BatchRecord` schema change this plan's row 20 / D8 forbid.
  No landing gate is named for this beyond the existing `FU-CACHE-*` deferred-rows convention; it
  is a plan-level accepted risk, not a follow-up to close.
- **Stage 1 has no rubric/profile hash-abort path of its own yet** (T6 adds one per contract row
  13). The stage-1 negative test in this subtask exercises the G3 gate as the available abort
  surface instead of a hash mismatch, proving the same "abort does not reset the hold clock"
  property holds for whichever abort mechanism is present. When T6 lands stage 1's rubric-abort
  path, its own subtask inherits the same non-reset obligation this decision log documents — T6's
  own tests are the closing gate for that specific abort path, not a re-open of this item.
- **Larger batches widen single-prefix blast radius** (coupling C10, already flagged in the
  packet as `suspected`, not bound as a kill criterion here since the exposure is cost, not
  correctness). Unaffected by this subtask beyond the default bump 10 → 50 already called for by
  the packet; G1's live-batch check before any backfill tranche remains the closing gate, per the
  packet's own text — not restated as new here.
