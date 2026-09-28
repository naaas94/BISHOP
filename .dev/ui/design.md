# Operator UI — design

As-built in `services/ui/static/style.css` (2026-09-27 first pass). Rebuild `ui` after edits (`bishop/ui:m8` bakes the sheet). Taste source: FRS hub / knowledge map (`C:/Users/Ale/Documents/Repos/frs`). That repo is not a Bishop spec.

**Operator 2026-09-27:** landed, not loved. Iterate. Do not treat this pass as locked taste or copy FRS harder to “finish” it.

Gold is focus (active nav, input focus, links). Health is `is-ok` / `is-warn` / `is-bad` / `is-dead`. Do not paint lag with the same red as a closed tap.

## Tokens (dark)

| Token | Value | Use |
|-------|-------|-----|
| `--bg` | `#080808` | Page |
| `--panel` | `#0b0b0b` | Header, inputs |
| `--card` | `#0d0d0d` | Stat tiles, heroes |
| `--border` | `#1e1e1e` | Hairline |
| `--fg` | `#e0e0e0` | Titles and numbers |
| `--muted` | `#686868` | Labels, `h2` eyebrows |
| `--faint` | `#505050` | Dead source |
| `--gold` | `#c8a96e` | Focus, current nav, links |
| `--gold-bg` / `--gold-line` | `#16120c` / `#4a4030` | Filled control hover |
| `--st-ok` | `#4ade80` | Caught up, tap open |
| `--st-warn` | `#fb923c` | Stale lag (two ticks) |
| `--st-bad` | `#f87171` | Headline lag, overshoot, `.error` |
| `--mono` | SF Mono / Fira Code / Roboto Mono | Eyebrows, meta, counts |
| `--sans` | system-ui | Body, `h1`, hero numbers |

Light keeps the same structure on `#f6f7f9` / `#1a1d21`. Gold is `#8a6a32`. Status colors are the darker set in `:root`. `color-scheme: light dark` stays.

## Layout

- Square corners. Stat grid gap 3px. Column 1100px.
- `h1` / `.brand` / `.stat-value` / `.harvest-hero-value`: weight 300, tabular.
- `h2` is the eyebrow (mono, 11px, 0.18em tracking, uppercase).
- Bars: 6px, no radius. `.bar-row` is the funnel/lag row. Do not import AIE `.sbar`.
- `.error` is a panel (`--error-bg` / `--error-line`), still HTML 200.
- `nav a[aria-current="page"]` is gold. Brand is not.

Classes: scrape hero `is-ok` / `is-bad`; source row `is-warn` / `is-dead`; harvest released bar `is-bad` on overshoot; faucet note `is-ok` when the tap is open.

## Rationale

The console is cursors and dollars, read in the dark, one baked image. Near-black, hairline gray, mono for structure, sans for the number, gold only when something is selected. That was the first-pass bet, not a closed look.

## Do not

- Tailwind, a second CSS file, Chart.js, or the knowledge-map graph/drawer.
- Rename `.bar-row`.
- Put harvest or scrape card grids back on `/dashboard`.
- Treat `frs` deck HTML or `BISHOP_NOTES.md` as this system.
- Freeze this first pass as “the Bishop look.” Next edits go through the operator, not another FRS copy.
