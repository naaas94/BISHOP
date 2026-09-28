# arxiv

Adapter: `services/scraper/app/adapters/arxiv.py`  
Shape: **1 — paper** (real abstract). Highest-evidence academic shape.

## Taste

Operator wants **applied** systems, architecture of products (not of the base model), skills, workflows, shipped practice. ArXiv’s nature is paper-coded: pretraining, weights, internals, experimental SOTA. That is often on-topic for “AI” and still the wrong flavor.

From `relevance_log.md` (soft-launch):

- `arxiv:2606.11375` — pretraining, not applied engineering; Call 2 0.35
- `arxiv:2606.11722` — LLM internal representations; interesting as a summary, not the niche
- Overall: “too aie based but not in the way I’m interested in; applied, systems, architecture but not of the llm itself”

Logged keep (rare, write more as they appear):

- `arxiv:2607.19592` — Knowledge-Centric Self-Improvement

Cross-source want-list (also in `relevance_log.md` meta): skills, WFs, knowledge you don’t possess, LLM-based **systems**, architectures, reviews, stacks, techniques, agents, eval, observability, backend, quantification of results, explainability, stakeholder management — tied to the professional profile.

## Machine today

- Queries `cs.AI`, `cs.CL`, `cs.LG`.
- Zero-cost **category gate** (primary category only): `config/sources/arxiv.yaml`. Do not switch to any-category matching — cross-lists are noisy (`eval/prefilter_v0`). Empty `include_categories` is intentional; exclusion list does the work.
- Spec backfill window 60 days. Live overlay is **60 days** (since 2026-09-15). The earlier “currently 7 days” line was the soft-launch overlay before that retune.
- Gate 1: same pin as every source. Do not invent an ArXiv-only profile because papers “feel academic.” Tighten taste in the **shared** profile/rubric, or accept that ArXiv will keep producing paper-shaped passes.

## Intel

- Soft-launch mix: ArXiv **pass rate is high** relative to HF/GitHub, but many passes are the wrong flavor (research internals vs stealable practice). That is a taste/profile problem, not a fetch-floor problem.
- Gold set for the **shared** prefilter (not ArXiv-only): `eval/prefilter_v0/`. Do not edit `items.json` after freeze.
- **2026-09-27 — export cursor stuck.** Last success `2026-09-17T14:20:27Z`. Newest row in the live DB was published 2026-09-15. `today 0` / `queue 0` because nothing was discovered, not because a queue was waiting. The 10:07 UTC tick got an empty **406** from Fastly in front of `export.arxiv.org` (varnish only, no Google hop). Same URL from the Windows host (OpenSSL 3.0) returned 200 and `totalResults` **2211**. Inside `bishop-scraper-1` (image `python:3.12-slim`, OpenSSL 3.5) a fresh date-window query 406’d; the same httpx SSL context capped at **TLS 1.2** was a cache miss that reached arXiv and returned 200. A custom User-Agent did not clear the 406. 406 is a permanent adapter failure, so the tick did not retry and did not stamp `last_successful_run_at`. Fix: TLS 1.2 on the export client, page `start` until the window is done (`sortBy=submittedDate`, 3s between pages), POST in chunks of 100, stamp the cursor only after the whole window is fetched and posted. A window still full at 30,000 hits raises and leaves the cursor. The scrape bar goes green when the cursor moves, including if a future bug stamps early — success is new `arxiv` rows with `published_at` after 2026-09-15. Write-up: `.dev/decision-logs/ops/2026-09-27-arxiv-export-stuck.md`. Rebuilt `bishop/scraper:m8` the same morning: pages `start=0..2200` all 200, cursor moved to **2026-09-27T12:21:08Z**, **2,211** rows inserted as `DISCOVERED` (gate `enforce: false`, so nothing was dropped). Semantic Scholar’s red row that morning was a separate **429** and was still 429 after this cycle.
- **2026-09-27 afternoon — do not stamp now.** The 12:21 UTC cursor was a jump. Overlay days behind it are partial (9 Sep is 104 stored of 307 on the API; 16 Sep is 0 of 338; 29 Jul is 2 of 343). 25–27 Sep are empty on the API. The walk now does one UTC day, pages it, posts it, stamps **23:59:59** of that day, then the next day. A midday cursor restarts at the 60-day floor (2026-07-29). Pre-filter had exited on a poll `ReadTimeout`, so those rows had no Anthropic submit; a poll timeout no longer kills the process.

## Do not

- Treat Call 2 as gold.
- Expand categories or any-category matching without replaying `eval/prefilter_v0`.
- Drop ArXiv from the registry because the flavor is wrong — document and calibrate; the applied sources (GitHub first) are the faucet we open after the repo bar is fixed.
- Treat a green `/scrape` arXiv bar as proof every day was collected. The cursor is the end of the last **finished UTC day** (`23:59:59`). A midday stamp is a jump: the next cycle re-walks from the overlay floor instead of continuing from today.
- Stamp `last_successful_run_at` to `now` after an arXiv fetch. That skips every day the fetch did not finish. One calendar day is paged, posted, then stamped. The next day starts only after that stamp.
