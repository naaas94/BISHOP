# openreview

Adapter: `services/scraper/app/adapters/openreview.py`  
Shape: **1 — paper**.

## Taste

Conference / workshop papers. Same applied-vs-internals taste as ArXiv. No operator stamps yet.

## Machine today

- Spec backfill window **90 days** (longest of the seven); live overlay **7 days**.
- 7-day rewind (2026-09-15) returned **empty**. Search window / venue query may simply have nothing in a short lookback — confirm against the adapter before calling the source “dead.”
- Gate 1: same pin. Shape 1 abstracts are trustworthy evidence.

## Intel

- Empty short-window pull is the only live signal so far. Do not “fix” OpenReview by widening GitHub or HF.

## Do not

- Invent venue allowlists without a labeled slice.
- Treat empty 7-day as a scraper bug without reading the adapter query.
