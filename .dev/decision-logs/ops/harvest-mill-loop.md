# Harvest mill loop — own asyncio cadence (PB-011)

**Date:** 2026-09-17
**Scope:** scraper process, third `asyncio.gather` sibling for GitHub Search harvest.
**Status:** mill loop landed in `services/scraper/app/main.py` (`_mill_loop`).
**Pickup:** this log. Incremental GitHub cutover (PB-012) is not this change.

## Chosen approach

GitHub closed-range harvest (`harvest_github_slices`) runs in `_mill_loop`, gathered beside `_scrape_loop` and `_release_loop` inside the existing scraper process. Each tick builds a fresh `httpx.AsyncClient(timeout=httpx.Timeout(30.0))`, passes a deadline of now + `BISHOP_HARVEST_SLICE_BUDGET_SEC` (90s default), then sleeps `BISHOP_HARVEST_MILL_INTERVAL_SEC` (5s default). Exceptions are logged as `harvest_mill_failed` and the loop retries — same shape as `_release_loop`. There is no `if BISHOP_HARVEST_ENABLED:` around the tick; `harvest_github_slices` already no-ops when that flag is off.

Not a new compose worker. Not a hitchhike on `scrape_cycle` (that call site was already removed). Not a dual-call.

## Alternatives rejected

### (a) Dual-call (keep scrape_cycle hitchhike *and* add a mill loop)

Rejected. Two production callers of `harvest_github_slices` would overlap Search traffic against the same sidecar cursor — double-Search risk, split 429 surfaces, and a mill that still looks "busy" on the 6h tick. Single call site in `_mill_loop` only.

### (b) Reuse `BISHOP_HARVEST_SLICE_BUDGET_SEC` or `BISHOP_HARVEST_RELEASE_INTERVAL_SEC` as the mill sleep

Rejected. Slice budget bounds **work-per-tick** (how long one `harvest_github_slices` call may run). Release interval bounds the paid tap, not Search. The mill sleep bounds **rest-between-ticks**, a distinct axis, so it is a new env: `BISHOP_HARVEST_MILL_INTERVAL_SEC`.

### (c) Shared Search rate-limiter bucket with incremental GitHub `fetch_manifest`

Rejected (no change). Incremental GitHub uses the adapter's REST bucket (`SOURCE_RATE_LIMITS` 5000/3600) and scrape-cycle `failure_envelope` retries on 429. The mill uses a per-call `TokenBucketRateLimiter` at 1 req / 2s on Search (`harvest_github.py:_SEARCH_RATE_LIMIT`) and `_mill_loop`'s broad `Exception` catch + sleep. Those are different GitHub quotas; merging buckets would either starve Search with a REST-sized limiter or cap REST with a Search-sized one. 429 is already handled inside each path.

### (d) A longer default mill interval (reuse 60s release, or something >> 5s)

Rejected as the default. The mill already throttles Search at 1 req / 2s inside `harvest_github_slices`. A short 5s inter-tick sleep does not by itself stack secondary-quota 429s on top of that limiter. A long sleep would idle the 2-year backfill for no quota reason.

## Assumptions made

- `harvest_github.py` reconstructs its rate limiter (`TokenBucketRateLimiter(...)` in `_harvest_into`) on every deadline-bounded call, and `_mill_loop` constructs a fresh httpx client per iteration. A 5s interval therefore does not accumulate open connections or limiter state across ticks. Hoisting the client or limiter to loop scope would invalidate this.
- `BISHOP_HARVEST_MILL_INTERVAL_SEC` already exists in `services/scraper/app/config.py` (T1). This log does not redefine it.
- Compose / `.env.example` passthrough for the new env is **deliberately deferred** as out-of-scope-by-precedent (plan §5.2 assumption 2), not forgotten. Same treatment as `WINDOW_DAYS` / `SLICE_BUDGET` / `QUERY_ID`.

## Items deferred

- Exception-swallow coverage for `_mill_loop`: waived at planning (no dedicated test for sibling `_release_loop` either). Wiring test proves the loop starts.
- Compose / `.env.example` passthrough for `BISHOP_HARVEST_MILL_INTERVAL_SEC`: out of this subtask's files; operator can set the env in the running container until a later passthrough lands.
- `.dev/decision-logs/ops/harvest-pool-first-landing.md` as-built rows still describe harvest after adapters in `scrape_cycle` and the 30s timeout in `loop.py`. That file was not in this subtask's files-to-touch; this log is the mill-loop authority. Banner there is an orchestrator follow-up, not a silent rewrite here.
