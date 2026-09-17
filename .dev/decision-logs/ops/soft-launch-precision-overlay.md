# Soft-launch precision overlay (ad hoc)

**Date:** 2026-09-11  
**Scope:** ops / first-week launch — not a milestone packet  
**Status:** Ad hoc overlay. **Not the intended steady-state behavior.**

## Verdict

This is a temporary, operator-requested launch posture. It is not a charter slice, not an M8 continuation, and not the §11 / §18 design.

Revert or formally promote it after the first-week spend and inbox quality are visible. Until then, treat every pin, state, and env default below as overlay — not as the new contract.

## Intended behavior (what this is not)

| Surface | Intended (pre-overlay) |
|---------|------------------------|
| Prefilter pin | `professional_v1.2.0.yaml` (calibrated, recall-first: uncertain → peripheral **pass**) |
| Enrichment pin | `professional_v1.0.0.yaml` (unchanged by this overlay) |
| Gate-1 `decision=1` | `RELEVANCE_PASSED` regardless of `pre_filter_tier`. Tier is provenance for later scoring, not a spend gate. |
| `RELEVANCE_REJECTED` | Terminal. No recoverability path. |
| First-run / backfill windows | `BACKFILL_CONFIG` per source (e.g. arxiv 60) when chunked backfill is on; ArXiv incremental first-run `ARXIV_BACKFILL_WINDOW_DAYS=7` |
| UI | No parked inbox. Explorer/search are INDEXED / entries only. |
| Spec §5.2 step 8 / §6.1 | `decision=1` → PASSED; `decision=0` → REJECTED. No `RELEVANCE_PARKED`. |

## Overlay that landed (ad hoc)

1. Prefilter pin → `professional_v1.2.0_soft_launch.yaml`. Precision-first: core only when the item is a working reference this week (`applied_systems`, `dev_skills`, or a build-from anchor). Uncertain / adjacent → park.
2. `decision=1` + `tier=peripheral` → `RELEVANCE_PARKED` on the manifest. No scrape, no enrichment, no index. Title + abstract stay readable.
3. Manual promote `RELEVANCE_PARKED` → `RELEVANCE_PASSED` (`POST /parked/promote`, query-api proxy, UI `/parked`). Then the existing scrape → enrich → index path runs.
4. `BISHOP_BACKFILL_WINDOW_OVERRIDE_DAYS` (compose default `60` as of 2026-09-15 after option 1; was `7`, originally `1`) caps cold-start lookback for every registered source without editing `BACKFILL_CONFIG`. Still overlay — not spec §18.2 windows.

## Why overlay, not a milestone

- Spec §18.1: backfill uses the same pipeline as steady state — no special mode.
- Spec §11 / v1.2.0: peripheral is a **pass** class (16 of 49 gold passes). Parking it changes the calibrated gate.
- Adding `RELEVANCE_PARKED` to `ProcessingState` and spec §6.1 is a contract mutation made so the overlay is executable, not because the intended machine gained a new happy-path state.
- The lookback overlay is a spend cap for first-week multi-source noise (GitHub, hubs, paper feeds). Originally 1 day; retuned to 7, then **60** on 2026-09-15 after option 1 Shape 2 went live. The intended windows stay in `BACKFILL_CONFIG`.

## Revert / promote

**Revert (return to intended):** pin prefilter back to `professional_v1.2.0.yaml`; restore `apply_pre_filter_results` so `decision=1` → `RELEVANCE_PASSED`; drop or ignore `/parked`; unset `BISHOP_BACKFILL_WINDOW_OVERRIDE_DAYS`; restore spec §5.2 step 8 and §6.1; decide what to do with any live `RELEVANCE_PARKED` rows (promote, reject, or leave).

**Promote (make intended):** a later packet that owns enum + spec + eval replay against the parked bar, and a recoverability story that is not a one-off inbox.

## Alternatives rejected for this overlay

| Option | Rejected because |
|--------|------------------|
| Rewrite `BACKFILL_CONFIG` to 1 day | User asked not to change the whole config; overlay env keeps spec defaults. |
| Park by rejecting (`decision=0`) | Rejection is terminal; the operator wanted recoverability + later promote. |
| Dual pipeline / special backfill worker | Violates §18.1 “same pipeline”; overlay stays on existing workers plus a promote route. |
| Wait for M9 source-expansion | Overlay is spend control on the sources already registered, not a new source class. |

## Files (overlay surface)

- `config/profiles/professional_v1.2.0_soft_launch.yaml`
- `bishop_shared/profile_renderer.py` (`_PROFILE_FILENAME` prefilter pin, `peripheral_disposition`)
- `services/state-worker/app/enums.py` (`RELEVANCE_PARKED`)
- `services/state-worker/app/transitions.py` (`_pre_filter_target`, `list_parked_manifests`, `promote_parked`)
- `services/state-worker/app/routers/parked.py`
- `services/query-api/app/routers/parked.py`
- `services/ui/app/templates/parked.html` + `/parked` routes
- `services/scraper/app/config.py` / `loop.py` (`BISHOP_BACKFILL_WINDOW_OVERRIDE_DAYS`)
- `docker-compose.yml` (override default `60` as of 2026-09-15 after option 1; was `7`, originally `1`)
- `bishop_spec_0_6.md` §5.2 step 8 and §6.1 (overlay-shaped; revert with the overlay)
