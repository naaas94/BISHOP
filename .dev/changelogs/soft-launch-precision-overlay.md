# Soft-launch precision overlay — ad hoc

**Date:** 2026-09-11  
**Decision log:** `.dev/decision-logs/ops/soft-launch-precision-overlay.md`  
**Root changelog:** `CHANGELOG.MD` → “ops — soft-launch precision overlay (ad hoc)”

## Status

**Ad hoc. Not intended behavior.**

This is an operator first-week overlay. It is not a milestone, not charter M9, and not the §11 / §18 steady-state design. Do not cite it as the intended gate when planning the next packet.

## Overlay (temporary)

- Prefilter pin: `professional_v1.2.0_soft_launch.yaml` (precision-first; park peripherals).
- `RELEVANCE_PARKED` + UI `/parked` promote (manifest-only; no scrape/enrich until promote).
- `BISHOP_BACKFILL_WINDOW_OVERRIDE_DAYS=1` on compose (does not rewrite `BACKFILL_CONFIG`).

## Intended (what to restore)

- Prefilter pin `professional_v1.2.0.yaml`.
- `decision=1` → `RELEVANCE_PASSED` for both core and peripheral.
- First-run / backfill windows from `BACKFILL_CONFIG` / `ARXIV_BACKFILL_WINDOW_DAYS`.
- Spec §5.2 / §6.1 without `RELEVANCE_PARKED`.
