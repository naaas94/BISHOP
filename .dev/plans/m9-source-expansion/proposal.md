# M9 — Source Expansion

**Proposal name:** `m9-source-expansion`  
**Version:** 0.1  
**Status:** Proposal — scoping; not a dispatchable plan  
**Prior milestone:** M8 — Hardening and Scale (`.dev/plans/m8-hardening-scale/`)  
**Normative spec:** `bishop_spec_0_6.md` v1.5.0 (tracked)  
**Referenced from:** `config/sources/arxiv.yaml`

This document is a scoping proposal. It does not decompose work into subtasks, packets, or estimates. A later orchestrator plan would consume the decisions this proposal leaves open.

---

## 0. Context

The pipeline from discovery through index currently has one live adapter: `ArxivAdapter`. `ADAPTER_REGISTRY` in `services/scraper/app/adapters/registry.py` is still `[ArxivAdapter]`. `SourceEnum` already reserves the remaining spec sources (`semantic_scholar`, `huggingface`, `paperswithcode`, `github`, `openreview`, `lesswrong`), and the M8 charter names those as the remaining adapters. Those sources are paper-, model-, or repo-shaped. They do not change the density of applied-systems or dev-skills content in the corpus.

The category gate that just shipped (`config/sources/arxiv.yaml`, `bishop_shared/source_config.py`) is a zero-cost pre-LLM filter on ArXiv **primary** category. It can drop `cs.CV` / `cs.RO` / `cs.SD` / `eess.*`. It cannot invent content ArXiv does not publish. The yaml already points at this path for the rationale that primary-category matching is ArXiv-local.

`relevance_log.md` and the 129-item hand-labeled set `eval/prefilter_v0/` are the evidence that motivates a different source class. The current relevance profile is `config/profiles/professional_v1.1.1.yaml`.

**Binding artifacts for this proposal (read, not amended):**

| Artifact | Role |
|----------|------|
| `eval/prefilter_v0/labels.json` | 129 human labels; reason counts cited in §2 |
| `eval/prefilter_v0/contract.json` | Closed reason vocab (`applied_systems`, `dev_skills`, `adjacent_interesting`) |
| `relevance_log.md` | Operator statement of what they want to read |
| `services/scraper/app/adapters/base.py` | `SourceAdapter` contract a new source must satisfy |
| `services/scraper/app/adapters/arxiv.py` | Existing Atom adapter; reusable vs ArXiv-specific split in §4 |
| `services/scraper/app/models.py` | `ManifestIngestEntry` shape |
| `config/profiles/professional_v1.1.1.yaml` | Current gate-1 vocabulary |
| `config/sources/arxiv.yaml` | Category gate; ArXiv-local by construction |
| `bishop_shared/source_config.py` | Gate semantics (fail open on missing category) |

**What this proposal is not:** an M8 continuation that lands HuggingFace / GitHub / OpenReview. Those remain a separate charter slice. Sequencing against them is an open question (§6 Q1).

---

## 1. Task statement

**(a) Active milestone ID:** M9 — Source Expansion

**(b) Thesis:** the keep-grade gap is a **corpus problem, not a profile problem.** ArXiv structurally cannot supply applied-systems or dev-skills content at usable density. Profile and prompt iteration on an ArXiv-only stream cannot raise that density.

**(c) What a later plan would do (not decided here):** add one non-ArXiv content source of a class that can actually emit applied systems, shipping narrative, and reusable techniques; produce `ManifestIngestEntry` rows through the existing `SourceAdapter` interface; and decide what of the downstream paper-shaped stack must change before those rows are allowed to reach index.

**Non-goals of this proposal:**

- A first-source pick, feed URL, or crawl schedule.
- A full adapter implementation, registry change, or `SourceEnum` amendment.
- A profile rewrite, enrichment-prompt rewrite, or new eval freeze.
- Landing the remaining M8 spec adapters.
- Subtask packets, DAG, estimates, or executor dispatch.

---

## 2. Motivation

The professional profile already asks for practitioner content. `professional_v1.1.1.yaml` context is written from "the perspective of a practitioner who ships production-grade AI" and the decisive principle is "Judge the contribution, not the topic." v1.1.0 and v1.1.1 were calibrated against the same ArXiv eval set after false-positive / false-negative analysis. That work can change *which papers pass*. It cannot change *what the feed contains*.

`relevance_log.md` states the operator want in their own words: "more applied stuff, systems, what people are doing and how they're doing it, what systems and businesses, and features" plus "skills (dev flow enhancement or techniques)." The same note already diagnoses the source: "the nature of arxiv is too paper coded and experimental and not applied based."

The 129-item hand-labeled set (`eval/prefilter_v0/labels.json`, `labeled_count: 129`, reason tags in `labels[<id>].reasons`, vocab in `eval/prefilter_v0/contract.json`) measures that diagnosis:

| Reason tag | Contract meaning | Fired on |
|------------|------------------|----------|
| `applied_systems` | "What people or businesses are actually building — products, features, pipelines, ops." | **2 of 129** |
| `dev_skills` | "Dev-flow techniques, skills, agent/editor workflows I would reuse." | **0 of 129** |
| `adjacent_interesting` | "Clever but not my lane; maybe a summary, not a keep." | **47 of 129**, of which **41 were `prefilter_should: reject`** |

Two applied-systems hits and zero dev-skills hits is not a threshold miss. The closed vocab was available to the labeler on every item. The content was not there.

`adjacent_interesting` is the complementary signal: the corpus *does* produce clever, paper-coded work that is adjacent to the profile. Most of it is correctly rejected. Tuning the profile to pass more of those 41 rejects would raise adjacent density, not applied-systems density. That is the wrong direction relative to `relevance_log.md`.

The category gate does not change this. Over the same 129 items it is measured to remove 8 rejects at the cost of 1 pass (`cs.CV` / `cs.RO` / `cs.SD`; `eess.*` unvalidated). That is a cheap reject trim on the existing paper stream. It does not create the two missing reason classes.

**Conclusion:** further profile or prompt work on ArXiv is the wrong lever. The next milestone is a source that can emit the missing classes.

---

## 3. Candidate source classes

Three classes are in scope for consideration. No class is selected. Specific sites and feed URLs are **unverified** unless noted as a known public pattern; do not treat the examples as an allowlist.

What matters for reuse: the live adapter is Atom-based (`https://export.arxiv.org/api/query`). Generic Atom/RSS field mapping (id, title, summary, link, published) is partly extractable from `arxiv.py`. A source that is not feed-addressable needs a different `fetch_manifest` implementation and does not inherit that parsing.

### 3.1 Engineering blogs

**What ArXiv cannot supply.** Shipping write-ups: how a team built a retrieval stack, an agent loop, an eval harness, a feature. Named systems, constraints, and tradeoffs written as narrative, not as a contribution claim. This is the `applied_systems` class, and often the architecture-tradeoff class, in the form the operator asked for.

**Feed addressability.** Many public engineering blogs publish RSS or Atom. That is a common pattern, not a verified inventory. Per-blog feed URL, auth, pagination, and full-text-in-feed vs link-only are outstanding. A link-only feed still needs `fetch_content` against HTML.

**Fit notes.** Closest to the existing Atom path *if* a chosen blog exposes a usable feed. The `abstract` field would be an excerpt or lede, not a paper abstract. `entry_type` already includes `article` in the enrichment Call 1 schema (`bishop_shared/enrichment_prompts.py`). Truncation already falls through to beginning/end for unknown sources (`bishop_shared/content_truncation.py`).

### 3.2 Changelogs and release notes

**What ArXiv cannot supply.** What a product or library actually shipped: features, breaking changes, ops notes. This is closer to "what people are doing and how they're doing it" than a methods paper. It can also carry `dev_skills` when the notes describe a workflow change (new CLI, eval harness, batch API) rather than a version bump.

**Feed addressability.** Mixed. Some hosts expose Atom/RSS for releases — GitHub Releases Atom (`/{owner}/{repo}/releases.atom`) is a known public pattern, not a product pick. Many vendor changelog pages are HTML-only, paginated, or JS-rendered. Per-product verification is outstanding. GitHub-the-source is already a reserved `SourceEnum` value aimed at repos (M8 charter); using it for changelog text is a different adapter job and should not be assumed to be the same implementation.

**Fit notes.** Items are often short, dated, and ID-stable *when* the host has a release ID. Items are often undated or rewritten *when* the host is a living changelog page. Dedupe and `published_at` are the load-bearing problems, not Atom syntax.

### 3.3 Conference talks

**What ArXiv cannot supply.** Applied talks: architecture reviews, production postmortems, technique walkthroughs. Closer to `dev_skills` and `applied_systems` than a proceedings paper. Academic conference *papers* (OpenReview, etc.) are the M8 class and do not belong here.

**Feed addressability.** Weakest of the three. Some conferences publish a blog or RSS of recaps. Talk catalogs, slide decks, and transcripts are commonly HTML, YouTube, or attendee-only. Transcript availability is unverified per venue. A video-only item has no `fetch_content` story under the current `str` return type without a speech-to-text dependency that does not exist in the scraper image.

**Fit notes.** Treat as a class that likely needs an HTML or API manifest, not an Atom reuse. Do not assume a transcript.

| Class | Missing reason tags it could feed | RSS/Atom-addressable? |
|-------|-----------------------------------|------------------------|
| Engineering blogs | `applied_systems`, sometimes `dev_skills` | Often, per-blog verification outstanding |
| Changelogs / release notes | `applied_systems`, `dev_skills` | Mixed; GitHub Releases Atom is a known pattern, not a pick |
| Conference talks | `applied_systems`, `dev_skills` | Generally no; verification outstanding |

---

## 4. Adapter interface fit

A new source is not a new pipeline. Discovery already iterates every class in `ADAPTER_REGISTRY` (`services/scraper/app/loop.py`). Content-scraper already resolves `SourceEnum` → adapter and calls `fetch_content`. The contract a new implementation must satisfy is `SourceAdapter` plus the ingest DTO.

### 4.1 What `SourceAdapter` requires

From `services/scraper/app/adapters/base.py`:

| Surface | Required | Notes |
|---------|----------|-------|
| `source: SourceEnum` | yes | Class-level. New literal means amending `bishop_shared/enums.py` **and** `services/state-worker/app/enums.py` (lockstep, spec §20.1). No blog / changelog / talk value exists today. |
| `domain: DomainEnum` | yes | Live ArXiv adapter hardcodes `PROFESSIONAL`. |
| `rate_limit: RateLimit` | yes | `SOURCE_RATE_LIMITS` in `services/scraper/app/rate_limit.py` currently has **only** `arxiv`. A new key is required or `ADAPTER_REGISTRY` construction fails the same way a missing enum would. |
| `fetch_manifest(since: datetime \| None) -> list[ManifestIngestEntry]` | yes (abstract) | Lightweight: IDs, titles, abstracts only. `since` is `ScraperState.last_successful_run_at` from state-worker, or `None` on first run. |
| `fetch_content(entry: ManifestIngestEntry) -> str` | yes at M4+ | Default ABC still raises `NotImplementedError("M4")`. Content-scraper will call the override. |
| `make_source_id(raw_id: str) -> str` | provided | `{source.value}:{raw_id}`. Reusable as-is **if** `raw_id` is short and stable. See §5. |

`ManifestIngestEntry` (`services/scraper/app/models.py`):

| Field | Type | Constraint for a new adapter |
|-------|------|------------------------------|
| `source_id` | `str` | Canonical `{source}:{raw_id}`. Ingest is idempotent on this key (`ingest_manifest` skips existing rows). Also capped at **48 UTF-8 bytes** by `bishop_shared/batch_custom_id.py` for Anthropic `custom_id`. |
| `source` | `SourceEnum` | Must be the adapter's `source`. |
| `url` | `str` | Required. For a blog this is usually the permalink. |
| `title` | `str` | Required. Atom parser already drops entries without title. |
| `abstract` | `str \| None` | Optional on the DTO. Pre-filter user message is `title + "\n" + (abstract or "")` (`PreFilterBatchEntry.user_message`). Empty abstract means title-only gate 1. |
| `published_at` | `datetime \| None` | Optional. Incremental `since` is still passed; the adapter decides what it means. |
| `domain` | `DomainEnum` | Required. |

The scrape loop, `failure_envelope`, state-worker ingest, and content-scraper worker do not need to know the source class beyond `SourceEnum` and those fields. That is the reuse. Everything paper-shaped *after* ingest is the breakage in §5.

### 4.2 Reusable machinery vs ArXiv-specific logic

Honest split of `services/scraper/app/adapters/arxiv.py` and its helpers. "Reusable" means the code is not conceptually ArXiv-bound; it is not already extracted, and a later plan should not assume a clean shared module exists today.

**Reusable (or extractable):**

| Piece | Where | Why it generalizes |
|-------|-------|--------------------|
| Token-bucket rate limiter | `TokenBucketRateLimiter` + `RateLimit` | Per-source numeric policy. New source needs its own `SOURCE_RATE_LIMITS` row; the limiter class does not. |
| Generic Atom field mapping | `ATOM_NS` handling in `parse_atom_feed_with_categories`: `id`, `title`, `summary`, `link[rel=alternate]`, `published` | Standard Atom. Usable for a blog or releases feed **after** ArXiv-schema and version-suffix logic are peeled off. |
| In-feed dedupe | `seen: set[str]` on `source_id` | Any feed. State-worker ingest is a second, persistent dedupe on the same key. |
| `make_source_id` | `SourceAdapter` | Format only. Stability of `raw_id` is the source's problem. |
| HTML → text | `_HTMLTextExtractor`, `strip_html_to_text` | Usable for blog/changelog HTML `fetch_content`. No new deps. |
| Title + blurb fallback | `compose_fallback_content` | Same shape: `{title}\n\n{abstract or ""}`. Meaning of `abstract` changes; the helper does not. |
| `failure_envelope` + scrape cycle | `loop.py`, `failure_envelope.py` | Already source-agnostic. |
| Category-config *loader* | `load_source_config(source)` | File-per-source, fail-open if absent. The *matching language* (ArXiv primary category, `cs.*` wildcards) is not reusable. |

**ArXiv-specific (do not reuse as-is):**

| Piece | Where | Why it does not generalize |
|-------|-------|----------------------------|
| Export API query | `ARXIV_EXPORT_API_URL`, `build_search_query`, `ARXIV_CATEGORIES`, `submittedDate` range | ArXiv search dialect. A blog feed is a URL, not a `cat:` union. |
| `arxiv:` id scheme | `_extract_raw_id`, `_ARXIV_ID_VERSION_RE`, `parse_raw_id_from_source_id` | Versioned abs IDs (`2301.00001v2` → `2301.00001`). Blog slugs and release tags do not have this shape. |
| Primary-category gate | `ARXIV_SCHEMA_NS`, `extract_primary_category`, `apply_category_gate` | Gate-local metadata that never reaches the ingest DTO. Blogs and changelogs have no ArXiv primary category. `allows(None)` already fail-opens. |
| HTML-by-id fetch | `ARXIV_HTML_BASE_URL/{raw_id}` | `https://arxiv.org/html/{id}`. A new source fetches `entry.url` or a host-specific content URL. |
| First-run window | `ARXIV_BACKFILL_WINDOW_DAYS` / `resolve_effective_since` | Tied to `submittedDate` query construction. A feed's `since` semantics (lookback vs cursor vs "whole feed") are source-local. |

`parse_atom_feed` is the gray zone: the function signature (`xml, *, adapter`) is generic, but the body calls `_extract_raw_id` (version strip) and `extract_primary_category` (ArXiv schema). A later plan that wants Atom reuse should split "standard Atom → DTO" from those two helpers, not import `parse_atom_feed` unchanged.

Registry today is a single-element list plus an import-time stub. Adding a class is a one-line registry edit **after** the enum and rate-limit keys exist. Content-scraper vendors `scraper_app/` from this tree; a new adapter file has to be on that COPY list or the image runs without it.

---

## 5. What breaks for non-paper content

The adapter seam accepts a blog-shaped row. Several downstream stages will mis-handle it even if ingest succeeds. This list is the known surface, not a complete audit.

### 5.1 Gate 1 assumes a paper abstract

Pre-filter user text is `title + "\n" + (abstract or "")`. The frozen eval protocol is the same (`eval/prefilter_v0/contract.json` replay: `item.title + item.abstract`). A blog excerpt, a changelog bullet list, or a talk subtitle is not an abstract. Title-only rows are legal on the wire and starved at the model. Whether to synthesize a lede, pass the first N characters of the body at gate 1, or skip gate 1 for some source classes is unsolved.

### 5.2 The profile is written in research-contribution vocabulary

`professional_v1.1.1.yaml` principles and exclusions judge **papers**:

- "Judge the contribution, not the topic: a paper about agents whose contribution is a training recipe is a training paper"
- Exclusions keyed on "the contribution improves the base model itself", "object of study is the model", calibration examples that are paper titles

That test is meaningless for a blog post or a release note. There is no "contribution" in the academic sense. Applied to a shipping write-up, the model may reject on "tutorial" / "market" exclusions or pass on topic keywords. Either way the rationale contract ("name the anchor or the exclusion") will cite language that does not describe the artifact. A later plan must decide whether this is a profile amendment, a second profile, or a source-specific prompt overlay. This proposal does not pick.

### 5.3 Enrichment Call 1/2 and `enrichment_score` assume a paper-shaped body

- Call 1 (`build_call1_system_prompt`) is closer to generic ("technical content analyst") and already allows `entry_type: article`. That part may hold.
- Truncation for paper sources (`arxiv`, `openreview`, `semantic_scholar`) splits on an `Abstract` heading or the first paragraph (`_paper_strategy`). A new source falls through to `_beginning_end_strategy` unless someone adds a branch. Beginning/end is plausible for a blog and bad for a changelog (the useful part is often the latest section, not the page chrome).
- Call 2 scores relevance against the same paper-shaped profile and writes `relevance_score` / `enrichment_score`. `config/index_policy.yaml` bands were swept on the **129 ArXiv labels** (median 0.65 wanted vs 0.35 not; `keep_min: 0.40`). Those numbers do not transfer.

### 5.4 `source_id` schemes and mutating URLs

Ingest dedupe is exact `source_id` match. ArXiv IDs are stable. Blog and changelog URLs are not:

- trailing slash, `www`, scheme, query params, CMS slug edits, title changes
- the same article at `/blog/foo` and `/blog/foo/` becomes two rows
- a rewritten slug looks like a new item; the old row stays

`make_source_id` does not canonicalize URLs. A raw permalink also blows the **48-byte** `source_id` cap used for batch `custom_id` (`arxiv:2606.11375` fits; `blog:https://…/long-slug` often will not). Any URL-as-id scheme needs a short stable raw_id (hash, host-local id) and a documented canonicalization. Neither exists.

### 5.5 Missing or unstable publication dates

`published_at` is already optional. Incremental discovery still passes `since=last_successful_run_at`. ArXiv encodes that as a `submittedDate` range. A feed without dates, or with "last updated" instead of "published", cannot use the same rule. Living changelog pages often have no per-item date. First-run backfill window (`ARXIV_BACKFILL_WINDOW_DAYS`) is ArXiv-query-specific. A new adapter must define `since` or accept "re-read the whole feed and rely on ingest skip" — which fails if IDs mutate (§5.4).

### 5.6 Paywalls and `robots.txt`

ArXiv export + HTML is an explicit public API plus a public HTML endpoint, rate-limited in-process. Engineering blogs, vendor changelogs, and conference sites have their own robots rules, bot walls, and paywalls. The scraper has no robots parser today. Fetching behind a login or ignoring `Disallow` is out of scope until a source is picked and its terms are read. Some "feeds" are link-only and the linked HTML is gated; `fetch_manifest` would succeed and `fetch_content` would return chrome or a 403, which the failure envelope will treat as a scrape failure, not as "this source class is wrong."

### 5.7 Frozen eval sets do not transfer

`eval/prefilter_v0/` and `eval/prefilter_v1/` items are ArXiv IDs. Replay scripts refetch ArXiv abstracts (`scripts/build_eval_v1.py`). Profile hashes, gate-2 bands, and the category-gate measurements are all on that corpus. A new source ships with **zero** labeled items and **zero** calibrated thresholds. Existing replay numbers cannot be cited as quality evidence for the new adapter. A new eval freeze is a prerequisite for claiming the milestone improved applied-systems density — otherwise the only observable is "more rows entered `DISCOVERED`."

### 5.8 Adjacent couplings (not blockers, but real)

- `SourceEnum` / state-worker enum lockstep and compose/contract tests that enumerate sources.
- Content-scraper Docker vendor COPY of `scraper_app/`.
- `source_id` in UI routes (`/entries/{source_id}`) and query-api — punctuation in slugs.
- Tag taxonomy and OOV log: article vocabulary may not be in `TAG_TAXONOMY_ORDERED`.
- Category-gate YAML per source: a new file is optional; matching language is ArXiv-shaped and should not be copied blindly.

---

## 6. Open questions

These need a person before implementation. No answers are implied.

**Q1 — Sequencing vs M8 remaining adapters.** Does M9 land *instead of*, *before*, or *after* the spec sources already reserved on `SourceEnum` (HuggingFace, PapersWithCode, Semantic Scholar, GitHub, OpenReview, LessWrong)? Those expand paper/repo volume. They do not address the thesis. The charter currently stops at M8.

**Q2 — First source (class and concrete origin).** Which class in §3, and which one feed or site? A generic "RSS adapter" with a config list is a different design from one adapter class per host. Feed URLs, robots, and full-text-in-feed are unverified for every unnamed candidate.

**Q3 — `SourceEnum` and spec §20.1.** New literal (e.g. a blog host, a generic `rss`, a `changelog`)? Reuse of `github` / `lesswrong` for a job they were not specified to do? Spec amendment vs local enum extension? Dual-enum lockstep is mandatory either way.

**Q4 — What stands in for `abstract` at gate 1.** Excerpt from the feed, first N characters of HTML, title-only, or a different pre-filter prompt for non-paper sources? Title-only is already legal and likely too thin.

**Q5 — Profile vocabulary for non-papers.** Amend `professional_v1.1.1` (or a new version) with article-shaped anchors/exclusions? A second profile? Source-specific overlay that does not change the paper profile? Shipping the current profile against blogs will judge "contribution" that is not there.

**Q6 — `source_id` canonicalization and the 48-byte batch cap.** Hash of canonical URL? Host-provided id? How to treat slash, scheme, query, and slug edits? What happens when a permalink changes after ingest?

**Q7 — Incremental cursor without a stable date.** Whole-feed reread + ingest skip? Per-source watermark other than `published_at`? What is first-run lookback when `submittedDate` does not exist?

**Q8 — Eval before or after the adapter.** New labeled set on the new source as an entry gate, or ship and label from live traffic? Existing ArXiv evals cannot certify applied-systems density. Without a new set, success is not measurable.

**Q9 — Fetch policy.** Which hosts are acceptable under `robots.txt` and terms? Is paywalled or login-gated content a hard skip? Is video-without-transcript a hard skip for talks?

**Q10 — Category gate generalization.** Does `config/sources/<source>.yaml` grow a non-category language (tags, path prefixes, feed names), or stay ArXiv-only and absent for the new source (fail-open, which is the current missing-file behavior)?

---

## 7. What this proposal does not decide

- The first source, its schedule, or its rate limit.
- Whether Atom parsing is extracted into a shared helper in this milestone or copied once.
- Profile version, enrichment prompt edits, or index-policy bands for non-papers.
- Charter text, a context-map, or executor packets.
- Any change to the live ArXiv path, including the category gate `enforce` flag (still `false`).

The implementation plan, when written, should freeze Q1–Q3 at minimum. Q4–Q8 are the ones that determine whether new rows improve the corpus or just add adjacent noise.

---

*Proposal v0.1 — 2026-09-10 — scoping only; not charter-governed dispatch*
