# T3 — `call1_rubric_v1.md` (cache key B)

**Plan:** prompt-caching v1.1.0 · **Tier:** architectural · **Depends on:** T1-bis (`8d9af01`)

## Chosen approach

Authored `config/prompts/call1_rubric_v1.md` as a standalone Markdown asset with
the required front matter (`rubric_id: call1_rubric`, `version: "1.0.0"`,
`canonical_hash`, stamped via `scripts/rubric_hash.py`). Content is organized in
six sections: (1) why extraction drifts without guidance (summary genericism,
`challenge_hooks` title-restatement), (2) per-`entry_type` guidance for all nine
types (`paper`, `model`, `dataset`, `repo`, `article`, `spec`, `idea`,
`benchmark`, `other`), (3) per-source content-shape notes for all seven sources
grouped by how `content_truncation.py` actually reshapes their content (paper
sources: abstract+body; `github`: header+structural digest; `huggingface`:
YAML front matter + prose; article sources: beginning+end window), (4) four
full worked examples (`paper`/arxiv, `repo`/github, `model`/huggingface,
`article`/lesswrong) each showing a realistic truncated input and the expected
5-key JSON output, (5) boundary-case guidance for the five entry-type pairs
most likely to be ambiguous from truncated content alone, (6) a failure-modes
checklist. Measured annex body: 4,619 `cl100k_base` tokens; total key-B prefix
estimate (267 + 4,619 = 4,886) clears the 4,506 target with a ~380-token
margin. Extended `tests/test_rubric_assets.py` with one new test asserting the
*actual committed* asset (not a synthetic `tmp_path` fixture) exists, parses,
and hash-verifies — mutation-checked by corrupting the stamped hash in place,
confirming the test fails, then restoring the original file byte-for-byte.
Produced the required manual spot-check artifact
(`.dev/plans/prompt-caching/artifacts/T3-call1-spotcheck.md`) running 6 real
`arxiv` entries from the live `bishop.db` through `claude-haiku-4-5-20251001`
with and without the annex appended to the system prompt, comparing all five
output fields; no `challenge_hooks` specificity degradation observed across any
of the 6 entries (three showed the after-run pulling a more specific number or
named comparison than the before-run).

## Alternatives rejected

- **Padding to the token floor with restated schema/taxonomy text or filler
  prose.** Rejected per the plan's explicit non-goal (no padding — every token
  must carry gate quality) and this packet's own kill criterion ("HALT rather
  than pad"). Every section of the annex is guidance a Call 1 extraction call
  can actually use, not filler.
- **One worked example per entry-type note (9 examples) instead of 4 examples
  spanning the highest-volume source/type combinations.** Rejected: the task
  statement calls for "worked examples for summary/concepts/tags/entry_type/
  challenge_hooks" — i.e., demonstrating the field set, not exhaustively
  demonstrating every type. Four examples covering the four highest-volume
  source families (paper, repo, model, article) already exercise all five
  output fields multiple times and both per-source and per-type guidance
  together, at proportionate token cost. The remaining five types (`dataset`,
  `spec`, `idea`, `benchmark`, `other`) get prose guidance in §2 and boundary
  disambiguation in §5 instead of a fifth-through-ninth full worked example.
- **Running the spot-check against synthetic/hand-written content instead of
  live DB rows.** Rejected: the packet's own risk framing ("weakest
  verification story... the spot-check artifact is the mitigation") calls for
  evidence about real behavior, and synthetic content could be shaped to make
  the comparison look favorable. Real, unmodified `content_raw` rows through
  the actual (frozen, out-of-scope) `truncate_content_for_call1()` function
  were used instead.

## Assumptions made

- **A2/A3 (plan-level, inherited):** Haiku 4.5's cacheable floor is 4,096
  `cl100k_base`-proxy tokens and the 4,506 target absorbs proxy-tokenizer
  error. This subtask sized the annex to clear 4,506 with margin; it cannot
  itself falsify A2/A3 — that remains G1's live `cache_creation_input_tokens`
  check, out of this subtask's scope.
- **The annex will be appended, not interleaved, into the Call 1 system
  prompt** by T6 (`[call1_system, call1_rubric]` per contract row 10's block
  order). This subtask did not wire the annex into `build_call1_system_prompt`
  or `build_requests` — that is T6's `Files to touch`, not T3's. The spot-check
  probe manually concatenated `build_call1_system_prompt() + "\n\n" + annex_body`
  to approximate T6's eventual behavior; if T6 wires the blocks differently
  (e.g., a different separator or block boundary), the exact prefix bytes this
  spot-check exercised will differ from what ships, though the annex *content*
  itself does not change.
- **The live DB's current content mix (arxiv-only `content_raw` rows) is
  representative enough for a spot-check on `paper`/`arxiv`,** but is
  explicitly **not** assumed representative for the other six sources or
  eight other entry types — see Items deferred.

## Items deferred

- **Live spot-check coverage for `github`, `huggingface`, and article sources
  (`lesswrong`/`paperswithcode`), and for entry types other than `paper`.**
  Not closed here: the live `bishop.db` snapshot used for this spot-check has
  no non-`arxiv` rows with usable `content_raw` at the time this subtask ran.
  The annex's content for those sources/types (§2, §3 of the annex) is
  authored and covered by the structural/hash test, but not live-behavior
  validated. No subtask in this plan currently owns re-running this probe
  once non-arxiv content exists in the DB; flagged in the spot-check artifact
  itself as a named coverage gap, not silently dropped. Landing gate: none
  named in this plan — a future backfill or data-diversity milestone is the
  natural point to re-run `T3_spotcheck_probe.py`'s approach (the probe script
  itself was scratch and was deleted per repo convention, not committed; its
  logic — pull `content_raw` rows, run before/after through the two system
  prompts, diff — is fully described in the spot-check artifact and can be
  reconstructed from there).
- **Row-9 "single emitter" contract status.** Inherited from T1-bis; T3 did
  not touch `bishop_shared/enrichment_prompts.py` or introduce any
  `cache_control` literal, so this subtask does not change row 9's status.
  T10 remains the closure point.
