# Operator UI docs

Standing folder for **future agents** working on `services/ui`. Cursor rule: `.cursor/rules/bishop-ui.mdc`.

Host on this machine: `http://localhost:8081`.

## What this folder is

The live UI map. Architecture rows in `.dev/architecture/bishop/` still say `GET /` → `/batches` and omit `/dashboard` — trust files here, not that folder.

## Files

| file | what |
|------|------|
| [agent-reference.md](agent-reference.md) | Routes, query-api map, dashboard recipe, rebuild/cache-bust, how to add a page |
| [harvest-dashboard.md](harvest-dashboard.md) | Harvest pool / projected $ card (not live Anthropic; rebuild ui + query-api) |

Add new notes as sibling markdown files and list them in this table. Do not recreate `.dev/ui.md` at the `.dev/` root.
