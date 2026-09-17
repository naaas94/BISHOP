# Bishop as an Agent Tool / MCP — Next-Steps Notes

**Status:** scoping notes, not a plan or spec. Read path: 2026-09-13/14. Sidecar + consumers: 2026-09-16. Write-up: `.dev/decision-logs/ops/mcp-consumer-extraction.md`. No code, no MCP server exists yet in this repo. Tracked as PB-010.

**Goal:** expose Bishop's already-processed corpus (scrape → pre-filter → enrich → index) to other agents as a tool/MCP. **v1 is read-only retrieval.** A later **v2** may accept a schema-gated scout artifact into a consumption sidecar — not into the ingest pipeline, not into the VDB.

---

## 0. Why this is the right shape

The expensive work Bishop does is the pipeline itself. Agents consuming Bishop don't need a UI — they need retrieval:

- **General work:** "what do I already know about X" → search over the indexed corpus.
- **Specific ad hoc work:** "pull the exact entries on this problem" → search + fetch full entry.

This is the same shape the human-facing surface already has. There is no MCP in the repo today, but the human analog exists: `services/query-api` (FastAPI, `mode=ro` SQLite) plus `bishop_cli` (Typer CLI: `search`, `recent`, `batch`, `escalations`) hitting `http://localhost:8080`.

**The design move is: wrap the *read* half of query-api, not the whole HTTP surface.**

---

## 1. What to expose

| Tool | Existing route | Role |
|------|----------------|------|
| `search` | `GET /search` (`services/query-api/app/routers/search.py`) | RRF fusion over BM25 + dense channels. Filters already exist: `domain`, `source`, `tags`, `min_relevance`, `days`, `type`, `reading_status`. |
| `get_entry` | `GET /entries/{source_id}` (`services/query-api/app/routers/entries.py` → `sqlite_reader.read_entry`) | Full row from SQLite opened `mode=ro`. Includes `content_raw`, summary, concepts, tags, challenge_hooks, relevance_score, etc. |
| `recent` | `GET /recent` (`services/query-api/app/routers/recent.py`) | "What landed" without a query — DuckDB `ingested_at` ordering, filterable by `source`/`domain`/`days`. |

`search` returns titles/scores/summaries (`SearchHit` in `app/models.py`); `get_entry` is a deliberate second call for the full body. Keep that split — it's what keeps an agent from dumping full entries into context on every query.

## 2. What NOT to expose

Even though `query-api` has routes for these, they are write-proxies into `state-worker` and belong to the UI/operator surface, not a general agent tool:

- `POST /entries/{source_id}/retry`
- `POST /entries/{source_id}/permanent-fail`
- `PATCH /entries/{source_id}/reading-status`
- `POST /parked/promote`
- `POST /batches`, `PATCH /batches`, `POST /batches/{id}/timeout`

**Read-only for agents must be a separate bind, not "MCP in front of all of query-api."** The MCP process should never receive `STATE_WORKER_URL` / `STATE_WORKER_BASE_URL` — that's the structural guarantee against accidental writes, not just a convention.

Batches (`GET /batches`, `GET /batches/{id}`) and escalations (`GET /escalations`) are read-only but operator-shaped (pipeline health, not knowledge retrieval). Candidate for a separate "Bishop-ops" tool/MCP if ever needed — not bundled into the general-purpose one.

## 3. Constraints specific to agent consumption (vs. human UI)

- **Token budget on `get_entry`.** `content_raw` is the entire scraped body. Default response should be summary + concepts + tags + challenge_hooks, with an explicit `include_content` flag or a hard character cap to opt into the full body. The UI can afford to render everything; an agent session cannot afford to eat it by default.
- **Default hit count / pagination on `search`.** Needs an explicit small default (existing `SearchResponse.total` plus `hits` — cap before wrapping, don't just pass query-api's raw response through).
- **Domain default.** `DEFAULT_SEARCH_DOMAIN` (`bishop_shared/query_config.py`) is `"professional"` today; personal domain profile/routing is still not implemented (per `.dev/architecture/bishop/public-interface-inventory.md` — "Still not public: personal domain profile YAML and routing"). The tool surface should not imply a personal-domain filter exists yet.
- **Ops vs. knowledge separation.** A general research/coding agent should see `search` / `get_entry` / `recent` only. A Bishop-ops agent (if one is ever built) is a different tool with `escalations` / `batches` added — don't merge the two personas into one schema.

## 4. Structural guarantees to hold (matches existing pattern)

- SQLite opened `file:...?mode=ro` — same rule `query-api/app/sqlite_reader.py` already follows (`tests/test_query_api_routes_entry.py::test_read_entry_opens_sqlite_read_only` is the existing falsifier; an MCP-facing equivalent test should exist too).
- Single writer stays `state-worker`. The **v1** MCP process is "another `mode=ro` reader," same rule as `query-api` and CLI/scripts per `.cursor/rules/bishop-sqlite.mdc`. It must not receive `STATE_WORKER_URL`.
- v1: no new columns, no new write paths, no bypassing `processing_state` semantics. v2 write-back (if built) is a **separate bind** that only posts a scout artifact through state-worker. It still must not open SQLite.

## 5. Two possible next steps (undecided — pick one to proceed)

**A. Thin version — build first, refine later**
A stdio MCP server that only calls the three GETs above (`search`, `get_entry`, `recent`) against a running `query-api` instance. No `STATE_WORKER_URL` in its env. Ship fast, iterate on token/pagination limits from real usage.

**B. Design version — lock schemas first**
Before any code: lock the MCP tool schemas — filter parameters, default hit count, content-inclusion policy on `get_entry`, error shape on upstream failure (query-api down, empty stores per G7 cold-start pattern) — as a small spec artifact, then build against that contract.

Neither has been chosen yet. This file exists so that decision (and the exclusions in §2) survive between sessions.

---

## 6. Open questions carried forward

- Where does the MCP server live — new `services/mcp-bishop/` (own container, own port) vs. a script that agents run outside compose against the existing `QUERY_API_HOST_PORT` (8080)?
- Auth/access: today `query-api` is bound to localhost inside the dev compose network; does an agent-facing MCP need its own access boundary, or does "local-first, same machine" cover it?
- Should `recent` exist as a separate tool, or fold into `search` with no query string (it's currently a separate query-api route with its own DuckDB path — `services/query-api/app/stores/duckdb_reader.py` — so folding is a real design decision, not free)?
- Escalations/batches as a second, ops-scoped MCP: worth building at all, or is CLI/UI sufficient for that persona indefinitely?
- v2: one consumption MCP vs two binds (read-only vs `record_scout`)? Structural preference is two binds so v1 stays `STATE_WORKER_URL`-free.
- Scout artifact: store the value-scout `report.md` blob, a JSON subset of the findings table, or both?
- Search filter `scout_status` on v1, or only after the sidecar exists?
- After a few real scouts: do artifact-level findings exist in enough density to earn a Bishop-owned extract channel, or does extraction stay 100% consumer-side?

---

## 7. v2 — consumption sidecar (2026-09-16)

Not in v1. Capture here so the next MCP pass does not invent "the agent writes the index."

The loop that survived an adversarial pass: Bishop is the **triage index** (card + `content_raw` blob). Value comes from visiting `url` and running **value-scout**. The extract skill emits **one** artifact (`report.md` / findings table). A later MCP tool `record_scout` stores that artifact against `source_id`. It does not re-embed, does not patch Call 1/2 fields, and does not move `processing_state` off `INDEXED`.

**Skill vs MCP.** value-scout stays report-only (it does not write sibling storage). The consuming agent (or a thin hop after the report exists) is what calls MCP. Do not teach the skill to open Bishop.

### What to capture (two events, not "everything")

| Event | Trigger | Stored |
|---|---|---|
| visit | `get_entry` and/or URL open | `visited_at` — cheap, optional |
| scout | completed scout artifact posted | `none \| scouted_empty \| scouted_kept` + run locator + date + `why_this_now` + findings |

A search hit is neither. Marking extracted on every hit is how the sidecar fills with noise.

### What not to write

- `summary`, `challenge_hooks`, `value_rationale`, N1 `build_embed_text`, LanceDB vector
- `reading_status` (human). `processing_state` (ingest). `INDEXED` stays terminal.
- Task-conditioned findings (skill-gaps for *this* session) into retrieval. Those stay in the report. Only artifact-level claims would ever earn a later retrieval channel, and that is a promote step, not auto-fold.

### Shape

Append-only sidecar (table or files + index row), keyed by `source_id`. Human routing of findings stays outside Bishop. Search may later filter `unscouted` / `scouted_empty`. Promote-into-VDB is a later, explicit decision after real reports exist to schema against.

**Build order:** v1 read-only MCP first. Schema the artifact after a few real `report.md`s. Then `record_scout`. Not the other way around.

---

## 8. Consumers vs extraction vs action (2026-09-16)

Bishop is the pantry. Consumers are the kitchen. Full write-up: `.dev/decision-logs/ops/mcp-consumer-extraction.md`.

Bishop **does** owe consumers a general “how to understand this index” (MCP tool prose / a short consumer note): a hit is a card, `get_entry` is the scrape blob, the paper/repo is at `url`. That is not a second extractor. Per-consumer docs only if the persona splits (research vs ops).

**Value extraction is per consumer** for anything task-shaped. **Action is always per consumer.** Bishop never applies a finding (no destination skill/spec/repo). The “other way around” (Bishop extracts once into the VDB) is better for a shared corpus and worse to distribute — you would be shipping a judge. Only artifact-level claims (“this README is a landing”) would ever belong in Bishop, and only if a lightweight experiment shows they recur.

**Experiment before v2:** one real task, a few hits, scout by hand. Count artifact vs task findings. Do not scale `record_scout` or a Bishop-owned extract on theory.
