---
subtask_id: T7-bis
plan: prompt-caching
plan_version: 1.3.0
tier: architectural
model_class: architectural
skills: [executor-subtask-execution]
decision_log_path: .dev/decision-logs/prompt-caching/T7-bis-call2-breakpoint-move.md
amendment_round: 3
supersedes: T7
---

# Packet T7-bis — Continuation of T7: Enrichment Call 2 wiring (cache key C) (amendment round 3, v1.3.0)

## Orientation

- You receive only this packet plus the executor SKILL.md. Do not consult the parent plan; everything binding is reproduced below.
- **T7 wrote no code.** Like T9-bis, there is no partial T7 working tree to consume. Implement the full Call 2 wiring scope below.
- **You are not starting from the HALT report's HEAD.** T7's brief recorded HEAD `c47248e` (T9-bis). That is stale. T5 then landed at `eb9b873` and **T6 landed at `ba49bb1` after T7 HALTed**. T6 already edited three files you also own: `bishop_shared/enrichment_prompts.py` (Call 1 now returns cached system blocks), `tests/test_enrichment_prompts.py` (Call 1 block-list tests), and `services/enrichment-batcher/app/anthropic_batch_client.py` (Call 1 `build_requests`). Start from **current HEAD** (T6, `ba49bb1`, or whatever is HEAD when you dispatch — it includes T6). Reconcile with T6's Call 1 blocks; do not rewrite those files from the pre-T6 state.
- **Why T7 HALTed (do not repeat this mistake).** Packet T7 §6 required a supersession banner at FIRST mention in `.dev/decision-logs/m5-enrichment/T4-call2-cache-control.md` (M5 recorded `cache_control` on the profile block only). That file is git-tracked and was **not** in T7's Files to touch. Editing it was out of scope; skipping the banner failed §6. This amendment (§7 round 3 of the parent plan) resolves it by **fork a**: that M5 log is in **your** Files to touch so the banner can land at first mention. Full HALT report: `.dev/plans/prompt-caching/runs/T7-brief.md`.
- **Do not invent a new Call 2 caching design.** Scope is T7's original DoD plus the M5-log banner. Fork b (waive §6 / named follow-on) was rejected.
- **You are not in a parallel group.** Rank 2 `{T5, T6, T7}` already ran: T5 and T6 committed; T7 HALTed and is not re-dispatched. T9-bis is also already committed. You run alone, then T10.
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
- **Amendment-specific non-goals:** do not rewrite T6's `build_call1_system_prompt` or Call 1 tests; do not revert T6's Call 1 `build_requests`; do not waive the M5-log banner or route it to a follow-on; do not start from HEAD `c47248e`.

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
| 5 | `build_requests` / `build_stage2_requests` accept the system prefix as `list[dict[str, object]]`; `params["system"]` is a block list on **all three** gates. Pre-filter: `build_requests(*, system_blocks: list[dict[str, object]], entries: list[PreFilterBatchEntry])` — the `system_prompt: str` parameter is **retired**. Enrichment Call 1: `build_requests(*, entries: list[Stage1BatchEntry])` signature unchanged; blocks are assembled inside. Call 2: `build_stage2_requests(*, profile_prompt: str, rubric_body: str, entries: list[Stage2BatchEntry])`. **Amendment banner (v1.3.0, round 3) — Call 2's share is yours:** T7 HALTed with no code (Files-to-touch omitted the M5 T4 cache_control log). You (T7-bis) own Call 2's `build_stage2_requests` / `build_call2_system_prompt` migration. T5 and T6 have already landed their shares. See plan §7 round 3. | T5 / T6 / **T7-bis** | `instance-method` ×3 | `pytest-enforced` | Per-gate payload tests asserting `isinstance(params["system"], list)` and the retired `system_prompt` kwarg raising `TypeError` |

### Naming

| # | Contract | Owner | Enforcement | Falsifier |
|---|---|---|---|---|
| 6 | New assets: `config/prompts/prefilter_rubric_v1.md` (T2), `config/prompts/call1_rubric_v1.md` (T3), `config/prompts/call2_rubric_v1.md` (T4). New script `scripts/rubric_hash.py` (T1-bis). New modules `bishop_shared/prompt_cache.py`, `bishop_shared/rubric_assets.py` (T1-bis). | T1-bis–T4 | `docs-structural` | Path-existence assertions in each owner's test. **Semantic falsifier** (structural presence proves nothing about content): row 8's token-floor gate plus row 7's hash round-trip. |
| 7 | Rubric front-matter schema, exactly: `---\nrubric_id: <RubricId>\nversion: "<semver>"\ncanonical_hash: "<64-hex>"\n---\n<body>`. `compute_rubric_hash` hashes **body only**, LF-normalized (`\r\n` → `\n`), excluding front matter. | T1-bis | `parser-key` | `pytest-enforced` | `tests/test_rubric_assets.py`: CRLF body and LF body yield the **same** hash; a front-matter `version` edit does **not** change the hash; a one-character body edit **does** |

### Cache-shape contracts

| # | Contract | Owner | Enforcement | Falsifier |
|---|---|---|---|---|
| 8 | **Token floor.** Total measured system-prefix tokens per cache key ≥ **4,506** (`cl100k_base`) = 4,096 × 1.10. The 10% margin exists because `cl100k_base` is a proxy for Anthropic's tokenizer, not the tokenizer itself. Measured on the **total prefix**, not the annex, so the contract cannot go stale when a profile render changes. | T10 (gate); T2/T3/T4 size their annexes to meet it | `pytest-enforced` | **New** `tests/test_prompt_cache_token_floor.py`: one point-literal assertion per key (A, B, C) that the assembled prefix ≥ 4506, printing the measured margin. **Named semantic gap:** a proxy tokenizer cannot prove Anthropic cached anything — the live falsifier is G1's `cache_creation_input_tokens > 0`. |
| 9 | **Single emitter.** No `cache_control` dict literal may appear anywhere outside `bishop_shared/prompt_cache.py`. All three gates obtain blocks from `cached_system_blocks`. **Amendment banner (v1.1.0, round 1):** at T1's original dispatch this row's falsifier could not pass — `bishop_shared/enrichment_prompts.py::build_call2_system_prompt` (pre-existing production code on the live Call 2 wire path) inlined a `cache_control` literal. **Amendment banner (v1.3.0, round 3) — you are the migrator:** T7 HALTed with no code, so that inline literal is still in HEAD. **Your landing is what turns the grep green.** T10 verifies green at closure after you land. Do not leave a `cache_control` dict literal in `build_call2_system_prompt`; call `cached_system_blocks`. | **T1-bis** (author); **T10** (verify); **T7-bis** (removes the remaining Call 2 literal) | `pytest-enforced` | `tests/test_prompt_cache.py::test_no_inline_cache_control_literals` — tree grep over `bishop_shared/**` and `services/**` excluding `prompt_cache.py`; asserts zero hits. This is the mechanical guard for §5.4 C1. T1-bis landed with this test red (documented); **your landing is what turns it green**, and T10 re-runs it at closure to confirm. |
| 10 | **Breakpoint placement.** Exactly **one** `cache_control` per request, on the **last** system block, on all three gates. Block order: key A `[profile_render, prefilter_rubric]`; key B `[call1_system, call1_rubric]` (**already landed by T6**); key C `[profile_render(include_output=False), call2_rubric, call2_instructions]` (**yours**). | T5 / T6 / **T7-bis** | `pytest-enforced` | Per-gate: `sum(1 for b in blocks if "cache_control" in b) == 1` **and** the index equals `len(blocks) - 1`. Both assertions required — a count-only test passes with the breakpoint on block 0. |
| 11 | **Batch identity.** Every request within one batch carries byte-identical system blocks. Dynamic per-entry content stays in the user message. | T5 / T6 / **T7-bis** | `pytest-enforced` | Per-gate multi-entry test asserting all requests' `params["system"]` compare equal |

### Error envelope

| # | Contract | Owner | Enforcement | Falsifier |
|---|---|---|---|---|
| 12 | **Rubric hash-or-abort.** Each gate verifies its rubric asset before touching Anthropic: `compute_rubric_hash(path) != doc.canonical_hash` → abort the cycle, no submit. The abort mirrors the existing profile-hash abort in the *same module*. Asymmetry preserved deliberately: **pre-filter** additionally emits the existing CRITICAL alert path in `services/pre-filter-worker/app/alerts.py`; **stage1 and stage2 log only**, matching the M5 T4 deferral. Changing that asymmetry is out of scope. T6 already landed stage 1's log-only abort; you land stage 2's. | T5 / T6 / **T7-bis** | `pytest-enforced` | Per-gate: tampered rubric body → Anthropic client **never called**; pre-filter additionally asserts the CRITICAL alert fired; stage1/stage2 assert log-only and **no** alert |
| 13 | **Call 1 gains an abort path it did not have.** `stage1_loop` currently trusts the YAML `canonical_hash` without recompute (`_profile_render_hash`). This plan adds a rubric recompute-and-abort to Call 1 **without** changing `_profile_render_hash`'s profile semantics. **Landed by T6** — do not reopen. | T6 | `pytest-enforced` | `tests/test_enrichment_batcher_stage1_loop.py`: rubric mismatch aborts; **and** a regression test asserting `_profile_render_hash` still returns `load_profile(path).canonical_hash` with no recompute |

### Logging

| # | Contract | Owner | Enforcement | Falsifier |
|---|---|---|---|---|
| 14 | **Poller cache-usage fields.** The existing completion `logger.info("<msg>", extra={...})` lines in all three `_handle_*_complete` functions gain exactly these keys: `cache_read_tokens`, `cache_write_tokens`, `input_tokens`, `output_tokens`, `cache_hit_ratio` (float, `cache_read / (cache_read + cache_write)`, `None` when both are zero). Existing keys (`batch_id`, `external_batch_id`, `event`, `passed`, `failed`/`rejected`) are unchanged. Idiom is preserved: static message string, structured `extra` dict, stdlib `logging`, no f-strings, no structlog. | T8 | `pytest-enforced` | `caplog`-based test per handler asserting the **exact key names** at the emit site (a logging-contract literal needs a print-key assertion, not adjacent line coverage). Plus a reserved-name test: none of the five keys collides with `logging.LogRecord` reserved attributes, since a collision raises at call time. |
| 15 | **Zero-read warning.** When a completed batch reports `cache_read_tokens == 0 and cache_write_tokens == 0`, emit `logger.warning("no cache usage reported", extra={..., "event": "cache_read_zero"})`. This is the misconfiguration detector from strategy §15a. | T8 | `pytest-enforced` | Fixture with zero usage → warning emitted with `event="cache_read_zero"`; fixture with nonzero → **not** emitted (positive and negative path both required) |

### Deployment

| # | Contract | Owner | Enforcement | Falsifier |
|---|---|---|---|---|
| 16 | **Rubric assets are image-baked, never bind-mounted.** `services/pre-filter-worker/Dockerfile` and `services/enrichment-batcher/Dockerfile` gain `COPY config/prompts ./config/prompts`. `docker-compose.yml` **must not** contain any mount whose target is `/app/config/prompts`. Rationale (P1): the profiles mount already masks image-baked files with a hand-populated host dir; an empty-dir mount over baked rubrics would make all three gates abort with no repo-visible cause. Consequence accepted: a rubric change requires an image rebuild, which correctly couples the asset and its stamped hash to one artifact. | T1-bis; verified T10 | `pytest-enforced` | `tests/test_prompt_cache.py::test_no_prompts_bind_mount` parses `docker-compose.yml` and asserts no mount targets `/app/config/prompts`. T1-bis additionally creates `config/prompts/` at its own commit so the new `COPY` cannot break the build in the window before T2–T4 land. |
| 17 | **Mixed provenance is acknowledged, not fixed.** Key A's prefix = host-mounted profile render + image-baked rubric. A host-side profile edit changes key A without an image rebuild; the existing `_verify_profile_hash` abort is the only guard and it only fires if the stamped hash also moved. Not in scope to unify. | — | `deferred` | Follow-up **`FU-CACHE-MOUNT-01`**, owner = operator. Recorded so §5.2 A4 is a bound deferral, not a missed coupling. |

### Config / amortization

| # | Contract | Owner | Enforcement | Falsifier |
|---|---|---|---|---|
| 18 | **Typed env surface.** New and changed keys, each with a typed parse path in its own service `config.py` and a round-trip test. Pre-filter: `BISHOP_PREFILTER_BATCH_SIZE` (unchanged, 50), `BISHOP_PREFILTER_MIN_BATCH_SIZE` (**new**, 25), `BISHOP_PREFILTER_MAX_HOLD_MINUTES` (**new**, 120). Enrichment, **stage 1 and stage 2 tracked separately**: `BISHOP_ENRICHMENT_STAGE1_BATCH_SIZE` (10 → **50**), `BISHOP_ENRICHMENT_STAGE1_MIN_BATCH_SIZE` (**new**, 10), `BISHOP_ENRICHMENT_STAGE1_MAX_HOLD_MINUTES` (**new**, 120), and the identical STAGE2 triad. No `getattr`-papered defaults; every key parses through the typed parse path or the row is unsatisfied. **Landed by T9-bis** — do not reopen. | **T9-bis** | `pytest-enforced` | Per-key: default value, env override, and invalid-value handling. Plus a hold-deadline test (row 19). |
| 19 | **No starvation.** Minimum-volume hold is bounded: a gate submits below `MIN_BATCH_SIZE` once `MAX_HOLD_MINUTES` has elapsed since that gate's last submit. The hold clock is per-gate and in-process; it resets on service restart, and that is accepted and documented. **Landed by T9-bis.** | **T9-bis** | `pytest-enforced` | Time-injected test: entries below min are held, then submitted after the deadline passes. **And** a negative test: a hash abort must not extend the hold indefinitely. |

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

**`.dev/decision-logs/prompt-caching/T<n>-<slug>.md`** — required for every `architectural` subtask (T1-bis, T2, T3, T4, T6, **T7-bis**, T9-bis). This path is a contract anchor; drift between `decision-logs/` and `decisions/` is a violation, not cleanup.

**Amendment round 3 (v1.3.0):** T7 never reached a commit before its HALT (no code written), so no `T7-*.md` decision log was ever written. **You (T7-bis)** are the architectural subtask that actually lands Call 2 wiring; your decision log is `.dev/decision-logs/prompt-caching/T7-bis-call2-breakpoint-move.md`. You additionally edit `.dev/decision-logs/m5-enrichment/T4-call2-cache-control.md` (already tracked) with a supersession banner at first mention pointing at that T7-bis log as the new authority.

### CHANGELOG convention

`CHANGELOG.MD` is a Files-to-touch entry on **every** subtask in this plan, not only T10. Each subtask appends its own bullet in its own commit.

## 3. Your subtask

### T7-bis — Continuation of T7: Enrichment Call 2 wiring (cache key C) (amendment round 3, v1.3.0)

| Field | Content |
|---|---|
| **ID** | `T7-bis` |
| **Scope** | Execute T7's original scope from current HEAD (includes T6): move the Call 2 `cache_control` breakpoint from the first system block to the **last**, add `ttl: "1h"`, insert the Call 2 rubric, and stop caching the gate-1 output contract that the v1.0.0 profile render currently drags into the Call 2 prefix. Additionally place a supersession banner at first mention in the M5 T4 cache_control log. |
| **Files to touch** | `bishop_shared/enrichment_prompts.py` (T6 already converted `build_call1_system_prompt`; you own **only** `build_call2_system_prompt`), `services/enrichment-batcher/app/anthropic_batch_client.py` (T6 already converted Call 1 `build_requests`; you own `build_stage2_requests` / `submit_stage2_batch`), `services/enrichment-batcher/app/stage2_loop.py`, `tests/test_enrichment_prompts.py` (T6 already added Call 1 block tests; update **only** Call 2 tests — do not edit `test_call1_*`), `tests/test_enrichment_batcher_stage2_loop.py`, `CHANGELOG.MD`, `.dev/decision-logs/prompt-caching/T7-bis-call2-breakpoint-move.md` (new — T7 never wrote `T7-call2-breakpoint-move.md`), **`.dev/decision-logs/m5-enrichment/T4-call2-cache-control.md`** (amendment round 3 addition — supersession banner at FIRST mention, pointing at your T7-bis decision log; appending a note at the end is not sufficient) |
| **Contract bindings** | Rows 1, 2, 3, 5, 8, 9, 10, 11, 12, 21, 22. |
| **Inputs** | **T1-bis** (`include_output` param, `cached_system_blocks`); T4 (stamped `call2_rubric_v1.md`); **T6 (already committed at `ba49bb1`)** — shared-file state to reconcile, not a new design input. T5 (`eb9b873`) and T9-bis (`c47248e`) are already committed; you do not re-implement them. |
| **Outputs** | Three-block Call 2 system with one `cache_control` on the last block; profile rendered with `include_output=False`; rubric abort (log-only); updated Call 2 tests; T7-bis decision log recording the breakpoint move **and** the output-contract removal as two distinct decisions **and** the HALT/fork-a resolution; M5 log supersession banner at first mention |
| **Kill criteria** | **(runtime-invariant)** HALT if more than one block carries `cache_control`, or if it is not on the last block. HALT if the cached prefix contains a `{"decision": 0 or 1}` instruction — v1.0.0's `output.instruction` is a **gate-1** contract and caching it ahead of the relevance schema ships a contradiction to the model on every row (§5.4 C4). HALT if the enrichment pin moves off `professional_v1.0.0.yaml` (D5). **(C2 — current HEAD line numbers, not T7 packet's stale 29-32 / 178-179)** Must update `tests/test_enrichment_prompts.py::test_call2_system_has_cache_control` (currently lines 83-88, asserting `blocks[0]["cache_control"] == {"type": "ephemeral"}` with no `ttl`) and `tests/test_enrichment_batcher_stage2_loop.py:182` (same assertion on the wire payload). Replacement assertions must check **both** count and last-block index (row 10). Do **not** edit T6's Call 1 tests in the same file (`test_call1_includes_taxonomy`, `test_call1_system_is_two_block_list_with_rubric_annex_last`, `test_call1_system_single_cache_control_breakpoint_on_last_block`, `test_call1_system_prompt_fresh_blocks_each_call`). **(amendment round 3 — T6 reconcile)** HALT if your diff reverts or rewrites `build_call1_system_prompt`, T6's Call 1 `build_requests`, or T6's Call 1 tests. HALT if you start from or reset to HEAD `c47248e`. **(amendment round 3 — M5 log banner)** The supersession banner on `.dev/decision-logs/m5-enrichment/T4-call2-cache-control.md` must sit at the **first sentence that records the profile-block-only `cache_control` decision** (today: the `# T4 — ...` title / **Chosen approach** bullet that says ephemeral `cache_control` on the profile block). Appending a *Landed:* note at the end does not discharge this. Point the banner at `.dev/decision-logs/prompt-caching/T7-bis-call2-breakpoint-move.md` as the new authority. **(mechanical post-check)** Run `git ls-files .dev/decision-logs/m5-enrichment/T4-call2-cache-control.md` and paste the output — empty means the tracked-path premise was wrong. HALT rather than invent a new Call 2 caching design (three-block order, last-block breakpoint, `include_output=False`, log-only abort are frozen). No inline `cache_control` literal (row 9). |
| **Log tier** | `architectural` — a schema-stable **semantic inversion**: which content is billed at cache-read price versus full price reverses, and the removal of the gate-1 output contract changes what the model is told to produce. No structural or AST test can see either change. Same tier as the T7 spec it continues. |
| **Model class** | `architectural` |
| **Risks & mitigations** | This is the only gate where caching is already partially wired, so it is the one most likely to look correct while being wrong. Row 10's paired assertions (count **and** index) exist for this subtask. **Amendment-specific:** T6 landed on the same two Python files after T7 HALTed; treating the T7 packet's pre-T6 resolved inputs (line numbers 52-75 / tests 29-32) as current will edit the wrong tests. Current HEAD facts are in §7 below. Widening Files to touch by one tracked decision log is a narrow narrative fix; the risk is skipping the first-mention placement or rewriting the M5 log's Chosen approach instead of banner-superseding it. |

## 4. Load-bearing assumptions that name this subtask

**A1** · `invariant` after T1-bis
```
(The Anthropic SDK accepts ttl:"1h" on the GA cache_control param with no beta header | §2 row 1a + services/*/requirements.txt anthropic pin | an install resolved from the old >=0.40 floor rejects or silently drops ttl; all three keys write 5-minute entries, pay the write premium repeatedly, and the 1h benefit never materialises | T1,T5,T6,T7-bis)
```
Confirmed at planning time on `anthropic` 0.100.0: `CacheControlEphemeralParam.ttl: Literal["5m","1h"]` on the GA type. Row 1a's test is the standing falsifier. **Amendment round 3:** tuple relabeled `T7` → `T7-bis` (T7 never landed the Call 2 `ttl`).

**A8** · `invariant`
```
(The spec's Phase 1.5 "no code change" language stays uncorrected and executors will not halt on it | §2 row 23 deferred + D6 | an executor reads bishop_spec_0_6.md §12.3 as authority and halts, or hedges its implementation to match a document the operator has chosen not to fix | all subtasks)
```
Mitigated structurally: every packet carries an explicit line marking the spec informational and known-stale on caching.

## 5. Hidden couplings that name this subtask

**C1** · **confirmed**
```
(params.system wire shape: string vs content-block list | bishop_shared/prompt_cache.py:cached_system_blocks vs the three clients' build_requests | if any one gate inlines its own cache_control dict instead of calling the helper, that gate's breakpoint rule silently diverges from the other two and no per-gate test notices, because each gate only tests itself | T5,T6,T7-bis)
```
**Bound** — §2 row 9 plus `tests/test_prompt_cache.py::test_no_inline_cache_control_literals`. **Amendment round 1 note (v1.1.0):** T1's HALT discovered this because Call 2 had not migrated yet. **Amendment round 3:** T7 never migrated; **your landing is what turns this test green**; T10 confirms it at closure.

**C2** · **confirmed**
```
(existing tests assert the pre-move cache shape | tests/test_enrichment_prompts.py:83-88, tests/test_enrichment_batcher_stage2_loop.py:182, tests/test_prefilter_anthropic_client.py:73 | these fail by construction the moment the breakpoint moves or the system becomes a list; an executor that "fixes" them by loosening the assertion removes the only guard on breakpoint placement | T5,T7-bis)
```
**Amendment round 3:** line numbers refreshed against T6's HEAD (`ba49bb1`). T7's packet still cites the pre-T6 lines 29-32 / 178-179; those now point at T6's Call 1 fixture/tests. Use the current lines above. T5's prefilter assertion already landed. **Bound** — each assertion is named with its file:line in the owning subtask's kill criteria, and row 10 requires the replacement to assert **both** the count and the index.

**C4** · **confirmed** — *found by the packet-only lens; absent from the context map's flag list*
```
(the Call 2 cached prefix would include a gate-1 output contract | profile_renderer.render_profile_prompt appends ProfileOutput.instruction, and professional_v1.0.0.yaml's instruction is the gate-1 {"decision": 0 or 1} JSON, while build_call2_system_prompt then supplies the real relevance schema | moving the breakpoint to the last block caches the contradiction, so every Call 2 row is told to emit a binary decision and a relevance float; today the contradiction exists but only the profile block is marked cacheable, so "just move the breakpoint" makes an existing latent bug permanent and prepaid | T1,T4,T7-bis)
```
**Bound** — §2 row 3 adds `include_output` to `render_profile_prompt` (default `True`, so pre-filter is untouched); **you** render Call 2 with `include_output=False`; you carry a kill criterion forbidding a `{"decision": ...}` instruction inside the cached prefix; T4 already landed the annex without reintroducing one.

**C9** · **confirmed** — *found by the packet-only lens; not in the context map*
```
(minimum-volume hold interacts with hash-or-abort | T9-bis's per-gate hold clock in the three loops vs T5/T6/T7-bis's abort-before-submit paths | a hash mismatch aborts the cycle before submit, so if the hold clock only advances on a successful submit, one bad hash converts a temporary abort into permanent starvation: entries accumulate, the deadline never fires, and the gate looks merely idle | T5,T6,T7-bis,T9-bis)
```
**Amendment round 2:** relabeled `T9` → `T9-bis`. **Amendment round 3:** relabeled `T7` → `T7-bis` (T7 never landed the stage-2 rubric abort). T9-bis already landed; you must not regress the hold-clock-advances-on-abort behaviour when you add the stage-2 rubric abort. **Bound** — T9-bis kill criterion required the maximum-hold deadline to be reachable on every path including the abort path; your stage-2 abort must keep that reachable.

**C13** · **confirmed** — amendment round 3 (T6 landed after T7 HALTed)
```
(T6 already committed Call 1 block assembly into the files T7 also owned | bishop_shared/enrichment_prompts.py::build_call1_system_prompt + tests/test_enrichment_prompts.py Call 1 tests + anthropic_batch_client.py Call 1 build_requests, committed at ba49bb1 | rewriting those files from the pre-T6 tree or from the T7 HALT report's stale HEAD c47248e reverts cache key B while looking like Call 2 wiring | T6,T7-bis)
```
**Bound** — kill criterion above forbidding revert of T6's Call 1 builder, Call 1 `build_requests`, and `test_call1_*`. Start from current HEAD.

## 6. Coordination

You do **not** run in parallel with T5 or T6. Both have committed (T5 `eb9b873`, T6 `ba49bb1`). T7's original packet said you would share `bishop_shared/enrichment_prompts.py` with a still-running T6; that race is over — T6 won the commit-order and you reconcile. Contract row 9 is a direct instruction: obtain Call 2 cache blocks from `bishop_shared/prompt_cache.py::cached_system_blocks` and do not write a `cache_control` dict literal anywhere in your diff. You own `build_call2_system_prompt`; T6 owns `build_call1_system_prompt` — do not touch T6's builder. T9-bis already changed WHEN stage 2 submits; you change WHAT it submits. Do not change hold-clock / min-batch logic.

**Decision-log supersession duty (now in Files to touch).** Your change contradicts `.dev/decision-logs/m5-enrichment/T4-call2-cache-control.md`, which records the `cache_control` breakpoint on the profile block only and records "Omit cache_control when profile is short: Rejected". That log currently scans as current authority. Put a supersession banner at that log's **FIRST mention** pointing to `.dev/decision-logs/prompt-caching/T7-bis-call2-breakpoint-move.md` as the new authority — appending a note at the end is not sufficient, because a reader who stops at first mention never reaches it. This path **is** in your Files to touch (amendment round 3, fork a). T7's packet is retained unmodified as the historical HALT record and is not re-dispatched.

**Runner-ledger bypass (not yours).** This amendment's plan artifacts were committed out-of-band from plan-runner. Do **not** edit `runs/ledger.md` or `runs/execution-summary.md`.

## 7. Resolved inputs

From T1-bis (committed, `8d9af01`): `bishop_shared/prompt_cache.py` (`cached_system_blocks`, `CACHE_TTL`) and `render_profile_prompt(profile, *, include_output: bool = True)`, plus `bishop_shared/rubric_assets.py` (`verify_rubric_hash`, `resolve_rubric_path`, `load_rubric`). From T4 (committed, `e4b7e9d`): stamped `config/prompts/call2_rubric_v1.md`. From **T6 (committed, `ba49bb1` — this is current HEAD at amendment time):** `build_call1_system_prompt()` already returns `cached_system_blocks(schema_text, rubric_body)` (two blocks, breakpoint on last); `tests/test_enrichment_prompts.py` already has Call 1 block-list tests and an autouse fixture patching `PROMPTS_CONTAINER_DIR` to the repo `config/prompts` (reuse it when Call 2 starts loading `call2_rubric`); Call 1 `build_requests` already emits a block list. **Do not revert any of that.**

**Call 2 current-state facts at HEAD `ba49bb1` (not at T7's stale `c47248e`):** `build_call2_system_prompt(profile_prompt)` is at `bishop_shared/enrichment_prompts.py:64-87` and still returns exactly 2 blocks — block 0 is `{"type": "text", "text": profile_prompt, "cache_control": {"type": "ephemeral"}}` (no `ttl`) and block 1 is the relevance_score / relevance_reason / value_rationale JSON schema with no `cache_control`. `services/enrichment-batcher/app/anthropic_batch_client.py::build_stage2_requests` (lines 92-121) still takes `(*, profile_prompt, entries)` only — **no `rubric_body` yet**; it assigns `build_call2_system_prompt(profile_prompt)` to `params["system"]` with `_CALL2_MAX_TOKENS = 512`. `submit_stage2_batch` (lines 123-130) forwards the same kwargs. `stage2_loop._verify_profile_hash` (line 58) still calls `render_profile_prompt(profile)` with the default `include_output=True` — you must pass `include_output=False` for Call 2. There is not yet a stage-2 rubric hash-or-abort; T6's `stage1_loop` is the log-only pattern to mirror, not pre-filter's CRITICAL alert. The enrichment pin is `professional_v1.0.0.yaml`, whose `output.instruction` is the gate-1 string `Respond with a JSON object: {"decision": 0 or 1, "rationale": "one sentence"}` — that is the contradiction coupling C4 exists to remove from your cached prefix.

**C2 assertions at current HEAD:** `tests/test_enrichment_prompts.py::test_call2_system_has_cache_control` lines 83-88; `tests/test_enrichment_batcher_stage2_loop.py` line 182. Both assert `blocks[0]["cache_control"] == {"type": "ephemeral"}`. T7's packet cited lines 29-32 and 178-179; those numbers are wrong after T6.

**M5 log (tracked):** `.dev/decision-logs/m5-enrichment/T4-call2-cache-control.md`, committed at `47c7d91`. First mention of the superseded decision is the Chosen approach bullet "submit Call 2 Anthropic batch with `build_call2_system_prompt` (ephemeral `cache_control` on profile block)". Alternatives rejected includes "Omit `cache_control` when profile is short: Rejected". Full HALT context: `.dev/plans/prompt-caching/runs/T7-brief.md`.
