# T4 — Author `call2_rubric_v1.md` (cache key C)

**Plan:** prompt-caching v1.1.0 · **Tier:** architectural · **Date:** 2026-09-12

## Chosen approach

Authored `config/prompts/call2_rubric_v1.md`, a stamped rubric annex that
governs enrichment Call 2's continuous `relevance_score` float (0.0–1.0)
and its accompanying `relevance_reason` / `value_rationale` strings. The
annex is structured as:

- An explicit framing section distinguishing the float-scoring question
  from gate 1's binary corpus-admission question, so the model does not
  answer the wrong question.
- Five score bands (0.90–1.00 core exemplar, 0.70–0.89 strong secondary,
  0.50–0.69 marginal, 0.30–0.49 weak/tangential, 0.00–0.29
  should-not-have-passed-gate-1), each with a worked description.
- Anchor-weighted scoring guidance tying the profile's per-anchor weights
  (1.0 / 0.9 / 0.8 / 0.7) to expected score ranges.
- Fifteen worked examples covering every band, multi-anchor overlap, a
  peripheral-tier pass-through, a low-weight-anchor-at-high-quality case,
  and a deliberately close borderline-weak-vs-excluded case, each with a
  `relevance_reason` and `value_rationale` in the exact style Call 2
  should produce.
- `value_rationale` guidance distinguishing specific/checkable value
  statements from topic restatement, plus a parallel
  `relevance_reason`-vs-`value_rationale` distinction section.
- A scoring-consistency section (batch compression, gate-1 tier leakage)
  and a common-miscalibration-traps list (hype inflation, author-prestige
  substitution, length-as-depth substitution, binary bleed-through).

Sized and measured against the **`include_output=False`** render of
`professional_v1.0.0.yaml` (348 `cl100k_base` tokens) — the variant T7 will
actually assemble for cache key C — plus the current Call 2 instructions
block (82 tokens, taken from `enrichment_prompts.build_call2_system_prompt`
verbatim). Annex body measures 4,379 tokens. Total key-C prefix: 348 +
4,379 + 82 = **4,809** tokens, clearing the §2 row 8 floor (4,506) by a
303-token (6.7%) margin. All measurement performed with the actual
`bishop_shared.profile_renderer.render_profile_prompt` and
`bishop_shared.rubric_assets.load_rubric` code paths, not a hand count.

Stamped `canonical_hash` via `python scripts/rubric_hash.py
config/prompts/call2_rubric_v1.md` (see kill-criterion evidence below for
the raw output).

## Alternatives rejected

- **Measuring against `include_output=True` (383 tokens).** This is the
  packet's explicitly named trap: T7 will render Call 2's profile block
  with `include_output=False` (348 tokens, per §5.4 C4's fix — the
  gate-1 output instruction must not appear in the Call 2 cached prefix).
  Sizing the annex against the larger, wrong variant would have produced a
  margin that reads safe on paper but leaves the real prefix under-floor
  once T7 lands. Rejected in favor of measuring against the actual render
  variant named in the packet's Inputs/Kill-criteria.
- **Padding with repeated boilerplate or restated schema text to hit the
  floor faster.** Rejected per the plan's explicit non-goal ("no padding")
  and this subtask's own kill criterion ("HALT rather than pad"). Every
  section added (worked examples 11–15, the consistency section, the
  `relevance_reason`/`value_rationale` distinction section) is gate-quality
  scoring guidance that a model applying the rubric would actually use,
  not filler encoded to hit a token count.
- **A single large worked-examples table instead of prose sections.**
  Rejected because the scoring bands, anchor-weight guidance, and
  miscalibration traps are qualitatively different kinds of guidance from
  worked instances; collapsing them into one table would have made the
  band boundaries and the anchor-weight reasoning harder to state
  precisely, and would have made it easier to accidentally reintroduce a
  binary-flavored framing (the exact failure this subtask must avoid).

## Assumptions made

- **A2/A3 (inherited from the packet):** Claude Haiku 4.5's real cacheable
  floor is 4,096 tokens and `cl100k_base` is a safe proxy at the stated
  10% margin. This subtask does not re-derive either; if both are wrong in
  the unsafe direction, G1's live `cache_creation_input_tokens` is the only
  real falsifier, per the packet.
- **The 82-token Call 2 instructions figure is stable until T7 lands.**
  `tests/test_rubric_assets.py::test_call2_rubric_v1_clears_key_c_token_floor_against_include_output_false`
  pins this figure as a literal (matching
  `enrichment_prompts.build_call2_system_prompt`'s current text) rather
  than importing the builder, specifically so this test does not silently
  track an unrelated wording change T7 might make. If T7 changes that
  instructions text materially, T7 (or T10 at closure) must re-verify the
  key-C floor against the actual assembled prefix — this subtask's test is
  a proxy pinned at today's wording, not a live wire to T7's diff.
- **The profile pin for enrichment stays `professional_v1.0.0.yaml` (D5).**
  If that pin moves, the 348-token figure moves with it and the margin
  must be re-measured (this is exactly the A6 pin-revert trigger from the
  packet, extended to the enrichment side).

## Items deferred

- **Live cache-hit confirmation.** This subtask can only prove the
  `cl100k_base`-measured token floor; it cannot prove Anthropic actually
  caches the resulting prefix. Deferred to **G1** (`batch-poller`'s
  `cache_creation_input_tokens > 0` observation once T5/T6/T7/T8 land and
  a real batch runs), per §2 row 8's named semantic gap. Not a gap this
  subtask can close.
- **Wiring `call2_rubric_v1.md`'s body into the actual Call 2 system
  prompt / cache blocks.** Out of scope for T4 per the packet (`build_
  stage2_requests` / `build_call2_system_prompt` migration is T7's Files
  to touch under §2 row 5 and row 10). This subtask only authors and
  stamps the asset; T7 consumes it.
- **§2 row 9 "single emitter" grep test currently red** (pre-existing,
  inherited from T1-bis; `bishop_shared/enrichment_prompts.py` still
  inlines a `cache_control` literal until T7 migrates it). Not touched or
  worsened by this subtask; re-verified green at T10 closure per the
  T1-bis decision log's own note.
- **CHANGELOG.MD reconciliation.** Per the packet's commit-order guard,
  T2 and T3 were both mid-flight in the same working tree while this
  subtask ran. This subtask's own commit stages only its own bullet
  (verified via a diff review restricted to the T4 hunk); it does not
  merge or reorder T2's / T3's bullets, which they commit themselves.
