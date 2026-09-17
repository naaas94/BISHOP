# GitHub repo gate — option 1 (reject-heavier Shape 2)

**Date:** 2026-09-15  
**Scope:** same gate, same pin, same cache key A. Shape-2 park-vs-reject only.  
**Pickup:** `repo-gate-next.md` · **Eval:** `eval/github_repo_gate_v0/`

## Chosen approach

Tighten `config/prompts/prefilter_rubric_v1.md` Shape 2 so kitchen-sink wrapper, product
landing, badge-wall, awesome-list, vendor SDK, and clone-of-a-CLI-you-already-run are
**reject** (decision 0), not park. Ambiguous membership in those classes is also reject.
This is a stricter *reading* of the profile's existing star-count-dump / no-reusable-technique
exclusion against a GitHub tagline — not a second profile, not a second cache key, not a new
exclusion class.

A repo may still be **core** when the tagline names a stealable artifact (working-reference
code). A named artifact that is too thin to mark core this week still parks. Badges on a
README that also names an artifact do not auto-reject.

One optional sentence on `professional_v1.2.0_soft_launch.yaml`: core on a repo requires a
stealable artifact, not a topic match. Anchors/exclusions otherwise untouched.

## Alternatives rejected

- **Option 2 (tighter GitHub fetch):** optional, coarse, does not catch `ragleap-core`-shaped
  junk that already has stars and the right words. Does not replace Shape 2.
- **Option 3 (GitHub-only profile / prefix):** not earned. Spotcheck: 0 keep→junk on the
  stamped 23; papers stay on this pin. A second cache key A is a real contract, not a prompt
  tweak.
- **Park-on-ambiguous (previous Shape 2):** the failure mode. 11 of 23 stamps were Call 2
  ≥ 0.7 and still junk — gate 1 + enrichment agreed "this looks agentic" and then spent scrape
  + enrich. Park still costs gate-1 tokens and fills the inbox.

## Assumptions

- The four stamped keeps (`ai-dive-deep`, `hermes-browser-extension`, `LightRAG`,
  `herdr-browser`) remain pass-or-park under the new wording because each names a stealable
  artifact. Not auto-reject. Stamped unsure (`agent-manual`, `openlivery`) are not gold reject.
- Call 2 `relevance_score` is not gold. Rubric is trained on the human stamps, not on scores.
- Annex is image-baked. Operator rebuilt `pre-filter-worker` on 2026-09-15; new Shape 2 is the running gate. Overlay lookback then went **7 → 60**.

## Items deferred

- Option 2 (raise `stars:>10` / add topic terms in `build_search_query`) — operator optional.
- Retrieval check and parked/reject audit from the original eval list — not blocking.
- Re-label remaining 70 agent-keep rows — provisionally accepted; do not re-run the 93.
