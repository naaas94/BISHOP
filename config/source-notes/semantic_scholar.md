# semantic_scholar

Adapter: `services/scraper/app/adapters/semantic_scholar.py`  
Shape: **1 — paper** (same law as ArXiv / OpenReview).

## Taste

Same as ArXiv: applied systems and stealable practice, not base-model science. No operator-stamped Semantic Scholar keep/junk list yet. Until one exists, inherit `arxiv.md` + `relevance_log.md` meta. Do not invent a SS-specific quality bar.

## Machine today

- Academic paper feed. Abstracts are real evidence (shape 1).
- Spec backfill window 60 days; live overlay **7 days**.
- Without an API key the public endpoint **429s**. Key is expected in live `.env` (do not print it).
- Gate 1: same pin. No SS-only profile.

## Intel

- 7-day rewind (2026-09-15 faucet open) added on the order of ~85 SS rows. Not labeled.
- No dedicated eval packet. If SS starts flooding like GitHub, freeze a slice before changing fetch.

## Do not

- Treat as a second ArXiv with different gate language.
- Add routing by source.
