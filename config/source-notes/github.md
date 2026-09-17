# github

Adapter: `services/scraper/app/adapters/github.py`  
Shape: **2 — repo** (title + marketing tagline). Lowest-evidence applied source.

## Taste

Bar: **would I study or steal from this codebase** — not “is this about agents / RAG.”

Wanted: applied systems, shipped practice, stealable architecture, skills, workflows, eval/obs, agentic products with a real artifact. Thin, high-signal corpus.

Not wanted: kitchen-sink “AI employees” wrappers, product landings, badge-walls, awesome-lists, vendor SDKs, clones of a CLI you already run, on-topic boilerplate that still costs scrape + enrich.

Operator quote (2026-09-15) on `github:antonyrag/ragleap-core`: “yes this is the type of junk we need to filter out.”

## Machine today

- **Fetch:** `pushed:>DATE stars:>10` (`build_search_query`). Popularity floor, not quality.
- **Gate 1:** same pin as every source — `professional_v1.2.0_soft_launch.yaml` + rubric shape 2. Shape law as of option 1 (2026-09-15): taglines are marketing; kitchen-sink / landing / badge-wall / awesome-list / vendor SDK / CLI-clone are **reject**; ambiguous membership in those classes is reject, not park. A named stealable artifact can still be core or park.
- **Park:** `decision=1` + `tier=peripheral` → `RELEVANCE_PARKED` (no scrape/enrich until promote). Park still spends gate-1 tokens. Do not use park as the dump for on-topic boilerplate.
- **Call 2** `relevance_score` is not gold. High score means “looks agentic,” not “study this repo.”
- Live overlay lookback: **60 days** (extended 2026-09-15 after option 1 Shape 2 was live in `pre-filter-worker`). Spec `BACKFILL_CONFIG` github window is 30 days — overlay is now wider than that spec row on purpose. GitHub Search still caps at 1000 hits/cycle (`stars:>10`). Do not rewind Hugging Face.

## Intel — 2026-09-15 repo-gate v0 spotcheck

Packet: `eval/github_repo_gate_v0/` (`contract.json` v0.2.0, `corpus.json`, `proposals.json`, `labels.json`, `intel.json`, `review.html` + `packet.js`).

93 INDEXED github rows. Agent prior 68 keep / 19 junk / 6 unsure. Operator stamped **23** (all agent-junk + 2 unsure + 4 keep), then stopped. Remaining agent-keep = **provisionally accepted**. Do not re-run the 93-card pass.

| agent → human | n |
|---|---|
| junk → junk | 17 |
| junk → unsure | 2 |
| keep → keep | 4 |
| keep → junk | **0** |

**Load-bearing:** 11 of 23 stamps are Call 2 ≥ 0.7 and still **junk**. Gate 1 + enrichment agree on topic. They do not implement the quality bar. Default next work is **option 1** (stricter shape-2 language on the **same** pin). Option 3 (GitHub-only profile) is **not earned**. Option 2 (tighter fetch) is optional and does not replace 1.

### High-score junk (train the next rubric on these)

Kitchen-sink / landing / badge-wall / sovereign-OS marketing. All Call 2 ≥ 0.7 unless noted in packet.

- `github:antonyrag/ragleap-core` — kitchen-sink “AI employees” / RAG wrapper
- `github:hanyeol/model-compose` — YAML “deploy in minutes” landing
- `github:Apra-Labs/apra-fleet`
- `github:MikkoParkkola/mcp-gateway` — badge-wall
- `github:Mnemosyne-OS/Mnemosyne-Neural-OS` — sovereign-OS landing
- `github:BlocUnited-LLC/mozaiks`
- `github:clayrune-io/clayrune`
- `github:HongyunQiu/QevosAgent`
- `github:caura-ai/caura-build-fleet`
- `github:magicyuan876/mineru-tianshu`
- `github:sseshachala/conductai`

### Stamped keeps (must still be allowed to pass or park)

- `github:Belkins/ai-dive-deep`
- `github:abundantbeing/hermes-browser-extension`
- `github:HKUDS/LightRAG`
- `github:StructuPath/herdr-browser`

### Junk classes (named so option 1 can reject, not park)

1. Kitchen-sink wrapper (“AI employees”, RAG-in-a-box, fleet-of-agents landing)
2. Product landing (“deploy in minutes”, YAML-as-product)
3. Badge-wall README (stars/CI/shields, no stealable core)
4. Awesome-list / link dump (already reject in shape 2)
5. Vendor SDK / thin client around someone else’s API
6. Clone of a CLI you already run

Ambiguous kitchen-sink / landing / badge-wall → **reject**, not park (park still costs tokens and fills the inbox).

## Intel — 2026-09-15 option 1 landed

Shape 2 now rejects the junk classes named above. Same pin, same cache key A. Four stamped keeps still allowed to pass or park. Live in `pre-filter-worker` as of 2026-09-15. Overlay lookback extended to **60 days** the same day.

## Intel — 2026-09-17 harvest sidecar + tap landing

Harvest sidecar (`${BISHOP_DATA_ROOT}/harvest/ledger.sqlite`) and the dollar tap landed. Incremental GitHub still writes `DISCOVERED`. Dashboard projected $ is sidecar released-today × blended GitHub unit cost, not live Anthropic (PB-002). Do not rewind Hugging Face.

## Intel — 2026-09-17 tap live, mill hitchhiker

Same-day live: `released_today` hit `N_cap` (1413). Pool 2000 after two incomplete Search windows (1000 each, cursor still 2024-09-21 of a 2y walk). `N_cap` stops the tap, not harvest. Harvest is 90s at the end of `scrape_cycle` then `BISHOP_SCRAPER_SCHEDULE_INTERVAL_SEC=21600` on this host. Next code is a harvest **loop** (PB-011), not GitHub cutover (PB-012) and not paper exhaust. Write-up: `.dev/decision-logs/ops/harvest-pool-first-landing.md`.

## Next (do not invent)

See `repo-gate-next.md` for Shape 2 / option 2–3. Harvest mill vs cutover: `harvest-pool-next.md`. Option 1 is implemented and live. Option 2 (tighter fetch) is optional and does not replace 1. Option 3 is not earned. Retrieval check and parked/reject audit remain **deferred**.

## Do not

- New worker, new `SourceEnum`, new cache key, Hugging Face rewind
- Treat leftover `labels.json` / `intel.json` at **repo root** as canonical — packet copies live under `eval/github_repo_gate_v0/`
