# M8 — Hardening and Scale

**Plan:** `.dev/plans/m8-hardening-scale/` v1.5  
**Audit:** revision 2 `accepted-with-waivers` (2026-09-11)  
**Code HEAD at last implementation:** `9f18367`

## Built

- Seven-source `ADAPTER_REGISTRY` (ArXiv + HF, PwC, Semantic Scholar, GitHub, OpenReview, LessWrong).
- Typed tokens: `GITHUB_TOKEN`, `SEMANTIC_SCHOLAR_API_KEY`, `HUGGINGFACE_TOKEN`.
- state-worker hub: reading-status PATCH, permanent-fail POST; query-api proxies; UI `/escalations` and `/explorer`.
- Backfill *enablement*: `BACKFILL_CONFIG`, chunking, `BISHOP_BACKFILL_*` compose keys (default off).
- G5 fixture wrapper; G6 prefilter gold bind (`eval/prefilter_v1`); G6 enrichment assessed 7/10 with owner waiver.
- `scripts/verify-m8.sh` complete vs declared T5/T6 + registry test surfaces.
- Compose tags `bishop/scraper:m8`, `bishop/ui:m8`.

## Deferred (not next-milestone scope unless reopened)

- G7 wet-run: live chunked backfill producing `INDEXED` without pipeline errors.
- Architecture folder refresh (audit F7).
- Context-map refresh (`m8-context-map-refresh`).
- Call 1 `challenge_hooks` iteration (`g6-call1-hooks-iteration`).
- Charter §23 / §24 items (never in M8).
- `Mark Resolved` escalation action (M8 non-goal).

## Decisions not yet in the spec

- LessWrong: GET-only after GraphQL probe (T4 decision log).
- Incremental ArXiv window stays 7 days; `BACKFILL_CONFIG` 60-day window is backfill-only (T1-bis).
- G6 “assessed” + 7/10 waiver is the G7 *entry* bar, not all-true pytest (`BISHOP_G6_MANUAL=1` expected-fail).
- Overlapping backfill chunks accepted (F6); disjoint `until` not added.

## Not a charter M9

`.dev/plans/m9-source-expansion/proposal.md` is a 2026-09-10 scoping note written against ArXiv-only registry. M8 later landed the reserved spec adapters. That proposal’s thesis (applied-systems / dev-skills density) is a different source *class*, not a missing M8 packet.
