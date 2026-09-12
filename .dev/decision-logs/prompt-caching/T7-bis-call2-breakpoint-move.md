# T7-bis — Continuation of T7: Call 2 wiring (cache key C, breakpoint move)

**Plan:** prompt-caching v1.3.0 · **Tier:** architectural · **Amendment round:** 3
**Supersedes:** T7 (HALTed with no code; `.dev/plans/prompt-caching/runs/T7-brief.md`)
**Depends on:** T1-bis (`8d9af01`), T4 (`e4b7e9d`), T6 (`ba49bb1`, current HEAD at dispatch)

## Chosen approach

Two distinct decisions, kept separate per the packet's instruction:

**1. Breakpoint move.** `bishop_shared/enrichment_prompts.py::build_call2_system_prompt`
now takes a second parameter, `rubric_body: str`, and returns a three-block
`list[dict[str, object]]` via `cached_system_blocks(profile_prompt, rubric_body,
instructions)` — block order `[profile_render, call2_rubric, call2_instructions]`
per row 10. The sole `cache_control` breakpoint (with `ttl: "1h"`, absent before)
moves from block 0 (profile) to the last block (instructions), so the entire
static prefix — not just the profile — is the cacheable span. This closes row 9's
"single emitter" grep (`tests/test_prompt_cache.py::test_no_inline_cache_control_literals`),
whose one remaining offender was this function's old inline
`{"type": "ephemeral"}` literal.

`AnthropicBatchClient.build_stage2_requests` / `submit_stage2_batch` /
`submit_stage2_batch_or_fatal` (`services/enrichment-batcher/app/anthropic_batch_client.py`)
all gained a `rubric_body: str` keyword-only parameter threaded straight through
to the builder. Unlike Call 1 (row 5 freezes `build_requests` at `entries` only,
forcing T6 to accept a duplicate rubric-file read — see T6's decision log), Call
2's `build_stage2_requests` signature is *not* frozen at the caller-owns-rubric
shape; the packet's row 5 explicitly names `rubric_body` as a parameter. This
means `stage2_loop` reads and hash-verifies the rubric exactly once per cycle and
passes the verified body down — no duplicate read.

`stage2_loop.py` gained a `_verify_rubric_hash` function that mirrors
`stage1_loop.py::_verify_rubric_hash` byte-for-byte in structure (load, recompute,
compare, log `event="rubric_hash_mismatch"` at ERROR, return `None` on mismatch —
no CRITICAL alert, preserving the row 12 asymmetry inherited from the M5 T4
deferral). It is called after `_verify_profile_hash` and before the (pre-existing)
G3 check, with the same plain-`return`-on-mismatch discipline: `_pending_entries`
and `_hold_started_at` are left untouched, so a persistent rubric mismatch cannot
push the hold deadline forward and starve stage 2 (C9 — bound, and now proven for
stage 2's own rubric-abort path by
`test_stage2_cycle_rubric_abort_does_not_extend_hold_deadline`, mirroring the
existing profile-hash-abort proof for the same coupling). `stage2_cycle` gained an
optional `rubric_path: Path | None = None` kwarg mirroring the existing
`profile_path` override, resolved via `rubric_path or resolve_rubric_path("call2_rubric")`.

**2. Gate-1 output-contract removal (C4).** `_verify_profile_hash` now calls
`render_profile_prompt(profile, include_output=False)` instead of the default.
Before this change, the profile render appended `professional_v1.0.0.yaml`'s
`output.instruction` — gate 1's `{"decision": 0 or 1, "rationale": "..."}` string
— into the Call 2 system prompt, contradicting the real `relevance_score`/
`relevance_reason`/`value_rationale` schema supplied by `build_call2_system_prompt`.
This was a latent bug before this subtask (every Call 2 row already received both
instructions); moving the breakpoint to the last block would have made it
*cached* — prepaid on every row — without this fix. `build_call2_system_prompt`
itself does not strip or re-add the instruction; it trusts the caller, per its own
docstring. Guarded by
`tests/test_enrichment_prompts.py::test_call2_system_prompt_does_not_reintroduce_gate1_output_contract`
(unit, synthetic input) and, more load-bearingly, by the happy-path integration
assertion in `tests/test_enrichment_batcher_stage2_loop.py` that scans every
system block built from the **real** `professional_v1.0.0.yaml` render for the
literal `"decision"` substring — this is the falsifier that actually exercises the
production call path (`_verify_profile_hash` → real profile file → real
`render_profile_prompt`), not just a hand-shaped string.

## Alternatives rejected

- **Loading the rubric independently inside `build_call2_system_prompt`, mirroring
  T6's Call 1 approach (accept a duplicate file read).** Rejected: row 5 for Call 2
  explicitly names `rubric_body` as a parameter on `build_stage2_requests`, unlike
  Call 1's frozen `entries`-only signature. Threading the already hash-verified
  body through is both the contract-literal choice and strictly better (no
  duplicate read, no risk of the hash-checked body and the prompt-assembled body
  silently diverging if the file changes mid-cycle).
- **Fixing the C4 contradiction inside `build_call2_system_prompt` itself** (e.g.
  stripping a `{"decision"` substring from the passed `profile_prompt`).
  Rejected: this would silently paper over a caller bug instead of fixing the
  actual defect, and it would make the builder's behavior depend on string
  content matching rather than on the caller using the `include_output=False`
  contract `render_profile_prompt` already exposes (T1-bis). The fix belongs at
  the render call site (`stage2_loop._verify_profile_hash`), where the decision
  about *which* profile variant to render is actually made.
- **Waiving row 6/§6's M5-log supersession banner requirement, or routing it to a
  follow-on subtask (T7's rejected fork b).** Rejected by the orchestrator before
  this subtask was dispatched (packet §"Why T7 HALTed", fork a chosen). Not
  re-litigated here; the banner is landed in this subtask (see M5 log edit below).
- **Starting from HEAD `c47248e` (T7's stale packet-cited HEAD).** Rejected per
  explicit packet instruction — T5 (`eb9b873`) and T6 (`ba49bb1`) landed after
  T7's HALT and are load-bearing prerequisites (T6's Call 1 blocks, cache-shape
  helpers) that a `c47248e`-based diff would have reverted.

## Assumptions made

- **T4's `call2_rubric_v1.md` token-floor measurement (4,809 measured
  `cl100k_base` tokens against the `include_output=False` profile variant) is
  still accurate against the now-actually-wired three-block prefix.** T4's
  decision log measured the annex separately from the wired call; this subtask
  does not re-measure the assembled prefix with a dedicated point-literal test —
  that is row 8's closure gate, owned by T10 (mirroring T6's identical deferral
  for key B). If T10's `tests/test_prompt_cache_token_floor.py` measures a
  different total, that is T10's finding to report, not a contradiction of this
  subtask's work.
- **The M5 T4 log's "Chosen approach" bullet is the correct first-mention anchor**
  for the supersession banner — it is the first sentence in that file recording
  the profile-block-only `cache_control` decision (confirmed by reading the file
  top to bottom before editing).
- **Row 9's grep test passing after this diff is sufficient proof of "single
  emitter" closure** — confirmed directly:
  `pytest tests/test_prompt_cache.py::test_no_inline_cache_control_literals` is
  green in this subtask's own diff (not deferred to T10; T10 re-runs it at
  closure as a second confirmation, per the packet's contract row 9 language).

## Items deferred

- **Row 8 (token-floor point-literal proof for the wired key-C prefix).** Not
  this subtask's file — `tests/test_prompt_cache_token_floor.py` is T10's new
  test module per the plan's contract. Landing gate: **T10**.
- **Live confirmation that Anthropic actually caches key C**
  (`cache_creation_input_tokens > 0` from a real batch). Named in row 8 as a
  semantic gap no proxy-tokenizer test can close; T8's poller observability
  fields (already landed) make this checkable once a real batch runs. Not this
  subtask's scope.
- **Row 12's alert asymmetry (stage 2 logs only, no CRITICAL) staying open.**
  Deliberate — `FU-CACHE-ALERT-01`, owner a future milestone per the plan's
  deferred-rows table. This subtask preserves, not closes, that asymmetry.
