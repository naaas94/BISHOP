# Ingest content risk — seed investigation

**Date:** 2026-09-15  
**Scope:** ops / security — static map of untrusted public content through scrape → LLM gates → index → UI  
**Status:** Documented, deferred. Not an incident. No code change.

Canvas (operator view): [Ingest content risk](C:/Users/Ale/.cursor/projects/c-Users-Ale-Documents-Repos-BISHOP/canvases/ingest-content-risk.canvas.tsx) — not in the architecture folder schema.

Tracked as OPEN-023 / PB-009.

## Verdict

The realistic exposure is **integrity of the knowledge base**, not RCE. Anyone who can publish into a scraped window (ArXiv, GitHub, HuggingFace, Semantic Scholar, OpenReview, LessWrong) can put instruction-like text in a title, abstract, or README. That text reaches Claude as the **user** turn, then the Call-1 summary hops into Call 2, then title + summary + hooks are embedded. A poisoned item can change pass/park, burn batch spend, and pollute retrieval.

There is no tool-use, no subprocess on ingest bytes, and no generative RAG chat that would re-send retrieved docs to another model. A poisoned item does not get a shell.

Not urgent on a local-first single-operator box. Do not treat this log as a build list until a later packet owns it.

## What was reviewed

Static evidence only (2026-09-15). Four independent maps: ingest adapters, LLM prompt construction, UI render, persist/query. No exploit attempts, no live adversarial scrape.

## Findings (IDs)

| ID | Severity | Finding |
|----|----------|---------|
| I-1 | High (integrity) | Gate 1: `title` + abstract concatenated into the user turn with no delimiters (`pre-filter-worker` `PreFilterBatchEntry.user_message`). |
| I-2 | High | Call 1: title + truncated `content_raw` as `Title:` / `Content:` user blob. GitHub/HF README stored raw. |
| I-3 | High | Call 1 → Call 2 hop: Call 2 user message is title + **Call-1 summary**, not the raw body. |
| I-4 | High | Index / embedding poisoning: vector-writer encodes title + summary + `challenge_hooks`. |
| I-5 | Medium | `ContentPostRequest.content_raw` and SQLite `sa.Text()` have no `max_length`. Truncation is Call-1 only (`ENRICHMENT_TRUNCATION_MAX_TOKENS = 4000`). |
| I-6 | Medium | UI `entry_detail.html` / `parked.html` render `entry.url` as `href` with no http(s) allowlist. Click XSS only if an upstream API returns `javascript:` / `data:`. |
| I-7 | Medium | `query-api` and `ui` publish host ports with no auth. LAN client can read the corpus and promote/retry. Expected for local-first; open only if this host is not a single-operator box. |
| I-8 | Low | `source_id` raw segment interpolated into **fixed-host** content URLs (no charset allowlist). Not open SSRF: adapters never `GET(entry.url)`. |
| I-9 | Low | ArXiv Atom uses stdlib `xml.etree.ElementTree` (no defusedxml). CPython ET does not resolve external entities; residual risk is quadratic blow-up, not classic XXE. |
| I-10 | Low | Offline `eval/github_repo_gate_v0/review.html` uses `innerHTML` with a partial `esc()`. Not served by `services/ui`. |

LessWrong is the noisiest body path: regex tag-strip keeps inner text of `<script>` nodes. ArXiv `HTMLParser` drops `script`/`style` data.

## Already solid (do not “fix”)

- SQLite and DuckDB value paths use bound parameters.
- No `subprocess` / `eval` / `pickle` of ingest bytes. Config YAML is `yaml.safe_load`.
- Adapters never fetch the stored `url`. Content GETs are templates on github.com / huggingface.co / arxiv.org / etc.
- Jinja2 autoescape on; `content_raw` in `<pre>`; no `|safe`, no markdown, no app JS `innerHTML`.
- Untrusted text is **outside** the prompt-cache prefix (`cache_control` on trusted system blocks only). Document is `role=user`.
- Batch-poller type-checks JSON before write; no `eval` of model output.
- `state-worker` is compose-internal (no host `ports:`).

## Open forks (not decided)

These are the architecture `open-questions.md` entries. A later packet picks; this log does not.

1. **Injection resistance:** frozen adversarial eval through Gate 1 / Call 1 / Call 2 first, vs prompt delimiters / fences first, vs both.
2. **Cheap ingest hardening:** http(s) allowlist on `manifest.url` at ingest **and** UI href; wire `max_length` (and/or HTTP response size cap) on `content_raw`. Independent of LLM work.
3. **LAN threat:** bind UI/query-api to localhost, add a shared secret, or explicitly accept unauthenticated local-first.

## Not minted

`failure-taxonomy.md` cause classes stay empty. The seed map is concrete anticipation, but taxonomy IDs still need owner names per that file’s addition protocol. Do not invent `L0.*` / `L2.*` ids here.

## Suggested later probes (when convenient)

1. Frozen adversarial eval slice (highest leverage for I-1–I-4) — measure whether current rubrics already resist obvious injection **before** changing prompts.
2. http(s) allowlist on stored URLs (I-6).
3. Wire / response size cap on `content_raw` (I-5).
4. `source_id` charset allowlist (I-8).
5. LAN bind/auth only if I-7 is in scope for this host.

## Registries

- `.dev/still_open.md` OPEN-023
- `product-backlog.yaml` PB-009
- `.dev/architecture/bishop/open-questions.md`
- `.dev/architecture/bishop/known-coupling-surfaces.md`
- `.dev/architecture/bishop/external-input-sources.md`
- `.dev/architecture/bishop/integration-seams.md`
