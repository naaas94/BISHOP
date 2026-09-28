# UTC 2026-09-15 day performance

**Date of day:** 2026-09-15 (UTC)  
**Filed:** 2026-09-17  
**Scope:** ops / first-week spend snapshot. Not a schema change. Not PB-002.  
**Status:** Snapshot. Overlay revert-or-promote is still open.  
**DB:** `${BISHOP_DATA_ROOT}/sqlite_live/bishop.db` (this host), `mode=ro`, queried 2026-09-17.

Operator console memory: **~25M tokens, mostly cache hits, ~$3**. Sqlite has no usage columns (PB-002). Reconstruction from row counts × the live Haiku 4.5 prefix matches that figure.

This was a **rewind day**, not steady-state ingest. Overlay lookback jumped 1 → 7 → 60 the same UTC day; GitHub Shape 2 (option 1) went live; T12 started shrinking the scraper gap from 6h toward 45 min.

## Verdict (spend only)

Cache is doing the work. ~25M input tokens billed ~$3 at Haiku 4.5 Batch + 1h cache. Same day uncached is ~$13. Yield was 52 INDEXED from 4,135 discoveries (1.3%), ≈ $0.06 per indexed card with cache.

Do not treat 4,114 pre-filter rows as the new daily rate. Adjacent UTC days were ~1.9k–2.2k.

## Tokens and $

Prefix 5,523 tokens from G1 batch `ebc1c3be` (276,150 cache-read / 50). Haiku 4.5 Batch API: cache read $0.05, 1h write $1.00, uncached $0.50, output $2.50 per MTok.

| Component | Tokens | Batch $ | If uncached |
|---|---|---|---|
| Pre-filter prefix (cache read ~98%) | 22.7M | $1.11 | $11.36 |
| Pre-filter prefix (cache write, ~6 cold waves) | 0.53M | $0.53 | — |
| Uncached user tails (HF cards ~750 tok, GH ~70) | ~1.5M | $0.74 | $0.74 |
| Output (rationale ~45 tok × 4,114 + Call 1/2) | ~0.26M | $0.64 | $0.64 |
| Enrichment Call 1+2 (53 rows) | ~0.7M | $0.13 | $0.36 |
| **Total** | **~25M input** | **~$3.10** | **~$13** |

Console ~$3 is the billed ground truth. Write tokens are inferred from wave structure (measured 5.5k writes on the 08:00 HF-only wave; ~30-write races on the big GitHub waves), not from sqlite. T12 sync warmup pings (not batch-discounted) omitted.

Argentina (UTC−3) calendar Sept 15 starts 03:00 UTC and **drops the 02:00 wave** (3,086 pre-filter rows / ~17M prefix). That is not the 25M console day. Anthropic’s calendar is UTC.

## Batches

93 submitted, all `complete`. Zero `error_log` rows that UTC day.

| Gate | Batches | Rows | Sizes | Failed |
|---|---|---|---|---|
| Pre-filter (key A) | 83 | 4,114 | 81×50, 36, 28 | 0 |
| Call 1 (key B) | 5 | 53 | 13, then 10×4 | 0 |
| Call 2 (key C) | 5 | 53 | 13, then 10×4 | 0 |

On a pre-filter batch, `passed_count` is gate-1 `decision=1` (core + parked), not HTTP success: **222 passed / 3,892 rejected**. 21-row gap vs 4,135 discovered is timing, not dropped work.

## Waves (discovered_at, UTC)

| UTC hour | Rows | What | GitHub | HF | Other |
|---|---|---|---|---|---|
| 02:00 | 1,028 | Normal 6h tick (still 1-day overlay) | 734 | 289 | LW 5 |
| 08:00 | 300 | HF-only; 1 cache write / 300 rows | 0 | 295 | LW 5 |
| 14:00 | 286 | HF-only | 0 | 284 | LW 2 |
| 15:00 | 323 | 45-min cadence starting (T12) | 0 | 281 | SS 40, LW 2 |
| 18:00 | 1,201 | 7-day rewind (changelog exact) | 755 | 286 | SS 85, arxiv 73, LW 2 |
| 22:00 | 997 | 60-day rewind, first Search chunk | 667 | 286 | arxiv 35, LW 6, OR 3 |

18:00 matches CHANGELOG: GitHub +755, arXiv +73, Semantic Scholar +85, LessWrong +2. Hugging Face was **not** rewound; it still added 1,721 incremental hub rows across the day.

## Funnel (discovered UTC day, current state)

4,135 discovered → 3,913 reject / 170 still `RELEVANCE_PARKED` / **52 INDEXED**.

| Source | n | Reject | Park | INDEXED |
|---|---|---|---|---|
| github | 2,156 | 93.6% | 107 | 32 |
| huggingface | 1,721 | 99.4% | 11 | 0 |
| semantic_scholar | 125 | 93.6% | 7 | 1 |
| arxiv | 108 | 54.6% | 30 | 19 |
| lesswrong | 22 | 31.8% | 15 | 0 |
| openreview | 3 | 100% | 0 | 0 |

222 gate-1 passes (5.4%): 52 core that fully enriched, 170 still in `/parked`. Park spends the same gate-1 tokens as a core pass and then stops. HF was the expensive reject-well (1,721 rows, 0 INDEXED), not GitHub.

INDEXED Call 2: GitHub 32 (avg 0.64, 17 ≥ 0.7), arXiv 19 (avg 0.57, 6 ≥ 0.7), Semantic Scholar 1 (0.28). High Call 2 is not the quality bar — `github:sseshachala/conductai` (0.72) is in this INDEXED set and was already stamped junk in `eval/github_repo_gate_v0/`.

## Adjacent UTC days (context)

| UTC day | Discovered | Pre-filter rows | GitHub n | GH reject | GH park | GH INDEXED |
|---|---|---|---|---|---|---|
| 11 | 2,475 | 2,204 | 820 | 91.3% | 5.5% | 26 |
| 12 | 2,060 | 2,204 | 873 | 91.6% | 4.6% | 33 |
| 13 | 1,937 | 1,942 | 784 | 92.0% | 6.4% | 13 |
| 14 | 1,911 | 1,911 | 686 | 90.1% | 6.7% | 22 |
| **15** | **4,135** | **4,114** | **2,156** | **93.6%** | **5.0%** | **32** |
| 16 | 2,136 | 2,157 | 566 | 98.2% | 1.1% | 4 |
| 17 | 3,203 | 3,181 | 2,063 | 98.2% | 0.5% | 5 |

Option 1’s reject lift is Sep 16–17 (98.2%), not the mixed 15th. Sep 17 GitHub volume is harvest-tap, not another rewind.

## Do not

- Treat this as overlay revert or promote. Spend is now visible; inbox quality is a separate walk of `/parked`.
- Invent UI token fields or `batches` usage columns from this note (PB-002).
- Cite 4k pre-filter rows/day as steady state.
- Rewind Hugging Face because it “did volume.”

## Related

- Overlay: `.dev/decision-logs/ops/soft-launch-precision-overlay.md`
- Cache amortization (console as of 2026-09-15 08:00 UTC, not the full day): earlier canvas analysis; T12 write-up `.dev/decision-logs/prompt-caching/T12-cache-warmup-ping.md`
- GitHub option 1: `repo-gate-next.md`, `eval/github_repo_gate_v0/`
- Usage hole: `.dev/persist-vendor-payloads.md` (PB-002)
