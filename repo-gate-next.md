# Repo gate — pickup

**Status:** **option 1 implemented** and live. Overlay lookback **60 days** as of 2026-09-15. Option 2 (tighter GitHub fetch) still optional. Option 3 (GitHub-only profile/prefix) still not earned.

**Date:** 2026-09-15  
**Attestation:** `eval/github_repo_gate_v0/labels.json` + `intel.json` (operator export; also leftover copies at repo root).

---

## Intent (unchanged)

Thin, high-signal corpus. GitHub is the applied source we want and the one that floods. The bar for a repo is **would I study or steal from this codebase**, not “is this about agents / RAG.” On-topic boilerplate must not spend scrape + enrich.

We do **not** give every source its own profile. GitHub is the only split we considered, because that’s where quality ≠ topic. Papers stay on the current gate.

---

## What the machine does today

- **Fetch:** `pushed:>DATE stars:>10` (`services/scraper/app/adapters/github.py::build_search_query`). Popularity floor, not quality.
- **Gate 1:** one pin for every source — `config/profiles/professional_v1.2.0_soft_launch.yaml` + `config/prompts/prefilter_rubric_v1.md` shape 2 (repo). Shape-law as of option 1: taglines are marketing; kitchen-sink / landing / badge-wall / awesome-list / vendor SDK / CLI-clone are **reject**; ambiguous membership in those classes is reject, not park. A named stealable artifact can still be core or park.
- **Park:** `decision=1` + `tier=peripheral` → `RELEVANCE_PARKED` (no scrape/enrich until promote).
- **Call 2** `relevance_score` is not gold. Overlay lookback is **60 days**. Do not rewind Hugging Face. Papers with Code API is dead.

---

## Spotcheck result (2026-09-15)

93 INDEXED github rows. Agent prior: 68 keep / 19 junk / 6 unsure.

Operator stamped **23** (all agent-junk + 2 agent-unsure + 4 agent-keep), then stopped: remaining agent-keep treated as **provisionally accepted**. Fine-tune later. Do not re-run the 93-card pass.

| agent → human | n |
|---|---|
| junk → junk | 17 |
| junk → unsure | 2 |
| keep → keep | 4 |
| keep → junk | **0** |

Human on those 23: 17 junk / 4 keep / 2 unsure.

**Load-bearing finding:** 11 of 23 stamps are Call 2 ≥ 0.7 and still **junk**. Gate 1 + enrichment agree with “this looks agentic.” They do not implement the quality bar. Operator note on `github:antonyrag/ragleap-core`: “yes this is the type of junk we need to filter out.”

High-score junk (train the next rubric on these, not on scores):

- `github:antonyrag/ragleap-core` (kitchen-sink “AI employees” / RAG wrapper)
- `github:hanyeol/model-compose` (YAML “deploy in minutes” landing)
- `github:Apra-Labs/apra-fleet`
- `github:MikkoParkkola/mcp-gateway` (badge-wall)
- `github:Mnemosyne-OS/Mnemosyne-Neural-OS` (sovereign-OS landing)
- `github:BlocUnited-LLC/mozaiks`
- `github:clayrune-io/clayrune`
- `github:HongyunQiu/QevosAgent`
- `github:caura-ai/caura-build-fleet`
- `github:magicyuan876/mineru-tianshu`
- `github:sseshachala/conductai`

Stamped keeps (the bar we want to keep passing): `github:Belkins/ai-dive-deep`, `github:abundantbeing/hermes-browser-extension`, `github:HKUDS/LightRAG`, `github:StructuPath/herdr-browser`.

Scale implication: lookback is now **60 days** (option 1 is live). GitHub Search still caps at 1000 hits/cycle.

Retrieval check and parked/reject audit were in the original eval list. **Deferred.** Not blocking option 1.

---

## Options (operator picks; default is 1)

### 1 — Same gate, stricter repo language (**implemented**)

Reject-heavier **shape 2** in `config/prompts/prefilter_rubric_v1.md`. Optionally a line or two in `professional_v1.2.0_soft_launch.yaml` that core on a repo requires a stealable artifact, not a topic match. Ambiguous kitchen-sink / landing / badge-wall → **reject**, not park (park still costs gate-1 tokens and fills the inbox).

- Same pin, same cache key A, same workers.
- Rubric is hash-stamped. Change the annex, restamp (`scripts/rubric_hash.py`), do **not** pad to hit the token floor.
- Falsifier: the high-score junk titles/taglines above would reject; the four stamped keeps would still be allowed to pass or park, not auto-reject.
- Do not rewrite paper / model-card / article / hub-dump shapes except a one-line cross-ref if needed.

### 2 — Tighter GitHub fetch (**optional, cheap, does not replace 1**)

Raise `stars:>10`, and/or add language/topic terms in `build_search_query`. Coarse. Does not catch `ragleap-core`-shaped junk that already has stars and the right words.

### 3 — GitHub-only profile or prefix (**not earned**)

Second profile pin or second rubric for `source=github`. Real contract: cache-key identity (key A must not silently fork), hash-or-abort, tests. Same workers, different prefix. Operator may still choose this; the stamps do **not** require it. Papers must stay on the current pin.

---

## Remaining

- **Option 2** still optional: raise `stars:>10` and/or add language/topic terms in `build_search_query`. Coarse. Does not replace Shape 2.
- **Option 3** still not earned.
- **Lookback / harvest:** overlay is 60 days. Harvest pickup: `harvest-pool-next.md` (tap live; mill hitchhiker; next is PB-011 loop, not cutover). HF not rewound.
- Retrieval check and parked/reject audit remain deferred.

## If you implement option 1

**Landed.** Shape 2 names the junk classes as **reject**; working-reference repos can still be core; hash restamped; no padding. Decision log: `.dev/decision-logs/github-repo-gate/option-1-shape2-reject.md`.

**Do not:** new worker, new `SourceEnum`, new cache key, `BACKFILL_CONFIG` rewrite, Hugging Face rewind, M9 sources, revert the parked overlay.

---

## Related

- Standing GitHub intel (append here, do not rediscover from chat): `config/source-notes/github.md`
- All sources: `config/source-notes/`
- Overlay: `.dev/decision-logs/ops/soft-launch-precision-overlay.md`
- Shape law: `config/prompts/prefilter_rubric_v1.md` § Shape 2
- Pin: `config/profiles/professional_v1.2.0_soft_launch.yaml`
- Packet: `eval/github_repo_gate_v0/` (`review.html`, `contract.json`, `corpus.json`, `proposals.json`, `labels.json`, `intel.json`)
- Operator taste: `relevance_log.md`
- SQLite: `.dev/sqlite.md` (this host: `sqlite_live`)
