# T2 — `prefilter_rubric_v1.md` (cache key A)

**Plan:** prompt-caching · v1.1.0 · **Tier:** architectural

## Chosen approach

Authored `config/prompts/prefilter_rubric_v1.md` as **source-shape law**: guidance on how much
evidentiary weight the pre-filter manifest's `title` / `abstract` fields can bear, broken out by
the five distinct content shapes behind the seven M8-registered scraper adapters
(`services/scraper/app/adapters/registry.py::ADAPTER_REGISTRY`):

- **paper** — arxiv, openreview, semantic_scholar (real multi-sentence abstract)
- **repo** — github (`title` = repo name, `abstract` = one-line tagline/description)
- **model card** — huggingface (`title` = `[kind] name`, `abstract` = card description or,
  degenerately, a bare comma-joined tag list)
- **article** — lesswrong (`title` only; `abstract` is **always** `None` — verified against
  `services/scraper/app/adapters/lesswrong.py`, which never sets it)
- **hub dump** — paperswithcode (paper-shaped fields, but the row exists because an
  implementation was linked, not because the implementation was evaluated)

Grounded each shape's claim in the actual adapter source (`title=`/`abstract=` construction in
each of the seven `services/scraper/app/adapters/*.py` files), not assumption, before writing
guidance about it. The annex explicitly does **not** add, remove, or reweight any exclusion,
anchor, or peripheral class from `config/profiles/professional_v1.2.0_soft_launch.yaml` — it
only calibrates confidence in reading the fields already in front of the model, and defaults
low-evidence, anchor-plausible rows to the profile's own peripheral-park instruction rather than
inventing a new default. Confirmed no use of "pass" language (the soft-launch overlay's
`peripheral_disposition` is `park`, not `pass`) and no exclusion/anchor/peripheral-class
vocabulary invented outside what the profile already states.

Sized the annex against the real, live pin (`professional_v1.2.0_soft_launch.yaml`, 2,280
`cl100k_base` tokens measured via `render_profile_prompt`) rather than the planning-time
estimate, and measured the annex itself (2,777 tokens) directly with `tiktoken.get_encoding
("cl100k_base")` — same technique `bishop_shared/content_truncation.py` already uses. Total
key-A prefix: 5,057 tokens, 551 above the 4,506-token floor target (row 8) and well clear of
the raw 4,096 Haiku floor.

Extended `tests/test_rubric_assets.py` (append-only, mirroring the section convention T3/T4
already established in the same file) with:

1. `test_prefilter_rubric_v1_resolves_and_hash_verifies` — the real committed asset resolves
   via `resolve_rubric_path` and its stamped hash matches a fresh recompute.
2. `test_prefilter_rubric_v1_front_matter_matches_shared_schema` — literal front-matter shape
   (row 7), shared verbatim with T3/T4.
3. `test_prefilter_rubric_v1_clears_key_a_token_floor` — the row-8 floor claim, measured
   against the real `professional_v1.2.0_soft_launch.yaml` render, not a stand-in.
4. `test_prefilter_rubric_v1_names_only_m8_registered_adapters` — extracts every source name
   from the annex's `## Shape N — <shape> (<sources>)` headers and asserts each is one of the
   seven adapters in `ADAPTER_REGISTRY`. This is this subtask's adversarial-micro-pass
   falsifier (§2.1): mutation-checked by temporarily appending a fictitious source (`, reddit`)
   to the Shape 1 header, confirming the test failed with `unregistered = {'reddit'}`, then
   reverting and re-stamping the hash back to the reverted (byte-identical) body.

## Alternatives rejected

- **Import `bishop_shared.enums.SourceEnum` in the new tests** to build the M8-adapter-set
  comparison, instead of a hardcoded literal frozenset. Rejected: `tests/test_rubric_assets.py`
  is a file T3 and T4 are concurrently editing in the same uncommitted working tree (no
  workspace isolation between parallel executors on this plan), and the import block at the top
  of the file is exactly the region their edits already touch. Adding a new top-level import
  there risks an unclean `git add -p` hunk boundary at commit time — mixing my import edit with
  a sibling's uncommitted import edit in the same diff hunk. A hardcoded, commented literal
  (naming the registry file it mirrors) keeps my entire diff to this file as one clean append at
  the end, matching the pattern T4 used for the same reason (their key-C token-floor test
  hardcodes the Call 2 instructions text rather than importing the not-yet-landed builder).
- **Writing the row-8 floor test into a new shared `tests/test_prompt_cache_token_floor.py`**
  instead of `tests/test_rubric_assets.py`. Rejected: that path is explicitly named as T10's
  file in contract row 8's falsifier ("New `tests/test_prompt_cache_token_floor.py`"); creating
  it here would collide with T10's Files-to-touch. This subtask's own floor-claim falsifier
  lives in the file already in my Files-to-touch instead.

## Assumptions made

- **A2/A3 (packet §4):** Claude Haiku 4.5's real cacheable-prefix floor is 4,096 tokens and
  `cl100k_base` is a safe-enough proxy for Anthropic's tokenizer that a measured 5,057 (23%
  over the raw floor, 12% over the 4,506 margin target) clears it. Not independently
  falsifiable from this subtask; G1's live `cache_creation_input_tokens` is the real falsifier
  per the packet.
- **A6 (packet §4):** The measured 1,816-token gap to the raw floor (soft-launch profile render
  at 2,280 tokens) does not move before this plan closes. If the prefilter pin reverts (its
  own stated future intent) or `professional_v1.2.0_soft_launch.yaml` is edited, the 5,057-token
  total is stale and needs re-measurement — row 8's contract binds the *total* prefix precisely
  so a pin change fails loudly (a re-run of `test_prefilter_rubric_v1_clears_key_a_token_floor`)
  rather than silently.
- The seven-adapter `ADAPTER_REGISTRY` list is stable for the life of this plan. If M9 (source
  expansion, per `.dev/plans/m9-source-expansion/proposal.md`) adds an eighth adapter before
  this plan closes, the M8-adapter-set naming test's hardcoded frozenset and this annex's shape
  taxonomy both go stale — out of scope to guard against here; a HALT-worthy discovery for
  whichever future subtask notices it.

## Items deferred

- **Live pre-filter eval replay with the annex wired into the prompt.** Wiring the annex into
  the actual Anthropic `system` block list (contract row 5: `build_requests(*, system_blocks=
  ...)`) is T5's scope, not this subtask's — this subtask only authors and hash-stamps the
  content. No claim is made here about measured pre-filter accuracy/precision/recall with the
  annex present; that is a T5/T10/G1 concern.
- Non-exhaustiveness of the M8-adapter-naming test (self-check §11 note, also stated in the
  test's own docstring): the test proves the named set is a *subset* of the registered
  adapters, not that every registered adapter is named somewhere in the annex. All seven are in
  fact named (verified by eye during authoring), but no test asserts that completeness
  property; a future adapter-registry change would not automatically flag a stale annex that
  quietly drops a source's coverage.
