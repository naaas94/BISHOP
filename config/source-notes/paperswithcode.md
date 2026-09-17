# paperswithcode

Adapter: `services/scraper/app/adapters/paperswithcode.py`  
Shape: **5 — hub dump** (paper title + method/dataset tags, not a written abstract).

## Taste

A PwC row is a pointer at a paper + claimed methods. Stealability lives in the paper or the linked repo, not in the hub tags. Until the API works again, taste notes are hypothetical.

## Machine today

- Spec backfill window 60 days.
- **Papers with Code API is dead** (as of the 2026-09 faucet / overlay work). Adapter will not fill. Do not treat empty PwC as a lookback-window bug.
- Gate 1: same pin. Shape 5: tags are not an abstract; do not promote to core on method-name match alone.

## Intel

- 7-day rewind: no useful pull (API dead).
- No eval packet.

## Do not

- Build a replacement scrape of paperswithcode.com HTML without a decision log.
- Pretend PwC is a live applied source in dashboards or “open the faucet” plans.
