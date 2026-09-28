# arXiv export cursor stuck

**Date:** 2026-09-27
**Scope:** Incremental arXiv manifest fetch (`export.arxiv.org`). Not Semantic Scholar, not the GitHub mill, not the category gate, not the profile pin.

## What the red bar was

`/scrape` headline **237.7h behind (arxiv)** is `scraper_state.last_successful_run_at` for arxiv, **2026-09-17T14:20:27Z**, against a 6h tick (`21600s`). `today 0 · queue 0` is zero `manifest` rows discovered since UTC midnight and zero arxiv rows in `DISCOVERED` or `RELEVANCE_QUEUED`.

Live DB is `C:/Users/Ale/bishop_data/sqlite_live/bishop.db` (compose mounts `sqlite_live`). Newest arxiv row: published **2026-09-15T17:55:28Z**, discovered **2026-09-16T04:24:11Z**. Papers submitted after that were absent. There was no backlog job waiting to run.

Same morning, github / huggingface / lesswrong / openreview had all stamped **2026-09-27T10:07:56Z**. Semantic Scholar was a separate stall: last success **2026-09-20T20:45:29Z**, and that tick’s call was **429**. This change does not touch it.

The GitHub mill walking backward (first slice `pushed:2026-09-25..2026-09-27`) is a different pipe. It does not fetch arXiv.

## Why the cursor did not move

`scrape_cycle` stamps `last_successful_run_at = now` only after `fetch_manifest` returns and the manifest POST succeeds. A thrown adapter error leaves the cursor where it is.

The 10:07 UTC tick (scraper container started for the mill flip) logged:

`GET https://export.arxiv.org/api/query?search_query=(cat:cs.AI OR cat:cs.CL OR cat:cs.LG) AND submittedDate:[20260917000000 TO 20260927235959]&max_results=100` → **406**

Then `Permanent adapter failure` for arxiv. 406 is not in the retriable set `{429, 500, 502, 503, 504}` and not in the escalatable set, so `failure_envelope` raises `PermanentFailureError` on the first response. No retry. No state POST. The other adapters in that cycle still ran.

The machine-off window 22–25 Sep added calendar time. The cursor was already frozen on the 17th, before that outage, and the first tick after the machine was back failed the same way. This container only kept the 10:07 cycle; earlier 406s are inferred from the cursor, not from retained logs.

## What the 406 actually was

Fastly in front of `export.arxiv.org`, not an arXiv query error.

| Client | Query | Result |
|---|---|---|
| Windows host, httpx 0.28.1, OpenSSL 3.0.18, fresh date window | 200, `via` includes `1.1 google`, `x-cache` MISS | Atom feed |
| `bishop-scraper-1`, httpx 0.28.1, OpenSSL 3.5.7, **httpx’s default SSL context**, fresh date window | **406 empty**, `via: 1.1 varnish, 1.1 varnish` only, `cache-control: private, no-store` | Never reached arXiv |
| Same container, **same httpx context with `maximum_version` TLS 1.2**, fresh date window | 200, `via` includes google, `x-cache` MISS MISS MISS | Atom feed |
| Same container, default context, URL already cached at Fastly | 200, `x-cache` HIT | Cached feed |
| Same container, custom User-Agent, uncached date window | 406 | User-Agent was not the switch |

Public egress IP was the same (`201.159.62.23`). DNS for `export.arxiv.org` was the same Fastly address (`151.101.219.42`). The scraper image is `python:3.12-slim`. Its default handshake is what Fastly refuses. TLS 1.2 on that context is what Fastly forwards.

The live scrape URL is a new `submittedDate` window, so it is a cache miss every day. A miss 406’d. A hit from somebody else’s earlier 200 would have looked healthy and still would not have been this scraper’s request.

Probed from the host, that 17–27 Sep window of `cs.AI` / `cs.CL` / `cs.LG` had **`totalResults` 2211**.

## Why a green tick would still have dropped the gap

Before this change, `fetch_manifest` sent one request, `max_results` 100 (`BISHOP_ARXIV_MAX_RESULTS`, default 100), no `start`, no sort. On success the loop stamped `now`. The next tick’s `since` would be that stamp, so the other ~2,100 papers would never be requested.

Backfill chunks run only when `last_successful_run_at` is null. arXiv has a cursor, so the tick is incremental `[since, end of today]`, not a backfill.

Healthy days in early September inserted about 100 arxiv rows per successful discovery day. That is the one-page cap, not the size of the categories.

## What changed

- `arxiv_export_ssl_context()` — httpx SSL context, `maximum_version` TLS 1.2. Used only when the export adapter creates its own client. Injected clients (tests) and the HTML full-text client are unchanged. Other sources stay on the default handshake; they were succeeding.
- `_page_export` — `start` / `max_results`, `sortBy=submittedDate`, `sortOrder=ascending`. Stop on a short page or when the next offset passes `opensearch:totalResults`. Stop uses the raw Atom entry count, then the category gate runs once on the whole window, so a page the gate would shrink is not treated as the last page. 3 seconds between pages (`ARXIV_INTER_PAGE_DELAY_SEC`). Duplicate `source_id`s across pages are dropped.
- A window that is still a full page at `start` 30,000 raises `PermanentFailureError`. The cursor stays. The export API will not return past that, and stamping `now` would drop the tail.
- A later page that raises (406, 5xx, the cap) never returns a partial list. `scrape_cycle` already skips `post_scraper_state` on that path. Rows posted by an earlier chunk of a failed POST stay; the next tick fetches the window again and manifest ingest skips existing `source_id`s.
- `_post_manifest_chunks` — manifest POSTs of more than 100 rows go out 100 at a time (`MANIFEST_POST_CHUNK`). The state-worker client timeout is httpx’s 5s default; one body of ~2,200 abstracts can miss it, the POST fails, and the cursor stays, which would look like “still stuck” after the TLS fix. Empty fetches still POST once.

## How to tell it worked

Rebuild and recreate `scraper` (`bishop/scraper:m8`). Startup runs a scrape cycle immediately.

Worked:

- Scraper log shows `export.arxiv.org` **200**, several pages (`start=0`, `100`, `200`, …), then `scraper state updated` for arxiv.
- `scraper_state` arxiv `last_successful_run_at` moves off 2026-09-17.
- New `manifest` rows with `source='arxiv'` and `published_at` after 2026-09-15, on the order of the gated subset of those 2,211. The category gate still drops excluded primaries. The bar is not the check: it goes green as soon as the cursor moves.

Not worked:

- One 406 and `Permanent adapter failure` for arxiv. Cursor still 2026-09-17. The running image is the old one, or Fastly started refusing TLS 1.2 as well.
- Cursor moved and only ~100 new arxiv rows appeared. Paging did not run.

Those new `DISCOVERED` rows enter Gate 1 on the normal pre-filter poll. They are outside `N_cap` (that cap is the GitHub harvest tap). The category gate is still `enforce: false` (`config/sources/arxiv.yaml`), so it logs skips and drops nothing. At the 2026-09-27 observed ~$0.00046 per judged row, the whole window is on the order of **$1** of Haiku.

## Live after the scraper rebuild (2026-09-27)

`docker compose up -d --build scraper` also recreated `state-worker` (compose dependency). It came back healthy.

Startup cycle, from `bishop-scraper-1` logs and `sqlite_live`:

- Export pages `start=0` through `start=2200`, every one **200**. No 406.
- Category gate ran, then manifest chunks posted, then the arxiv cursor stamped.
- `last_successful_run_at` = **2026-09-27T12:21:08Z** (captured at the start of the fetch; paging took about a minute).
- **2,211** new `manifest` rows, `source=arxiv`, `discovered_at` 2026-09-27T12:22Z, all `DISCOVERED`. That matches `totalResults`. Newest `published_at` in the window: **2026-09-24T17:59:54Z** (`arxiv:2609.30266`).
- Same cycle: GitHub, Hugging Face, LessWrong, and Papers with Code stamped. OpenReview retry-exhausted and stayed on **10:07 UTC**. Semantic Scholar still **429**, cursor still **2026-09-20**. Neither is this change.

## Correction — do not stamp now (2026-09-27 afternoon)

The first rebuild paged 17–27 Sep in one query and stamped `last_successful_run_at` to **2026-09-27T12:21:08Z**. That is a jump. Days inside the 60-day overlay that had only received the old 100-result page stay behind the cursor and would never be fetched again.

Checked against the export API the same afternoon (TLS 1.2, one calendar day, `totalResults`):

| Day | API | In the DB before the day walk |
|---|---|---|
| 2026-07-29 | 343 | 2 |
| 2026-09-09 | 307 | 104 |
| 2026-09-15 | 332 | 100 |
| 2026-09-16 | 338 | 0 |
| 2026-09-25 .. 27 | 0 | 0 |

17–24 Sep summed to the 2,211 that were inserted. 25–27 Sep are empty on the API (nothing announced). The holes are the earlier overlay days.

Pre-filter was already dead: `bishop-pre-filter-worker-1` had exited on `httpx.ReadTimeout` while polling state-worker, and that exception was not caught, so the process ended. No Anthropic submit ran against the 2,211 `DISCOVERED` rows. A poll timeout now logs and the loop continues.

### Day walk

arXiv incremental scrape no longer fetches `[cursor, now]` and stamps `now`. Each cycle walks UTC calendar days from the cursor through today:

- A cursor at **23:59:59** means that day is done. The next day starts the next morning.
- Any earlier timestamp is a jump. The walk restarts at the overlay floor (`BISHOP_BACKFILL_WINDOW_OVERRIDE_DAYS`, live **60**, so 2026-07-29 on this date).
- One day is paged to the end, posted, then the cursor is stamped **23:59:59 of that day**. A failed day does not stamp. The cursor is never moved to `now`.
- An empty day (25–27 Sep) still stamps, so the walk does not stall on a day the API says is empty.
- 3 seconds between days, and still 3 seconds between pages inside a day.

Days older than the overlay stay as they are. June and 17–28 Jul are outside today’s 60-day pin.

## Code map

- `services/scraper/app/adapters/arxiv.py` — TLS 1.2 context, paged export, 3s gap, 30k ceiling.
- `services/scraper/app/loop.py` — chunked manifest POST on the incremental path and the cold-start backfill path. Cursor stamp is still the line after a successful post.
- `tests/test_scraper_arxiv_adapter.py` — TLS cap, two-page window, second-page 406 raises, cap does not return a finished window.
- `tests/test_scraper_loop.py` — chunks post before the stamp; a failed later chunk does not stamp.
- Source note: `config/source-notes/arxiv.md`. Scrape page note: `.dev/ui/scrape.md`.
