# Harvest mill walks backward

**Date:** 2026-09-27
**Scope:** GitHub harvest mill cursor direction only. Not release, economics, N_cap, or incremental scrape.

## Plan (executed)

Live `harvest_cursor` at plan time (re-read, mode=ro): `next_window_start=2024-12-15T20:18:40Z` (floor; parent brief's 2024-12-10 had already advanced), `harvest_until=2026-09-17T14:18:40Z` (frozen ceiling), no direction column. Old mill still walking forward.

### Marker

Two columns on `harvest_cursor`, added with idempotent ALTER (CREATE TABLE IF NOT EXISTS will not change the live table):

- `walk_direction` TEXT: NULL = legacy never-flipped; `backward` = filling the gap; `forward` = caught-up.
- `high_water` TEXT: ISO timestamp of the flip `now`. Restored onto both edges when the gap is done.

Restart-safe rule: if `walk_direction == 'backward'`, never set `harvest_until` to now just because it is stale.

### Which column moves

- Floor `next_window_start` stays put during the backward walk.
- High edge `harvest_until` retreats to the start of each persisted slice.

### First tick (legacy row)

If `walk_direction` is NULL and `next < until`: flip once — `harvest_until = now`, `high_water = now`, `walk_direction = 'backward'`. First slice is `[max(floor, now-7d), now]`. Floor unchanged.

### Later ticks / restart

Already `backward`: do not flip, do not bump `harvest_until`. Next slice is `[max(floor, until-7d), until]`.

### Overflow

Wide overflow: fetch the newer half `[mid, end]` first (`pending_start = mid`). One-day overflow: cap 10 pages, then retreat `harvest_until` to `start` (no stall).

### Done

When `until <= floor`: write both edges to `high_water`, set `walk_direction = 'forward'`. Do not delete pool rows. After that, the old bump-until + forward walk covers days that arrive later.

### Fresh cursor

Init as `backward` with `high_water = now`, `next = now - WINDOW_DAYS`, `until = now`.

### Out of scope (stop if the plan needs these)

Release SQL, economics yaml, `$4.52` env, N_cap, incremental `fetch_manifest` / DISCOVERED, Hugging Face, paper exhaust.

## Live after scraper rebuild (2026-09-27)

`bishop/scraper:m8` rebuilt; only `scraper` recreated. First tick flipped the live row:

- Floor `next_window_start` stayed `2024-12-15T20:18:40Z`
- `walk_direction=backward`, `high_water=2026-09-27T10:07:56Z`
- First persisted slice: `pushed:2026-09-25..2026-09-27 stars:>10` (newer-half leaf of `2026-09-20..2026-09-27`, 10-page overflow cap, 964 upserts)
- High edge then retreated to `2026-09-25T16:07:56Z`
