---
subtask_id: T1-bis
plan: prompt-caching
plan_version: 1.1.0
tier: architectural
model_class: architectural
skills: [executor-subtask-execution]
decision_log_path: .dev/decision-logs/prompt-caching/T1-bis-cache-and-rubric-contract.md
amendment_round: 1
supersedes: T1
---

# Packet T1-bis — Continuation of T1: shared cache-block and rubric-asset contract (amendment round 1, v1.1.0)

## Orientation

- You receive only this packet plus the executor SKILL.md. Do not consult the parent plan; everything binding is reproduced below.
- **You are not starting fresh.** T1 was dispatched, did most of its work, and HALTed only on one specific falsifier. The working tree already contains T1's output: `bishop_shared/prompt_cache.py`, `bishop_shared/rubric_assets.py`, `scripts/rubric_hash.py`, `config/prompts/README.md`, `tests/test_prompt_cache.py`, `tests/test_rubric_assets.py` (all new), plus modifications to `bishop_shared/profile_renderer.py`, `tests/test_profile_renderer.py`, both Dockerfiles, all three `requirements.txt` files, and `pyproject.toml`. 38 of T1's tests already pass. **Consume this tree as your starting point. Do not rewrite it from scratch.** Your job is to finish T1's DoD under the amended contract below and commit.
- **Unrelated dirty files in the same working tree — do not touch, do not `git add`:** `AGENTS.md`, `.cursor/rules/windows-file-tools.mdc`. These predate this plan and are out of scope for your commit.
- **Spec note (plan disposition D6):** `bishop_spec_0_6.md` is INFORMATIONAL for this work and is known-stale on caching — its §12.1/§12.3 still say prompt caching "applies automatically" with "no code change required". That language is wrong and the operator has explicitly chosen not to fix it in this plan. Do not HALT on it and do not edit that file.
- HALT and report rather than guessing forward whenever a kill criterion below fires.

## 1. Task statement

Wire Anthropic prompt caching across all three BISHOP Anthropic batch paths — pre-filter, enrichment Call 1, and enrichment Call 2 — so that each path emits a `cache_control` breakpoint with `ttl: "1h"` on the **last** system block, and so that each path's cached prefix actually clears Claude Haiku 4.5's 4,096-token minimum. Clearing the floor is a content problem, not a padding problem: three quality-bearing rubric annexes are authored (source-shape law for pre-filter, extraction guidance for Call 1, relevance-scoring guidance for Call 2), each becoming a hash-verified asset under the same abort-before-Anthropic discipline the NL profile already has. The batch-poller learns to parse and log `usage` cache fields so enablement is observable rather than blind, and batch assembly gains minimum-volume and maximum-hold controls so batches are large enough to amortize a cache write. The three cache keys stay separate by construction.

**Non-goals:**

- **No model switch.** `ANTHROPIC_MODEL_PREFILTER` and `ANTHROPIC_MODEL_ENRICHMENT` remain `claude-haiku-4-5-20251001`. Switching to Sonnet for its 1,024-token floor is rejected (strategy §17) and would break the G3 pinned-model gate.
- **No padding.** Lorem ipsum, whitespace, or filler to reach 4,096 is rejected (strategy §17). Every token added must carry gate quality.
- **No merged prefixes.** Three cache keys (A pre-filter, B Call 1, C Call 2) stay independent. Putting `source` in a system prompt is rejected (strategy §11b option C) — it destroys prefix identity within a batch.
- **No `BatchRecord` schema change.** No Alembic revision, no `domain.py` / `http.py` / `transitions.py` edit, no new wire fields on `BatchPatchRequest`. Observability is logs only (D8).
- **No spec edit.** `bishop_spec_0_6.md` is not touched by this plan (D6).
- **No profile pin bump for enrichment.** Call 2 stays on `professional_v1.0.0.yaml` (D5).
- **No pre-filter pin revert.** The soft-launch overlay stays live; it gets committed, not reverted (D3).
- **No parked-route change**, no `eval/prefilter_v*/items.json` or `labels.json` edit, no `bishop_shared/content_truncation.py` edit, no change to `stage1_loop._profile_render_hash` semantics.
- **No G7 backfill enablement.** This plan makes backfill *affordable*; turning it on is a separate operator call.
- **No Phase 2 cosine / Gemini / OpenAI work.**
- **Amendment-specific non-goal:** do not migrate `bishop_shared/enrichment_prompts.py` or `services/enrichment-batcher/app/anthropic_batch_client.py`. That surface is T7's row-5 ownership (fork 3 of the original HALT was rejected specifically because it would absorb T7's scope into this subtask). **Amendment round 3:** T7 HALTed with no code; the Call 2 continuation is T7-bis. This packet already landed — do not re-open that migration here.

## 2. Shared contracts

Binding on every subagent. Enforcement mode is one token per row; rows whose verification would mix modes are split.

### Types / interfaces

| # | Contract | Owner | Binding site | Enforcement | Falsifier |
|---|---|---|---|---|---|
| 1 | **New** `bishop_shared/prompt_cache.py`: `HAIKU_CACHE_MIN_TOKENS: Final[int] = 4096`; `CACHE_TTL: Final[str] = "1h"`; `cached_system_blocks(*texts: str) -> list[dict[str, object]]` | T1-bis | `module-function` (+ two module constants) | `pytest-enforced` | `tests/test_prompt_cache.py`: (a) N inputs → N blocks; (b) `cache_control` present on **last** block only; (c) equals `{"type": "ephemeral", "ttl": "1h"}` exactly; (d) two calls return **equal but not identical** dicts (no aliasing across requests); (e) empty input raises `ValueError` |
| 1a | `anthropic` pin floor raised `>=0.40` → `>=0.100` in all three service `requirements.txt` **and** `pyproject.toml` dev extra | T1-bis | `parser-key` (requirements line) | `pytest-enforced` | `tests/test_prompt_cache.py::test_sdk_supports_1h_ttl` asserts `"ttl" in anthropic.types.cache_control_ephemeral_param.CacheControlEphemeralParam.__annotations__`. Falsifies P2 directly. |
| 2 | **New** `bishop_shared/rubric_assets.py`: `PROMPTS_CONTAINER_DIR = Path("/app/config/prompts")`; `RubricId = Literal["prefilter_rubric", "call1_rubric", "call2_rubric"]`; `_RUBRIC_FILENAME: dict[RubricId, str]`; `RubricDocument` (pydantic: `rubric_id: str`, `version: str`, `canonical_hash: str`, `body: str`); `resolve_rubric_path(rubric_id: RubricId) -> Path`; `load_rubric(path: Path) -> RubricDocument`; `compute_rubric_hash(rubric: Path \| str) -> str`; `verify_rubric_hash(rubric_id: RubricId, *, rubric_path: Path \| None = None) -> tuple[str, str, str] \| None` | T1-bis | `module-function` ×5, `pydantic-model` ×1, `dataclass-field` n/a | `pytest-enforced` | `tests/test_rubric_assets.py`: front-matter parse; `resolve_rubric_path` for all three IDs; stamp→verify round trip; mismatch returns `None`; unknown `rubric_id` raises `ValueError` |
| 3 | `render_profile_prompt(profile: ProfileDocument, *, include_output: bool = True) -> str` — new keyword-only param. Default `True` preserves current byte-for-byte output. | T1-bis | `module-function` (signature extension) | `pytest-enforced` | `tests/test_profile_renderer.py`: (a) default render of `professional_v1.2.0_soft_launch.yaml` is **byte-identical** to the pre-change render (pin the current 10,799-char / 2,280-token render); (b) `include_output=False` omits the `## Output format` section and nothing else |
| 4 | `AnthropicBatchResultItem` gains `input_tokens: int \| None = None`, `output_tokens: int \| None = None`, `cache_creation_input_tokens: int \| None = None`, `cache_read_input_tokens: int \| None = None` | T8 | `pydantic-model` fields | `pytest-enforced` | `tests/test_batch_poller_anthropic_client.py`: construction round-trip with and without `usage`; extraction from a fixture whose `message.usage` carries all four |
| 5 | `build_requests` / `build_stage2_requests` accept the system prefix as `list[dict[str, object]]`; `params["system"]` is a block list on **all three** gates. Pre-filter: `build_requests(*, system_blocks: list[dict[str, object]], entries: list[PreFilterBatchEntry])` — the `system_prompt: str` parameter is **retired**. Enrichment Call 1: `build_requests(*, entries: list[Stage1BatchEntry])` signature unchanged; blocks are assembled inside. Call 2: `build_stage2_requests(*, profile_prompt: str, rubric_body: str, entries: list[Stage2BatchEntry])`. | T5 / T6 / **T7-bis** | `instance-method` ×3 | `pytest-enforced` | Per-gate payload tests asserting `isinstance(params["system"], list)` and the retired `system_prompt` kwarg raising `TypeError` |

### Naming

| # | Contract | Owner | Enforcement | Falsifier |
|---|---|---|---|---|
| 6 | New assets: `config/prompts/prefilter_rubric_v1.md` (T2), `config/prompts/call1_rubric_v1.md` (T3), `config/prompts/call2_rubric_v1.md` (T4). New script `scripts/rubric_hash.py` (T1-bis). New modules `bishop_shared/prompt_cache.py`, `bishop_shared/rubric_assets.py` (T1-bis). | T1-bis–T4 | `docs-structural` | Path-existence assertions in each owner's test. **Semantic falsifier** (structural presence proves nothing about content): row 8's token-floor gate plus row 7's hash round-trip. |
| 7 | Rubric front-matter schema, exactly: `---\nrubric_id: <RubricId>\nversion: "<semver>"\ncanonical_hash: "<64-hex>"\n---\n<body>`. `compute_rubric_hash` hashes **body only**, LF-normalized (`\r\n` → `\n`), excluding front matter. | T1-bis | `parser-key` | `pytest-enforced` | `tests/test_rubric_assets.py`: CRLF body and LF body yield the **same** hash; a front-matter `version` edit does **not** change the hash; a one-character body edit **does** |

### Cache-shape contracts

| # | Contract | Owner | Enforcement | Falsifier |
|---|---|---|---|---|
| 8 | **Token floor.** Total measured system-prefix tokens per cache key ≥ **4,506** (`cl100k_base`) = 4,096 × 1.10. The 10% margin exists because `cl100k_base` is a proxy for Anthropic's tokenizer, not the tokenizer itself. Measured on the **total prefix**, not the annex, so the contract cannot go stale when a profile render changes. | T10 (gate); T2/T3/T4 size their annexes to meet it | `pytest-enforced` | **New** `tests/test_prompt_cache_token_floor.py`: one point-literal assertion per key (A, B, C) that the assembled prefix ≥ 4506, printing the measured margin. **Named semantic gap:** a proxy tokenizer cannot prove Anthropic cached anything — the live falsifier is G1's `cache_creation_input_tokens > 0`. |
| 9 | **Single emitter.** No `cache_control` dict literal may appear anywhere outside `bishop_shared/prompt_cache.py`. All three gates obtain blocks from `cached_system_blocks`. **Amendment banner (v1.1.0, round 1) — this is the row that produced this packet:** at T1's original dispatch this row's falsifier could not pass — `bishop_shared/enrichment_prompts.py::build_call2_system_prompt` (pre-existing production code on the live Call 2 wire path, migrated under contract row 5 by **T7**) inlines a `cache_control` literal until T7 lands. That is not a T1/T1-bis defect: T7's files are outside your Files to touch. Verification is split by timing: **you** author `cached_system_blocks` and the grep test; **T10** owns asserting the test green, at its own closure sweep, after T5/T6/T7 have landed. Full discovery: `.dev/plans/prompt-caching/runs/T1-brief.md`. | **T1-bis** (author — this is you); **T10** (verify) | `pytest-enforced` | `tests/test_prompt_cache.py::test_no_inline_cache_control_literals` — tree grep over `bishop_shared/**` and `services/**` excluding `prompt_cache.py`; asserts zero hits. This is the mechanical guard for §5.4 C1. **You may land with this specific test red** — record that explicitly in your decision log, do not silently accept it — because T7 has not migrated yet. **Do not** weaken the grep or add an exemption/exclusion to the test body to make it pass; the test text is frozen as T1 originally wrote it. **Do not** edit T7's files to make it pass either. T10 re-runs it at closure once T7 has landed. |
| 10 | **Breakpoint placement.** Exactly **one** `cache_control` per request, on the **last** system block, on all three gates. Block order: key A `[profile_render, prefilter_rubric]`; key B `[call1_system, call1_rubric]`; key C `[profile_render(include_output=False), call2_rubric, call2_instructions]`. | T5 / T6 / **T7-bis** | `pytest-enforced` | Per-gate: `sum(1 for b in blocks if "cache_control" in b) == 1` **and** the index equals `len(blocks) - 1`. Both assertions required — a count-only test passes with the breakpoint on block 0. |
| 11 | **Batch identity.** Every request within one batch carries byte-identical system blocks. Dynamic per-entry content stays in the user message. | T5 / T6 / **T7-bis** | `pytest-enforced` | Per-gate multi-entry test asserting all requests' `params["system"]` compare equal |

### Error envelope

| # | Contract | Owner | Enforcement | Falsifier |
|---|---|---|---|---|
| 12 | **Rubric hash-or-abort.** Each gate verifies its rubric asset before touching Anthropic: `compute_rubric_hash(path) != doc.canonical_hash` → abort the cycle, no submit. The abort mirrors the existing profile-hash abort in the *same module*. Asymmetry preserved deliberately: **pre-filter** additionally emits the existing CRITICAL alert path in `services/pre-filter-worker/app/alerts.py`; **stage1 and stage2 log only**, matching the M5 T4 deferral. Changing that asymmetry is out of scope. | T5 / T6 / **T7-bis** | `pytest-enforced` | Per-gate: tampered rubric body → Anthropic client **never called**; pre-filter additionally asserts the CRITICAL alert fired; stage1/stage2 assert log-only and **no** alert |
| 13 | **Call 1 gains an abort path it did not have.** `stage1_loop` currently trusts the YAML `canonical_hash` without recompute (`_profile_render_hash`). This plan adds a rubric recompute-and-abort to Call 1 **without** changing `_profile_render_hash`'s profile semantics. | T6 | `pytest-enforced` | `tests/test_enrichment_batcher_stage1_loop.py`: rubric mismatch aborts; **and** a regression test asserting `_profile_render_hash` still returns `load_profile(path).canonical_hash` with no recompute |

### Logging

| # | Contract | Owner | Enforcement | Falsifier |
|---|---|---|---|---|
| 14 | **Poller cache-usage fields.** The existing completion `logger.info("<msg>", extra={...})` lines in all three `_handle_*_complete` functions gain exactly these keys: `cache_read_tokens`, `cache_write_tokens`, `input_tokens`, `output_tokens`, `cache_hit_ratio` (float, `cache_read / (cache_read + cache_write)`, `None` when both are zero). Existing keys (`batch_id`, `external_batch_id`, `event`, `passed`, `failed`/`rejected`) are unchanged. Idiom is preserved: static message string, structured `extra` dict, stdlib `logging`, no f-strings, no structlog. | T8 | `pytest-enforced` | `caplog`-based test per handler asserting the **exact key names** at the emit site (a logging-contract literal needs a print-key assertion, not adjacent line coverage). Plus a reserved-name test: none of the five keys collides with `logging.LogRecord` reserved attributes, since a collision raises at call time. |
| 15 | **Zero-read warning.** When a completed batch reports `cache_read_tokens == 0 and cache_write_tokens == 0`, emit `logger.warning("no cache usage reported", extra={..., "event": "cache_read_zero"})`. This is the misconfiguration detector from strategy §15a. | T8 | `pytest-enforced` | Fixture with zero usage → warning emitted with `event="cache_read_zero"`; fixture with nonzero → **not** emitted (positive and negative path both required) |

### Deployment

| # | Contract | Owner | Enforcement | Falsifier |
|---|---|---|---|---|
| 16 | **Rubric assets are image-baked, never bind-mounted.** `services/pre-filter-worker/Dockerfile` and `services/enrichment-batcher/Dockerfile` gain `COPY config/prompts ./config/prompts`. `docker-compose.yml` **must not** contain any mount whose target is `/app/config/prompts`. Rationale (P1): the profiles mount already masks image-baked files with a hand-populated host dir; an empty-dir mount over baked rubrics would make all three gates abort with no repo-visible cause. Consequence accepted: a rubric change requires an image rebuild, which correctly couples the asset and its stamped hash to one artifact. | T1-bis; verified T10 | `pytest-enforced` | `tests/test_prompt_cache.py::test_no_prompts_bind_mount` parses `docker-compose.yml` and asserts no mount targets `/app/config/prompts`. T1-bis additionally ensures `config/prompts/` exists at its own commit so the new `COPY` cannot break the build in the window before T2–T4 land. |
| 17 | **Mixed provenance is acknowledged, not fixed.** Key A's prefix = host-mounted profile render + image-baked rubric. A host-side profile edit changes key A without an image rebuild; the existing `_verify_profile_hash` abort is the only guard and it only fires if the stamped hash also moved. Not in scope to unify. | — | `deferred` | Follow-up **`FU-CACHE-MOUNT-01`**, owner = operator. Recorded so §5.2 A4 is a bound deferral, not a missed coupling. |

### Config / amortization

| # | Contract | Owner | Enforcement | Falsifier |
|---|---|---|---|---|
| 18 | **Typed env surface.** New and changed keys, each with a typed parse path in its own service `config.py` and a round-trip test. Pre-filter: `BISHOP_PREFILTER_BATCH_SIZE` (unchanged, 50), `BISHOP_PREFILTER_MIN_BATCH_SIZE` (**new**, 25), `BISHOP_PREFILTER_MAX_HOLD_MINUTES` (**new**, 120). Enrichment, **stage 1 and stage 2 tracked separately**: `BISHOP_ENRICHMENT_STAGE1_BATCH_SIZE` (10 → **50**), `BISHOP_ENRICHMENT_STAGE1_MIN_BATCH_SIZE` (**new**, 10), `BISHOP_ENRICHMENT_STAGE1_MAX_HOLD_MINUTES` (**new**, 120), and the identical STAGE2 triad. No `getattr`-papered defaults; every key parses through the typed path or the row is unsatisfied. | T9 | `pytest-enforced` | Per-key: default value, env override, and invalid-value handling. Plus a hold-deadline test (row 19). |
| 19 | **No starvation.** Minimum-volume hold is bounded: a gate submits below `MIN_BATCH_SIZE` once `MAX_HOLD_MINUTES` has elapsed since that gate's last submit. The hold clock is per-gate and in-process; it resets on service restart, and that is accepted and documented. | T9 | `pytest-enforced` | Time-injected test: entries below min are held, then submitted after the deadline passes. **And** a negative test: a hash abort must not extend the hold indefinitely. |

### Frozen surfaces

| # | Contract | Owner | Enforcement | Falsifier |
|---|---|---|---|---|
| 20 | **Byte-unchanged from baseline `b919fdb` through closure:** `bishop_shared/anthropic_config.py`, `bishop_shared/content_truncation.py`, `bishop_shared/batch_custom_id.py`, `eval/prefilter_v0/**`, `eval/prefilter_v1/items.json`, `eval/prefilter_v1/labels.json`, `services/state-worker/app/models/domain.py`, `services/state-worker/app/models/http.py`, `services/state-worker/app/transitions.py`, `services/state-worker/app/routers/parked.py`, `alembic/**`, `bishop_spec_0_6.md`, `config/profiles/professional_v1.0.0.yaml`. | T10 | `pytest-enforced` + closure `git diff` | T10 kill criteria literalize the **full** path list and the SHA range `b919fdb..<closure>`; a partial list is not a discharge. Immediately before the T10 sweep and again before G1, re-run `git log <frozen paths>` — the assumption expires. |

### Tests

| # | Contract | Owner | Enforcement | Falsifier |
|---|---|---|---|---|
| 21 | pytest ≥8, files `tests/test_<area>_<topic>.py`, plain `def test_*() -> None` functions, `unittest.mock` / `httpx.MockTransport`, existing `_load_*_stack()` sys.path idiom for service imports. **No new `conftest.py`** (the repo has none). No new markers. **Declared command:** `pytest tests/ -m "not heavy"`. **Operative command:** identical — no §8 waiver scopes this gate. Collection parity is checked at plan time and again at closure. | all | `pytest-enforced` | T10 records the collected count and confirms the new test modules are actually collected |

### Vocabulary (binding glossary — resolves Flag 8, copied verbatim into every packet)

| # | Term | In this plan it means | It does **not** mean |
|---|---|---|---|
| 22 | **cached prefix** / **prefix** | The concatenated `system` content blocks up to and including the block bearing `cache_control`. | The user message; the Call 1 content tail |
| 22 | **4096** | Claude Haiku 4.5's minimum cacheable prefix, in tokens. Plan target with margin: **4,506**. | The Call 1 `content_raw` truncation ceiling |
| 22 | **4000** | The Call 1 user-tail truncation ceiling in `content_truncation.py` (spec §13.1). **Frozen; unrelated to caching.** | Any cache floor |
| 22 | **profile hash** / `canonical_hash` (profile) | SHA-256 of the JSON-canonical **YAML dict minus `canonical_hash`**. Not the rendered text. | The rendered prompt hash the spec §7.3 prose describes |
| 22 | **rubric hash** / `canonical_hash` (rubric) | SHA-256 of the rubric **body only**, LF-normalized, front matter excluded. | The profile hash; a composite |
| 22 | **`profile_render_hash`** | The existing `BatchRecord` column. Semantics **unchanged** by this plan despite its name. | Anything this plan recomputes |
| 22 | **system** | The Anthropic `params.system` field, a **list of content blocks** after this plan on all three gates. | A plain string |

### Deferred rows

| # | Deferred contract | Why not closed here | What forces it open | Owner |
|---|---|---|---|---|
| 23 | `bishop_spec_0_6.md` §12.1/§12.3 keep asserting Phase 1.5 needs "no code change" and imply a ~1,024 floor, directly contradicting what this plan builds. | Operator decision D6. | Any future reader treating the spec as current on caching. | **`FU-CACHE-SPEC-01`** — operator, outside this plan |
| 24 | Key A's mixed provenance (host-mounted profile + baked rubric) — see row 17. | Unifying the deployment model is a separate ops change with live-traffic risk. | A host-side profile edit that changes cache key A without a rebuild. | **`FU-CACHE-MOUNT-01`** — operator |
| 25 | Call 2 hash mismatch is log-only (no CRITICAL alert), inherited from M5 T4. | Pre-existing asymmetry; changing it widens scope beyond caching. | An unnoticed Call 2 abort during backfill. | **`FU-CACHE-ALERT-01`** — future milestone |

### Decision log path

**`.dev/decision-logs/prompt-caching/T<n>-<slug>.md`** — required for every `architectural` subtask (T2, T3, T4, T6, T7-bis, T9-bis, **T1-bis**). This path is a contract anchor; drift between `decision-logs/` and `decisions/` is a violation, not cleanup. T1 never reached a commit, so no `T1-*.md` log exists to supersede — yours is the first and only architectural record for this surface.

### CHANGELOG convention

`CHANGELOG.MD` is a Files-to-touch entry on **every** subtask in this plan, not only T10. Each subtask appends its own bullet in its own commit.

## 3. Your subtask

### T1-bis — Continuation of T1: land the shared cache/rubric contract (amendment round 1, v1.1.0)

| Field | Content |
|---|---|
| **ID** | `T1-bis` |
| **Scope** | Finish T1's DoD from the existing uncommitted working tree under the amended §2 row 9 (verification timing moved to T10). Not a clean-slate rewrite: the working tree already contains T1's new modules, the stamping script, the Dockerfile bakes, the SDK pin bump, and 38 passing tests. Complete and commit that work; do not re-derive it. |
| **Files to touch** | `bishop_shared/prompt_cache.py` (new, present in tree), `bishop_shared/rubric_assets.py` (new, present), `bishop_shared/profile_renderer.py` (modified, present — includes both T1's `include_output` extension and pre-existing overlay pin edits; do not revert either), `scripts/rubric_hash.py` (new, present), `config/prompts/README.md` (new, present), `tests/test_prompt_cache.py` (new, present), `tests/test_rubric_assets.py` (new, present), `tests/test_profile_renderer.py` (modified, present), `services/pre-filter-worker/Dockerfile` (modified, present), `services/enrichment-batcher/Dockerfile` (modified, present), `services/pre-filter-worker/requirements.txt`, `services/enrichment-batcher/requirements.txt`, `services/batch-poller/requirements.txt` (all modified, present), `pyproject.toml` (modified, present), `CHANGELOG.MD`, `.dev/decision-logs/prompt-caching/T1-bis-cache-and-rubric-contract.md` (new). **Do not touch** `bishop_shared/enrichment_prompts.py` or `services/enrichment-batcher/app/anthropic_batch_client.py` — T7's row-5 ownership; migrating them here was rejected fork 3 of the original HALT. **Do not `git add`** `AGENTS.md` or `.cursor/rules/windows-file-tools.mdc` — unrelated pre-existing dirty files, out of scope. |
| **Contract bindings** | Rows 1, 1a, 2, 3, 6, 7, 9 (author only — verification moved to T10 by amendment round 1), 16, 21, 22. Owner of rows 1, 1a, 2, 3, 7, 16. Author (not verifier) of row 9. |
| **Inputs** | T1 (halted — you consume T1's uncommitted working-tree output directly; there is no other artifact to resolve) |
| **Outputs** | Two shared modules committed; `scripts/rubric_hash.py` committed with frozen CLI `python scripts/rubric_hash.py <path> [--render]`; `config/prompts/` committed; two Dockerfiles baking `config/prompts` committed; SDK floor `>=0.100` committed; three test modules committed (38 tests green; `test_no_inline_cache_control_literals` **expected red** — see kill criteria); decision log recording the HALT, the three offered forks, and why fork 2 was chosen. |
| **Kill criteria** | Re-verify all of T1's original kill criteria still hold on the working tree before committing: **(runtime-invariant)** `cached_system_blocks` places `cache_control` on the last block without mutating a module-level dict shared across requests. **(executor-preflight)** `anthropic>=0.100` is satisfied in this environment. **(mechanical post-check)** Run `docker build -f services/pre-filter-worker/Dockerfile .` and paste the exit code — asserting the build works is not evidence it does. **(mechanical post-check)** Run `git ls-files config/profiles/professional_v1.2.0_soft_launch.yaml` and paste the output — per T1's own HALT report, this file is **already tracked at HEAD**; if the output is empty, HALT and re-investigate rather than silently `git add`-ing it. **(runtime-invariant)** `render_profile_prompt`'s default render is byte-identical to pre-change (pin the 10,799-char / 2,280-token render). HALT if any change would touch a row-20 frozen path. **(row-9 specific — this amendment's own falsifier)** Run `pytest tests/test_prompt_cache.py::test_no_inline_cache_control_literals` and paste the result: it is **expected to fail** with exactly one hit (`bishop_shared/enrichment_prompts.py::build_call2_system_prompt`). Record this expected-red result explicitly in your decision log — do not treat it as silently acceptable, and do not treat it as a reason to keep HALTing. HALT (a genuinely new finding, not a re-run of T1's HALT) if the grep instead finds **any other** hit, or finds **zero** hits while the known T7 literal is still visibly present in `enrichment_prompts.py` (a stale grep/AST miss), or if you find yourself wanting to add an exemption/exclusion clause into the test body — the test text is frozen as T1 originally wrote it; only its *pass-requirement owner* changed. **Do not edit `enrichment_prompts.py` or `anthropic_batch_client.py`** to make the test pass — that is T7's row-5 work. **Run the full suite** `pytest tests/ -m "not heavy"` and paste passed/failed/skipped counts; only `test_no_inline_cache_control_literals` may be red. **Commit your work before reporting done** — T2, T3, T4, T8, T9 hard-depend on this commit existing (§3 commit-order invariant, amendment-rebound onto you). |
| **Log tier** | `architectural` (same tier as the T1 spec this continues) |
| **Model class** | `architectural` — every downstream subtask's contract surface originates here; a wrong breakpoint helper propagates to all three gates |
| **Risks & mitigations** | Same as T1's original risks: the `cache_control` dict is the single most-copied literal in the plan, row 9's grep test is the structural guard for the *other two* gates' inline-literal discipline; CRLF line endings on this Windows checkout could destabilise the rubric body hash (row 7's LF normalisation plus a CRLF-vs-LF equality test); `render_profile_prompt` is consumed by pre-filter, stage2, and `scripts/profile_hash.py` (the keyword-only default-`True` param is chosen precisely so no existing call site changes). **Amendment-specific risk:** committing a tree with one known-red test invites a future reader to assume the plan is broken; the decision log and the §2 row 9 banner exist specifically so that red reads as "expected, owned by T10" rather than "regression." |

## 4. Load-bearing assumptions that name this subtask

**A1** · `invariant` after T1-bis
```
(The Anthropic SDK accepts ttl:"1h" on the GA cache_control param with no beta header | §2 row 1a + services/*/requirements.txt anthropic pin | an install resolved from the old >=0.40 floor rejects or silently drops ttl; all three keys write 5-minute entries, pay the write premium repeatedly, and the 1h benefit never materialises | T1-bis,T5,T6,T7)
```
Confirmed at planning time on `anthropic` 0.100.0: `CacheControlEphemeralParam.ttl: Literal["5m","1h"]` on the GA type. Row 1a's test is the standing falsifier.

**A5** · `invariant`
```
(Rubric body bytes are line-ending stable between authoring, hashing, and prompt emission | §2 row 7 compute_rubric_hash LF normalisation | a CRLF checkout on this Windows host changes both the stamped hash and the model-visible prefix bytes, aborting every gate and churning every cache key | T1-bis,T2,T3,T4)
```

**A7** · `invariant`
```
(config/prompts has no compose bind mount | §2 row 16 + docker-compose.yml | mounting an empty host dir over the baked rubrics makes resolve_rubric_path point at nothing, and all three gates abort with no repo-visible cause — exactly the masking that already hides the baked config/profiles | T1-bis,T10)
```
Confirmed mechanism at planning time: the container's `/app/config` holds only `profiles`, and its two files come from the host mount, not the image.

**A8** · `invariant`
```
(The spec's Phase 1.5 "no code change" language stays uncorrected and executors will not halt on it | §2 row 23 deferred + D6 | an executor reads bishop_spec_0_6.md §12.3 as authority and halts, or hedges its implementation to match a document the operator has chosen not to fix | all subtasks)
```
Mitigated structurally: every packet carries an explicit line marking the spec informational and known-stale on caching.

## 5. Hidden couplings that name this subtask

**C1** · **confirmed — this is the coupling your HALT predecessor discovered live**
```
(params.system wire shape: string vs content-block list | bishop_shared/prompt_cache.py:cached_system_blocks vs the three clients' build_requests | if any one gate inlines its own cache_control dict instead of calling the helper, that gate's breakpoint rule silently diverges from the other two and no per-gate test notices, because each gate only tests itself | T5,T6,T7-bis)
```
**Bound** — §2 row 9 plus `tests/test_prompt_cache.py::test_no_inline_cache_control_literals`, a tree grep asserting zero `cache_control` literals outside the one module. **Amendment round 1 note:** this coupling is exactly what T1's HALT discovered — `build_call2_system_prompt` was still inlining the literal at T1's original dispatch because T7 had not yet run. You author the test; T10 verifies it green once T7 has landed.

**C3** · **confirmed**
```
(three hash notions diverge further | profile_renderer.compute_profile_hash vs pre-filter loop._verify_profile_hash vs stage2_loop._verify_profile_hash vs stage1_loop._profile_render_hash vs the new rubric_assets.compute_rubric_hash | stage 1 will recompute the rubric hash while still trusting the profile's YAML field without recompute, so the same loop enforces two different disciplines and a future reader cannot tell which is intended | T1-bis,T6)
```
**Bound** — §2 row 13 plus a T6 regression test pinning `_profile_render_hash` to `load_profile(path).canonical_hash`, and a T6 kill criterion forbidding the change. The asymmetry is documented in T6's decision log rather than silently inherited.

**C4** · **confirmed** — *found by the packet-only lens; absent from the context map's flag list*
```
(the Call 2 cached prefix would include a gate-1 output contract | profile_renderer.render_profile_prompt appends ProfileOutput.instruction, and professional_v1.0.0.yaml's instruction is the gate-1 {"decision": 0 or 1} JSON, while build_call2_system_prompt then supplies the real relevance schema | moving the breakpoint to the last block caches the contradiction, so every Call 2 row is told to emit a binary decision and a relevance float; today the contradiction exists but only the profile block is marked cacheable, so "just move the breakpoint" makes an existing latent bug permanent and prepaid | T1-bis,T4,T7)
```
**Bound** — §2 row 3 adds `include_output` to `render_profile_prompt` (default `True`, so pre-filter is untouched); T7 renders Call 2 with `include_output=False`; T7 carries a kill criterion forbidding a `{"decision": ...}` instruction inside the cached prefix, and T4 carries the mirror criterion forbidding the annex from reintroducing one.

## 6. Coordination

You are the root node's continuation. T2, T3, T4, T8 and T9 all depend on your committed output (rebound from T1 by amendment round 1). T5, T6, T7, T8, T9 import symbols you own (`prompt_cache`, `rubric_assets`, the extended `render_profile_prompt`). Commit-order invariant: none of those subtasks may land while your work is uncommitted, even if the full suite passes in a dirty tree. **You are not required to make `test_no_inline_cache_control_literals` pass before committing** — that is the one deliberate exception this amendment carves into the "commit only green work" norm, and it exists specifically because the fix for that one test lives in T7, not in you. Everything else must be green before you commit.

## 7. Resolved inputs

From T1 (halted, uncommitted): the entire working tree described in Orientation above — this is not "supplied at execution time" in the usual sense, it is already present on disk. Verify it matches the Files to touch list and the Outputs described above before committing; if the tree diverges materially from what this packet describes (e.g. a file listed as present is actually missing, or contains unexpected content), HALT and report the divergence rather than guessing which version is authoritative.
