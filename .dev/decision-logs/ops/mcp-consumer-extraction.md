# MCP consumers, extraction, and action (scoping)

**Date:** 2026-09-16  
**Scope:** product / MCP — who retrieves, who extracts, who applies  
**Status:** Documented, not a plan. No MCP server, no schema, no code.

Tracked as PB-010. Live notes: `mcp-agent-tool-notes.md`.

## Verdict

Bishop is the **shared pantry** (triage index). Consumers are the **kitchen** (extract + apply).

Do not fold value-scout findings into Call 1/2 fields or the VDB. Do not extend `processing_state` past `INDEXED`. Do not reuse `reading_status` for agent consumption. v1 MCP is read-only. A later sidecar may store a scout *artifact* against `source_id`; that is memory of “we looked,” not application of the insight.

Lightweight experiment **before** scaling v2: one real task, a few Bishop hits, scout by hand. Count how many findings are about the *artifact* vs *this task*. That decides whether Bishop ever owns an extract channel.

## What the corpus actually is

Search hits are enrichment **cards** (title, Call 2 summary, tags, score). `get_entry` adds `url` + `content_raw` (GitHub README; ArXiv HTML paper text when `arxiv.org/html/{id}` exists, else title+abstract). The PDF / repo tree is not stored. An agent that needs the artifact still follows `url`.

## Layers (do not collapse)

| Layer | Whose job | Why |
|---|---|---|
| How to *use* Bishop | Bishop, once, general | Tool contract: hit = card, `get_entry` = blob, URL = artifact. One consumer note / MCP prose. Per-consumer only if ops-Bishop vs research-Bishop splits. |
| Extract *what the source is* | Can live in Bishop later | Artifact-level: “README is a landing; stealable core is X.” Helps any later search. Earned only if the experiment shows density. |
| Extract *what I should do* | Per consumer | Task-conditioned (`why this, now`). value-scout stays report-only. |
| **Apply** the insight | Always per consumer | Bishop has no destination (skill, spec, repo). Sidecar is not a skill-update-runner. |

Centralizing extraction so the VDB is “smarter” is better for a generalized local corpus and **clunky to distribute**: you would be shipping a judge, not an index. Shipping `search` / `get_entry` is the product.

## Adversarial pass (what died)

- Search hit ≠ visit ≠ extracted. “Capture everything” fills the sidecar with noise.
- Appending scout text into `summary` / hooks / N1 embed poisons later unrelated retrieval and Call 1/2 eval.
- `extracted` as a bool erases the useful case: already scouted, zero kept.
- MCP v1 must not receive `STATE_WORKER_URL`. v2 `record_scout`, if built, is a **second bind** through state-worker. SQLite stays single-writer.
- value-scout does not write sibling storage. The consuming agent posts the one artifact (`report.md` / findings table).

## v2 sidecar (if earned)

Append-only, keyed by `source_id`. Two events only: optional visit; completed scout → `none | scouted_empty | scouted_kept` + run locator + date + `why_this_now`. Promote-into-VDB is a later, explicit step for artifact-level claims only.

**Build order:** v1 read-only MCP → a few real reports → schema `record_scout`. Not the other way around.

## Related

- `mcp-agent-tool-notes.md` (§7 sidecar, §8 consumers)
- `product-backlog.yaml` PB-010
- value-scout skill (report-only; not a Bishop writer)
