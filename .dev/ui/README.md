# Operator UI docs

Standing folder for **future agents** working on `services/ui`. Cursor rule: `.cursor/rules/bishop-ui.mdc`.

Host on this machine: `http://localhost:8081`.

## What this folder is

The live UI map. Architecture rows in `.dev/architecture/bishop/` still say `GET /` → `/batches` and omit `/dashboard` — trust files here, not that folder.

## Files

| file | what |
|------|------|
| [agent-reference.md](agent-reference.md) | Routes, query-api map, dashboard recipe, rebuild/cache-bust, how to add a page |
| [harvest-dashboard.md](harvest-dashboard.md) | Harvest page (`/harvest`): unreleased liability, walk forecast, faucet (not live Anthropic; rebuild ui + query-api) |
| [scrape.md](scrape.md) | Scrape page (`/scrape`): incremental cursors, overlay window, today’s inserts |
| [landed.md](landed.md) | Landed page (`/landed`): indexed window from `GET /recent` |
| [today.md](today.md) | Today page (`/today`): UTC-day glance (discovered, scrape health, harvest one-liner, cohort) |
| [design.md](design.md) | As-built look (FRS first pass in `style.css`). Not locked. Gold = focus; `is-*` = health |

Doctrine (dashboard vs dedicated pages, query-api env recreate): `.dev/decision-logs/ops/2026-09-27-operator-ingest-pages.md`.

Add new notes as sibling markdown files and list them in this table. Do not recreate `.dev/ui.md` at the `.dev/` root.
