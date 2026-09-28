# Jev / TypeSafe — request/response contract (raw notes)

Scouted 2026-09-27. Phase 1 intake only; no classification.

---

## Source map

| Label | URL | Resolved? |
| --- | --- | --- |
| first-party | https://typesafe.ai/blog/introducing-system-one-models-and-jev | yes |
| first-party | https://docs.typesafe.ai (index) | yes |
| first-party | https://docs.typesafe.ai/llms.txt | yes |
| first-party | https://docs.typesafe.ai/models.md (also `/models` redirect) | yes |
| first-party | https://docs.typesafe.ai/api.md | yes |
| first-party | https://docs.typesafe.ai/introduction/quickstart.md | yes |
| first-party | https://docs.typesafe.ai/introduction.md | yes |
| first-party | https://docs.typesafe.ai/primitives.md | yes |
| first-party | https://docs.typesafe.ai/confidence.md | yes |
| first-party | https://docs.typesafe.ai/model-jaggedness/jev-1.13.md | yes |
| first-party | https://docs.typesafe.ai/sdk/python/api/constants.md | yes |
| first-party | https://docs.typesafe.ai/quickstart | no (404) |
| **secondary** | https://systemonemodels.org/guides/jev-explained/ | yes |
| **secondary** | https://systemonemodels.org/glossary/jev/ | yes |
| unofficial-mirror | https://jevwiki.ai/wiki/reference/http-api.md | yes |
| unofficial-mirror | https://www.jevtypesafeai.com/how-to-use | yes |
| unofficial-mirror | https://jevtypesafeai.com/jev/models | yes |

---

## Pricing (keep domains separate)

### first-party (`typesafe.ai` blog, 2026-09-15)

- Input tokens: **$0.042 / MTok** (also stated as **$42 per billion tokens**).
- Output tokens: **FREE** (“too cheap to meter”).
- Comparison table vs LLMs: input $0.20–$10/MTok; output ~5× input for LLMs.

### first-party (`docs.typesafe.ai/models.md`)

- Jev 1.13 (`jev-1.13.0`): **$42 / Btok** and **$0.042 / Mtok** (same pair).
- Charged per input token; output tokens free.

### unofficial-mirror (`jevtypesafeai.com/jev/models`)

- States: “Pass the same input tokens at **$0.42/M** (output free, about $0.001 per decision) whichever version you pick.”
- **Do not merge** with first-party $0.042/MTok — this is **10×** the first-party figure and appears only on this unofficial-mirror domain.

### Reconcile $0.042/MTok vs $0.42/MTok

| Figure | Domain | Notes |
| --- | --- | --- |
| $0.042/MTok (+ $42/Btok) | first-party (`typesafe.ai` blog, `docs.typesafe.ai`) | Consistent across blog + models page |
| $0.42/M | unofficial-mirror (`jevtypesafeai.com`) only | Not cited on typesafe.ai or docs.typesafe.ai in this pass |

### unofficial-mirror (`www.jevtypesafeai.com/how-to-use`)

- Documents official `POST https://api.typesafe.ai/v1/systemone` with Bearer auth; no alternate $/MTok on that page.
- Also documents a **separate** hosted path: `POST https://jevtypesafeai.com/api/v1/decide` with `JEV_API_KEY` / `jv_live_` keys, prepaid balance — **not** the first-party contract endpoint.

---

## Endpoints (caller dependency)

### first-party HTTP

| Method | URL | Purpose |
| --- | --- | --- |
| `POST` | `https://api.typesafe.ai/v1/systemone` | Evaluate `state` + `questions` → `answers` |
| `GET` | `https://api.typesafe.ai/v1/models` | List model names/aliases the account may send |

SDK default base: `https://api.typesafe.ai` (`DEFAULT_BASE_URL` in Python SDK constants).

### unofficial-mirror note

- `jevwiki.ai` HTTP API page mirrors first-party `POST /v1/systemone` and `GET /v1/models` shapes; labels itself as community wiki referencing OpenAPI/raw docs — treat numbers there as unofficial-mirror unless traced to first-party.

---

## Authentication (first-party)

- Header: `Authorization: Bearer <API_KEY>` (401 if missing/invalid).
- `Content-Type: application/json` required on POST.
- Env var: `TYPESAFE_API_KEY` (Python/JS SDKs).
- Optional SDK env: `TYPESAFE_BASE_URL`, `TYPESAFE_DEFAULT_MODEL`, `TYPESAFE_LOG_LEVEL`.
- Quickstart: API key from dashboard / Playground login (`docs.typesafe.ai/introduction/quickstart.md`).
- unofficial-mirror jevwiki: key URL `https://console.typesafe.ai/keys` (wiki note; not re-verified against live console in this pass).

---

## Request body (`POST /v1/systemone`)

Top-level fields (all required in API reference examples):

| Field | Type | Role |
| --- | --- | --- |
| `state` | string \| object \| array | Content all questions evaluate against |
| `model` | string | e.g. `jev-latest`, `jev-1.13.0` |
| `questions` | map<string, Question> | Named questions; answer keys match question keys |

Question map keys are **not** sent to the model for inference (API reference).

### `state` (first-party)

- Plain string for text, or structured object/array (chat logs, records, app state).
- Text only for Jev 1.13 — no image/audio/video; pre-process non-text to text/structured fields (`models.md`, jaggedness).
- Limits: **64k tokens** total per request (`state` + all questions); **32k** for `state` + longest single question.

---

## Question types (task shape)

Three primitives (`docs.typesafe.ai/primitives.md`, `api.md`):

| `type` | Goal | Question `criteria` | Answer fields |
| --- | --- | --- | --- |
| `choice` | Pick one option | Map option → description (null allowed); **max 255 options** | `choice`, `probabilities`, `confidence` |
| `score` | Rate on ordered rubric | Array of level descriptions; **≥2 levels, up to 10** | `score`, `legend`, `probabilities`, `confidence` |
| `noul` | Yes/no statement | Optional `{ true, false }` rubric strings | `noul` (0–1); **no `confidence`** |

Shared: `type`, `instructions` (string \| object \| array).

Structured `instructions`: object with arbitrary field names + `question` referencing fields via backticks (API reference).

Blog framing: “unstructured state in, typed probabilistic decisions out”; parallel evaluation of all questions in one request; no string generation.

### secondary quotes (`systemonemodels.org`)

> “Jev is a decision model. It reads text you supply, answers typed questions about it, and gives you the answer with a probability attached instead of a written reply.” — jev-explained

> “A request sends one `state`, the text to evaluate, plus a set of named questions, and comes back with a typed answer under each name. All the questions in a call run against the same state, so asking four things about one ticket costs one round trip to `POST https://api.typesafe.ai/v1/systemone`.” — glossary/jev/

Secondary also notes SDK accessor mismatch in TypeSafe’s own pages: quickstart `response.answers[...]` vs Python SDK page `response.choices[...]` (caller should verify installed SDK version).

---

## Response body

| Field | Content |
| --- | --- |
| `model` | Versioned ID that actually answered (may differ from alias in request) |
| `answers` | Map keyed like `questions`; each answer `type` matches question |
| `usage` | `{ input_tokens, output_tokens }` — output billed at $0 but counted |

### Answer shapes (first-party)

**Noul:** `{ type: "noul", noul: number }` — 0=no, 1=yes; near 0.5 = uncertain.

**Choice:** `{ type: "choice", choice: string, probabilities: {option: float}, confidence: number }` — probabilities sum ~1; `choice` = highest-probability option.

**Score:** `{ type: "score", score: number, legend: {index: description}, probabilities: {level: float}, confidence: number }` — score can fall between discrete levels (probability-weighted).

### Confidence vs probability (first-party `confidence.md`)

- Choice/Score always include full `probabilities` distribution.
- `confidence` is a **derived** 0–1 scalar from that distribution (Noul has no confidence field).
- Docs: flatter distribution → lower confidence; callers may use own stats on `probabilities` instead of `confidence`.

---

## Models & versioning

### Current model (first-party `models.md`)

- Version ID: **`jev-1.13.0`** (table row “Jev 1.13”).

### Aliases

| Alias | Points to | Semantics |
| --- | --- | --- |
| `jev-latest` | `jev-1.13.0` | Most recent **stable official** release; SDK default |
| `jev-preview` | `jev-1.13.0` | Most recent release including previews; **currently same as jev-latest** — “no preview build available right now” |

Alias can move on new releases; response `model` field logs resolved version. Pin `jev-1.13.0` if thresholds tuned to a specific release.

`GET /v1/models` lists aliases; versioned IDs accepted even if not listed.

### secondary (`systemonemodels.org/glossary/jev/`)

- Shipping version `jev-1.13.0`; aliases `jev-latest` and `jev-preview` both point at it.
- Waitlist removed 2026-09-20 per secondary — **not** re-checked on first-party docs in this pass.

---

## Rate limits (first-party `models.md`, `api.md`)

- **250,000 tokens per second**
- **1,200 requests per minute**
- Over limit → **429 Too Many Requests**; also **529 Overloaded** documented
- SDKs: default retry with backoff; honor `retry-after` when present
- Note on models page: limits **adjusting dynamically** during high demand; can change without notice; enterprise/custom higher limits via sales@typesafe.ai

unofficial-mirror how-to-use repeats same 250k tok/s and 1200 req/min figures (aligned with first-party; still label domain unofficial-mirror if citing from there).

---

## Access, weights, early access

### first-party blog (2026-09-15)

- “Jev, available today in **early access**.”
- “Today, we are opening early access and bringing developers off the waitlist as quickly as we can.”
- Closed managed API implied; no weights release mentioned in fetched blog slice.

### first-party docs

- Not fine-tuned per customer; same weights all accounts (`models.md`).
- Jev not trained on customer requests/responses (data handling section).

### secondary

- Weights not released; closed managed API (`glossary/jev/`).
- jev-explained: not open source; community repros on Qwen/ModernBERT do not reproduce TypeSafe training method.

---

## Latency claims (label measurer)

### first-party blog

- “End-to-end response time is **70ms–500ms** for TypeSafe” vs “3 to 329 seconds” for frontier LLMs on comparable System One shaped queries.
- “**40×–200× faster**” for same intelligence level on System One tasks.
- Evidence nuance: “Speed per call: We truly are that fast, though our **published evals are generally run from our laptops on the West Coast** (this is where our service is currently based).”
- Workflow eval homepage claims (193.6× faster, 444.6× cheaper) attributed to workflow eval site — higher end of real-world gains.

### secondary glossary

- Same 70ms–500ms and 40×–200× figures quoted as **TypeSafe’s own**; “no independent benchmark had been published as of 2026-09-18.”

Blog demo nuance: Jev cardinality up to 255; higher cardinality may use 2-stage score-then-choice (occasional slowdown).

---

## HTTP errors (first-party `api.md`)

| Status | Meaning |
| --- | --- |
| 401 | Bad/missing API key |
| 422 | Validation failure on body |
| 429 | Rate limit |
| 529 | Overloaded |

---

## SDK surface (caller dependency, not HTTP)

- Python: `pip install typesafe-sdk` (≥3.10); `TypeSafeClient().system_one(state=..., questions={...})`; default model `jev-latest`.
- JS: `@typesafe-ai/sdk`, Node ≥20.
- Method name `system_one` / HTTP path `systemone` — naming asymmetry.

Python quickstart reads `response.answers["key"]`; secondary flags alternate `response.choices` in some SDK docs.

---

## Jaggedness / capability bounds (first-party `jev-1.13` jaggedness)

- Not trained to generate text (failure mode #9).
- Weak at counting, arithmetic, date ordering, indirection, large irrelevant state, adversarial state, contradictory criteria.
- Choice max 255 options (blog demo); API docs max 255 per Choice.

---

## unofficial-mirror-only API variant (`jevtypesafeai.com`)

- `POST https://jevtypesafeai.com/api/v1/decide` — parallel question JSON shape (`type`: choice/score/noul) but **different host, key prefix, billing**; not part of first-party TypeSafe contract.
- Pricing on models page: **$0.42/M** input (see pricing section — conflict with first-party only on this domain).

---

## Blog task-shape summary (first-party)

- Inputs: unstructured data, emphasis on **structured program state**.
- Outputs: type-safe structured values; calibrated probabilities + confidence on System One tasks.
- Sampling: parallel, single query for all outputs.
- Use-case framing: classify, route, score, extract, branch; map-reduce; real-time (~100ms UX mention in use-case list); verify/guardrail LLM outputs.
