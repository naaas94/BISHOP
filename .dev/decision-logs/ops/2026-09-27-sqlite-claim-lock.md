# Claim polls hold the SQLite write lock past the busy timeout

**Date:** 2026-09-27
**Status:** resolved 2026-09-27 21:48 ART. The remediation below is applied.
**Scope:** state-worker claim polls on `bishop.db`, the scraper process (incremental scrape and the GitHub mill), the pre-filter worker, and three pre-filter batches the poller is still retrying.

Live file: `C:/Users/Ale/bishop_data/sqlite_live/bishop.db`. `PRAGMA quick_check` = ok. This is not the 2026-09-11 leaked-transaction failure: state-worker logged no `sqlite_pool_rollback_on_release` in the last 8h, and `/health/db` stays 200.

## What is down

| Container | State at investigation | Exit |
|---|---|---|
| scraper | Exited 2026-09-27T21:15:40Z | 1, `httpx.ReadTimeout` in `post_scraper_state` |
| pre-filter-worker | Exited 2026-09-27T23:22:30Z | 1, `httpx.ReadTimeout` in `register_batch` |
| state-worker, query-api, ui, batch-poller, content-scraper, enrichment-batcher, vector-writer | Up | — |

The mill runs in the scraper process (`asyncio.gather` with the scrape loop). Harvest stopped with it. Cursor `harvest_cursor` github `updated_at` is `2026-09-27T21:15:18Z`, `walk_direction=forward`, `next_window_start=2026-09-27T21:14:41Z`.

Incremental cursors in `scraper_state` were last stamped on the startup cycle at 15:15Z (github, huggingface, lesswrong, openreview, paperswithcode). Arxiv is `2026-09-27T23:59:59Z` (day walk already finished). Semantic Scholar is still `2026-09-20T20:45:29Z` from the earlier 429 stall. That one is FU-005, not this outage.

The 21:15Z scrape cycle had already posted the GitHub manifest (`POST /manifest/batch` 200) and then died on the cursor stamp. A restart re-fetches from 15:15Z. Inserts of rows already stored are skipped.

## Root cause

Claim polls take the only WAL writer and then scan the whole table.

`claim_manifest_poll` and `claim_entries_poll` run `BEGIN IMMEDIATE` and then `SELECT * … WHERE processing_state = ? ORDER BY … LIMIT 50`. The only indexes on those tables are the primary key and `entries.source_id`. `EXPLAIN QUERY PLAN` is `SCAN` plus a temp B-tree for the `ORDER BY`.

Timed read-only, same SQL, against the live file:

| Where | Query | Time | Rows matched |
|---|---|---|---|
| Windows host | manifest `DISCOVERED` | 0.08s | 50 |
| `bishop-state-worker-1` | manifest `DISCOVERED` | 6.06s | 50 |
| `bishop-state-worker-1` | manifest `RELEVANCE_PASSED` | 5.45s | 0 |
| `bishop-state-worker-1` | entries `SCRAPED` | 8.91s | 0 |

An empty queue still reads every row, including `entries.content_raw`, across the Docker bind mount. The write lock is held for that whole scan.

`SQLITE_BUSY_TIMEOUT_MS` is 5000. A scan of 5.4–8.9s means every other `BEGIN IMMEDIATE` that overlaps it gives up and raises `sqlite3.OperationalError: database is locked`. In the 8h before 00:31Z, state-worker logged 307 of those. The waiters were mostly `claim_entries_poll` (169) and `apply_pre_filter_results` (72). They were still arriving at about one or two a minute after the scraper and pre-filter had already exited. Enrichment runs stage 1 and stage 2 claims together every 120s. Content-scraper claims `RELEVANCE_PASSED` every 120s. Pre-filter, while it was up, claimed `DISCOVERED` every 60s.

The scraper and pre-filter httpx clients use the library default timeout of 5s. That is the same number as the busy timeout, so the client gives up as the server gives up. `_scrape_loop` does not catch that exception (the mill loop and the release loop do). `register_batch` only catches `HTTPStatusError`. The poll path on pre-filter was wrapped this morning. The register path was not. Either timeout ends the process.

`manifest` is 66,190 rows. `entries` is 1,750. WAL is about 45MB, past the 4MB autocheckpoint, which makes each scan slower. The host-versus-container gap is the bind mount. An index on the filter column is what stops the scan from reading every blob while it owns the writer.

## Second fault, still running

Three pre-filter batches are not `complete` or `failed`. All 150 `source_ids` are already `RELEVANCE_REJECTED` with `relevance_decision` 0, and `pre_filter_batch_id` is a different batch on every row.

| batch_id | status | created (UTC) |
|---|---|---|
| `0de20a4f-1872-4a8e-aa15-d8c02b3c280d` | processing | 2026-09-26T23:45:58Z |
| `b182fa76-177a-4e76-aba7-6881c283a7d5` | submitted | 2026-09-27T02:23:30Z |
| `fcdebb59-bded-4913-ad05-77582ebb3fe3` | processing | 2026-09-27T02:54:02Z |

`apply_pre_filter_results` calls `_guard_terminal` before the same-batch idempotent check. `RELEVANCE_REJECTED` is terminal, so the POST returns 409 `terminal_state` and rolls back. The poller only stops retrying on 409 `invalid_transition`. `terminal_state` is logged as `results post failed` and tried again next cycle. 689 of those in 8h. The interval is 120s, three posts per cycle, and the errors were still landing at 00:33Z.

`patch_batch` updates the `batches` row only. It does not move `manifest`.

## Impact

- No incremental discover and no GitHub mill since 21:15Z.
- No new Gate 1 submits since 23:22Z. 5,696 rows are sitting in `DISCOVERED`. That backlog was already there. The crash stopped it draining.
- The register that timed out had already received Anthropic `POST /v1/messages/batches` 200. No `batches` row was created at 23:22Z (newest pre-filter `complete` is 23:20:14Z). The external id was only logged after a successful register, so that batch is an orphan. `RELEVANCE_QUEUED` is 0, so the sweep is not holding those rows in the claim state.
- Enrichment was still completing batches through 23:33Z. Content has nothing in `RELEVANCE_PASSED`. One entry is in `VECTOR_WRITE_QUEUED`. `POST /entries/indexed` returned 503 `database_locked` 49 times in 8h. Vector-writer stays up.
- Downstream of Gate 1 is draining. The front of the pipe is stopped.

## Remediation

Applied 2026-09-27 21:48 ART. Restarting the two workers without the index would have put the 6-second lock back on a 60-second pre-filter poll.

1. **Index the claim filters.** New Alembic revision: `manifest(processing_state, discovered_at)` and `entries(processing_state, ingested_at)`. Rebuild and recreate state-worker. Re-time the same three queries inside the container. Done when each is well under a second, so a 5s busy timeout stops being the steady state.
2. **Keep a slow state-worker from exiting the worker.** Catch `httpx.TimeoutException` and `httpx.TransportError` around `scrape_cycle` and around `register_batch`, the same way the mill loop and the pre-filter poll already do. Set the scraper and pre-filter state-worker clients to 60s, matching content-scraper, enrichment, and vector-writer. Rebuild those two images and start them with `--no-deps` so state-worker is not recreated again.
3. **Stop the 409 loop in code.** A pre-filter result for a row already in `RELEVANCE_REJECTED` or `INDEXED` should skip that row and still return 200, so the poller can mark the batch complete. The poller should also treat 409 `terminal_state` the way it treats `invalid_transition` and stop retrying. Do not move those rows back to `DISCOVERED`.
4. **Optional, before the rebuild.** `PATCH` the three batch ids above to `failed` so the poller stops downloading their Anthropic results every two minutes. Safe only because `patch_batch` does not touch `manifest`, and those judgments are already stored under other batch ids.

Raising `busy_timeout` on its own is the wrong knob. Waiters would block for the length of the scan and sit on the pool of five connections.

Leave the orphan Anthropic batch. One submit of about 50 rows, external id not in our logs. Leave Semantic Scholar on FU-005.

## Landed

Alembic `m8_002_claim_poll_indexes`. Recreated `bishop/state-worker:m1`. Inside the container the same three queries are now index searches: manifest `DISCOVERED` 0.009s (was 6.06s), `RELEVANCE_PASSED` 0.001s (was 5.45s), entries `SCRAPED` 0.046s (was 8.91s).

Scraper and pre-filter catch `TimeoutException` and `TransportError` and use a 60s state-worker client. Rebuilt `bishop/scraper:m8`, `bishop/pre-filter-worker:m3`, and `bishop/batch-poller:m5`. Started with `--no-deps`. Scraper stamped the empty arXiv day 2026-09-28 (`204`). Pre-filter registered a batch (`201`). All three stayed up. No `database is locked` in the first two minutes.

Batch-poller was stopped first. The three batches were `PATCH`ed to `failed`. A sample manifest row stayed `RELEVANCE_REJECTED` under the other batch id. The poller now settles `terminal_state` the same way as `invalid_transition`. A results POST skips a terminal row instead of failing the batch. After restart those three ids were still `failed` and were not reloaded.
