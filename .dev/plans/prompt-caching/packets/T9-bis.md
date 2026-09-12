---
subtask_id: T9-bis
plan: prompt-caching
plan_version: 1.2.0
tier: architectural
model_class: architectural
skills: [executor-subtask-execution]
decision_log_path: .dev/decision-logs/prompt-caching/T9-bis-batch-amortization.md
amendment_round: 2
supersedes: T9
---

# Packet T9-bis — Continuation of T9: batch amortization, minimum volume and maximum hold (amendment round 2, v1.2.0)

## Orientation

- You receive only this packet plus the executor SKILL.md. Do not consult the parent plan; everything binding is reproduced below.
- **You are starting from a clean slate, unlike T1-bis.** T9 HALTed before writing any code: nothing was staged or committed under that node. There is no partial working tree to consume. Implement the full scope below from the current committed state of the repo.
- **Why T9 HALTed (do not repeat this mistake).** T9's own Files to touch did not include `tests/test_enrichment_batcher_config.py`. That pre-existing file pins the enrichment stage1/stage2 batch-size defaults at `10` in `test_enrichment_stage1_batch_size_default` and `test_enrichment_stage2_batch_size_default`. Raising those defaults to `50` (row 18, below) as originally scoped would break both assertions, and T9 was not permitted to edit a file outside its declared Files to touch to fix them. This amendment (§7 round 2 of the parent plan) resolves it by fork 1: `tests/test_enrichment_batcher_config.py` is added to **your** Files to touch, specifically and only to update those two point-literal assertions from `10` to `50`. Full HALT report: `.dev/plans/prompt-caching/runs/T9-brief.md`.
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
- **Amendment-specific non-goal:** do not touch any assertion in `tests/test_enrichment_batcher_config.py` other than the two named in row 18 below (`test_enrichment_stage1_batch_size_default`, `test_enrichment_stage2_batch_size_default`). The file's other four tests (`test_enrichment_stage1_batch_size_env_override`, `test_enrichment_stage2_batch_size_env_override`, `test_enrichment_poll_interval_default`, `test_enrichment_poll_interval_env_override`, `test_state_worker_url_default`) are unrelated to this amendment; touching them is scope creep.

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
| 5 | `build_requests` / `build_stage2_requests` accept the system prefix as `list[dict[str, object]]`; `params["system"]` is a block list on **all three** gates. Pre-filter: `build_requests(*, system_blocks: list[dict[str, object]], entries: list[PreFilterBatchEntry])` — the `system_prompt: str` parameter is **retired**. Enrichment Call 1: `build_requests(*, entries: list[Stage1BatchEntry])` signature unchanged; blocks are assembled inside. Call 2: `build_stage2_requests(*, profile_prompt: str, rubric_body: str, entries: list[Stage2BatchEntry])`. | T5 / T6 / T7 | `instance-method` ×3 | `pytest-enforced` | Per-gate payload tests asserting `isinstance(params["system"], list)` and the retired `system_prompt` kwarg raising `TypeError` |

### Naming

| # | Contract | Owner | Enforcement | Falsifier |
|---|---|---|---|---|
| 6 | New assets: `config/prompts/prefilter_rubric_v1.md` (T2), `config/prompts/call1_rubric_v1.md` (T3), `config/prompts/call2_rubric_v1.md` (T4). New script `scripts/rubric_hash.py` (T1-bis). New modules `bishop_shared/prompt_cache.py`, `bishop_shared/rubric_assets.py` (T1-bis). | T1-bis–T4 | `docs-structural` | Path-existence assertions in each owner's test. **Semantic falsifier** (structural presence proves nothing about content): row 8's token-floor gate plus row 7's hash round-trip. |
| 7 | Rubric front-matter schema, exactly: `---\nrubric_id: <RubricId>\nversion: "<semver>"\ncanonical_hash: "<64-hex>"\n---\n<body>`. `compute_rubric_hash` hashes **body only**, LF-normalized (`\r\n` → `\n`), excluding front matter. | T1-bis | `parser-key` | `pytest-enforced` | `tests/test_rubric_assets.py`: CRLF body and LF body yield the **same** hash; a front-matter `version` edit does **not** change the hash; a one-character body edit **does** |

### Cache-shape contracts

| # | Contract | Owner | Enforcement | Falsifier |
|---|---|---|---|---|
| 8 | **Token floor.** Total measured system-prefix tokens per cache key ≥ **4,506** (`cl100k_base`) = 4,096 × 1.10. The 10% margin exists because `cl100k_base` is a proxy for Anthropic's tokenizer, not the tokenizer itself. Measured on the **total prefix**, not the annex, so the contract cannot go stale when a profile render changes. | T10 (gate); T2/T3/T4 size their annexes to meet it | `pytest-enforced` | **New** `tests/test_prompt_cache_token_floor.py`: one point-literal assertion per key (A, B, C) that the assembled prefix ≥ 4506, printing the measured margin. **Named semantic gap:** a proxy tokenizer cannot prove Anthropic cached anything — the live falsifier is G1's `cache_creation_input_tokens > 0`. |
| 9 | **Single emitter.** No `cache_control` dict literal may appear anywhere outside `bishop_shared/prompt_cache.py`. All three gates obtain blocks from `cached_system_blocks`. **Amendment banner (v1.1.0, round 1):** at T1's original dispatch this row's falsifier could not pass — `bishop_shared/enrichment_prompts.py::build_call2_system_prompt` (pre-existing production code migrated under contract row 5 by T7) inlines a `cache_control` literal until T7 lands. Verification is split by timing: T1-bis authors the helper + test; T10 verifies green at closure. See plan §7 round 1. | **T1-bis** (author); **T10** (verify) | `pytest-enforced` | `tests/test_prompt_cache.py::test_no_inline_cache_control_literals` — tree grep over `bishop_shared/**` and `services/**` excluding `prompt_cache.py`; asserts zero hits. This is the mechanical guard for §5.4 C1. T1-bis may land with this test red (documented, not silent); T10 re-runs it at closure. This row is **not** yours to touch or verify — reproduced here only because it is copied verbatim into every packet. |
| 10 | **Breakpoint placement.** Exactly **one** `cache_control` per request, on the **last** system block, on all three gates. Block order: key A `[profile_render, prefilter_rubric]`; key B `[call1_system, call1_rubric]`; key C `[profile_render(include_output=False), call2_rubric, call2_instructions]`. | T5 / T6 / T7 | `pytest-enforced` | Per-gate: `sum(1 for b in blocks if "cache_control" in b) == 1` **and** the index equals `len(blocks) - 1`. Both assertions required — a count-only test passes with the breakpoint on block 0. |
| 11 | **Batch identity.** Every request within one batch carries byte-identical system blocks. Dynamic per-entry content stays in the user message. | T5 / T6 / T7 | `pytest-enforced` | Per-gate multi-entry test asserting all requests' `params["system"]` compare equal |

### Error envelope

| # | Contract | Owner | Enforcement | Falsifier |
|---|---|---|---|---|
| 12 | **Rubric hash-or-abort.** Each gate verifies its rubric asset before touching Anthropic: `compute_rubric_hash(path) != doc.canonical_hash` → abort the cycle, no submit. The abort mirrors the existing profile-hash abort in the *same module*. Asymmetry preserved deliberately: **pre-filter** additionally emits the existing CRITICAL alert path in `services/pre-filter-worker/app/alerts.py`; **stage1 and stage2 log only**, matching the M5 T4 deferral. Changing that asymmetry is out of scope. | T5 / T6 / T7 | `pytest-enforced` | Per-gate: tampered rubric body → Anthropic client **never called**; pre-filter additionally asserts the CRITICAL alert fired; stage1/stage2 assert log-only and **no** alert |
| 13 | **Call 1 gains an abort path it did not have.** `stage1_loop` currently trusts the YAML `canonical_hash` without recompute (`_profile_render_hash`). This plan adds a rubric recompute-and-abort to Call 1 **without** changing `_profile_render_hash`'s profile semantics. | T6 | `pytest-enforced` | `tests/test_enrichment_batcher_stage1_loop.py`: rubric mismatch aborts; **and** a regression test asserting `_profile_render_hash` still returns `load_profile(path).canonical_hash` with no recompute |

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
| 18 | **Typed env surface.** New and changed keys, each with a typed parse path in its own service `config.py` and a round-trip test. Pre-filter: `BISHOP_PREFILTER_BATCH_SIZE` (unchanged, 50), `BISHOP_PREFILTER_MIN_BATCH_SIZE` (**new**, 25), `BISHOP_PREFILTER_MAX_HOLD_MINUTES` (**new**, 120). Enrichment, **stage 1 and stage 2 tracked separately**: `BISHOP_ENRICHMENT_STAGE1_BATCH_SIZE` (10 → **50**), `BISHOP_ENRICHMENT_STAGE1_MIN_BATCH_SIZE` (**new**, 10), `BISHOP_ENRICHMENT_STAGE1_MAX_HOLD_MINUTES` (**new**, 120), and the identical STAGE2 triad. No `getattr`-papered defaults; every key parses through the typed path or the row is unsatisfied. **Amendment banner (v1.2.0, round 2):** at T9's original dispatch this row's default-value bump (10 → 50, both stages) could not land without also editing the pre-existing `tests/test_enrichment_batcher_config.py`, which pins the old default of 10 in `test_enrichment_stage1_batch_size_default` and `test_enrichment_stage2_batch_size_default` — a file that was not in T9's declared Files to touch. Verification and authorship both move to **you (T9-bis)**, which adds that test file to its own Files to touch and updates both assertions 10 → 50 alongside the config-default change. See plan §7 round 2. | **T9-bis** | `pytest-enforced` | Per-key: default value, env override, and invalid-value handling. Plus a hold-deadline test (row 19). **Amendment round 2:** `tests/test_enrichment_batcher_config.py::test_enrichment_stage1_batch_size_default` and `::test_enrichment_stage2_batch_size_default` are updated in the same subtask to assert `50`, not `10`; the env-override tests (`_env_override`) are unaffected since they already set an explicit value. |
| 19 | **No starvation.** Minimum-volume hold is bounded: a gate submits below `MIN_BATCH_SIZE` once `MAX_HOLD_MINUTES` has elapsed since that gate's last submit. The hold clock is per-gate and in-process; it resets on service restart, and that is accepted and documented. | **T9-bis** | `pytest-enforced` | Time-injected test: entries below min are held, then submitted after the deadline passes. **And** a negative test: a hash abort must not extend the hold indefinitely. |

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

**`.dev/decision-logs/prompt-caching/T<n>-<slug>.md`** — required for every `architectural` subtask (T2, T3, T4, T6, T7, T9-bis). This path is a contract anchor; drift between `decision-logs/` and `decisions/` is a violation, not cleanup.

**Amendment round 2 (v1.2.0):** T9 never reached a commit before its HALT (no code written, nothing staged), so no `T9-*.md` decision log was ever written. **You (T9-bis)** are the architectural subtask that actually lands this surface; your decision log is `.dev/decision-logs/prompt-caching/T9-bis-batch-amortization.md`, following the same `T<n>-<slug>` pattern with `T9-bis` as `<n>`.

### CHANGELOG convention

`CHANGELOG.MD` is a Files-to-touch entry on **every** subtask in this plan, not only T10. Each subtask appends its own bullet in its own commit.

## 3. Your subtask

### T9-bis — Continuation of T9: batch amortization, minimum volume and maximum hold (amendment round 2, v1.2.0)

| Field | Content |
|---|---|
| **ID** | `T9-bis` |
| **Scope** | Execute T9's original scope from a clean slate — T9 left no working-tree state to consume, unlike T1-bis. Make batches big enough to be worth a cache write: raise the enrichment batch-size defaults, and add a per-gate minimum-volume threshold with a bounded maximum hold so entries never starve. Stage 1 and stage 2 are configured and timed independently. Additionally update the one pre-existing test file the default bump requires touching. |
| **Files to touch** | `services/pre-filter-worker/app/config.py`, `services/pre-filter-worker/app/loop.py`, `services/enrichment-batcher/app/config.py`, `services/enrichment-batcher/app/stage1_loop.py`, `services/enrichment-batcher/app/stage2_loop.py`, `tests/test_prefilter_loop.py`, `tests/test_enrichment_batcher_stage1_loop.py`, `tests/test_enrichment_batcher_stage2_loop.py`, **`tests/test_enrichment_batcher_config.py`** (amendment round 2 addition — update `test_enrichment_stage1_batch_size_default` and `test_enrichment_stage2_batch_size_default` from `== 10` to `== 50`; the two `_env_override` tests and the three other tests in this file are untouched), `CHANGELOG.MD`, `.dev/decision-logs/prompt-caching/T9-bis-batch-amortization.md` |
| **Contract bindings** | Rows 18, 19, 21, 22. Owner of rows 18, 19. |
| **Inputs** | T1-bis (ordering only — you import no T1-bis symbol directly; T1-bis must simply be committed first, which it already is) |
| **Outputs** | Nine env keys through typed parse paths (three per gate, stage 1 and stage 2 separate); hold-deadline logic per gate; raised stage-1/stage-2 defaults 10 → 50; the two pinned assertions in `tests/test_enrichment_batcher_config.py` updated 10 → 50 in the same commit; tests including the starvation and abort-interaction cases; decision log recording the in-process clock choice, its restart behaviour, and the HALT/fork-1 resolution |
| **Kill criteria** | **(runtime-invariant)** HALT if an entry can be held indefinitely — the maximum-hold deadline must be reachable on every path, including when inflow is permanently below the minimum. **(runtime-invariant)** HALT if a hash abort (T5/T6/T7) can prevent the hold clock from ever advancing, which would convert one bad hash into permanent starvation (§5.4 C9). HALT if raising stage-1 batch size to 50 requires touching `content_truncation.py` (row 20 frozen) or changes any Anthropic per-request limit assumption. HALT if a `getattr`-papered default is used instead of the typed parse path (row 18). **(amendment round 2 — mechanical post-check)** After updating the config defaults and the test file, run `pytest tests/test_enrichment_batcher_config.py` and paste passed/failed counts; all six tests in that file must pass. Do **not** weaken either updated assertion to anything other than a point-literal `== 50`, and do not touch `test_enrichment_stage1_batch_size_env_override`, `test_enrichment_stage2_batch_size_env_override`, `test_enrichment_poll_interval_default`, `test_enrichment_poll_interval_env_override`, or `test_state_worker_url_default` — those five are unrelated to this amendment and any diff touching them is out of scope. HALT (open a **new** §7 row, not a silent fix here) rather than editing any other pre-existing test file if a similar pinned-default conflict surfaces elsewhere in this subtask's scope. |
| **Log tier** | `architectural` — introduces a new class of failure (deliberate withholding of work) into three loops that previously always submitted what they claimed |
| **Model class** | `architectural` |
| **Risks & mitigations** | The in-process clock resets on restart, so a restart loop could keep batches small; documented rather than solved, because a persisted clock would mean a state-worker schema change that D8 excludes. Larger batches widen the blast radius of one bad prefix — G1 verifies on a real batch before backfill is considered. **Amendment-specific risk:** widening Files to touch by one test file is a narrow, mechanical fix (two point-literal edits); the risk is scope creep into the file's other four tests, fenced by the kill criterion above naming exactly which two assertions change and which five must not. |

## 4. Load-bearing assumptions that name this subtask

**A8** · `invariant`
```
(The spec's Phase 1.5 "no code change" language stays uncorrected and executors will not halt on it | §2 row 23 deferred + D6 | an executor reads bishop_spec_0_6.md §12.3 as authority and halts, or hedges its implementation to match a document the operator has chosen not to fix | all subtasks)
```
Mitigated structurally: every packet carries an explicit line marking the spec informational and known-stale on caching.

## 5. Hidden couplings that name this subtask

**C9** · **confirmed** — *found by the packet-only lens; not in the context map*
```
(minimum-volume hold interacts with hash-or-abort | T9-bis's per-gate hold clock in the three loops vs T5/T6/T7's abort-before-submit paths | a hash mismatch aborts the cycle before submit, so if the hold clock only advances on a successful submit, one bad hash converts a temporary abort into permanent starvation: entries accumulate, the deadline never fires, and the gate looks merely idle | T5,T6,T7,T9-bis)
```
**Amendment round 2:** relabeled `T9` → `T9-bis` (T9 HALTed and never landed the hold-clock logic this tuple describes). **Bound** — your kill criterion requires the maximum-hold deadline to be reachable on every path including the abort path, with an explicit negative test.

**C10** · **suspected**
```
(larger batches widen single-prefix blast radius | services/enrichment-batcher/app/config.py stage1/stage2 defaults 10 -> 50 | one malformed cached prefix now spoils 50 entries per batch instead of 10, and Anthropic batch results are all-or-nothing per request but the wasted spend scales with batch size | T9-bis)
```
**Amendment round 2:** relabeled `T9` → `T9-bis` — same reason as C9. **What would disprove it:** G1 confirming a healthy prefix on a real batch before any backfill tranche. Not bound as a kill criterion because the exposure is cost, not correctness, and G7 enablement is explicitly a non-goal of this plan.

## 6. Coordination

You run independently of any declared parallel group — your only hard predecessor is T1-bis, already committed, and you have no hard dependency on T2, T3, T4, or T8 (rank 1, already complete) or on T5, T6, T7 (rank 2, not yet dispatched). The runner may dispatch you before, interleaved with, or after rank 2. CHANGELOG.MD is shared; append your own bullet in your own commit. You are changing WHEN each gate submits; T5, T6 and T7 are concurrently changing WHAT each gate submits, in the same three loop files (`services/pre-filter-worker/app/loop.py`, `services/enrichment-batcher/app/stage1_loop.py`, `services/enrichment-batcher/app/stage2_loop.py`). Do not change payload shape, do not touch cache_control, and do not touch the rubric or profile hash paths. Your minimum-volume hold interacts with their abort-before-submit paths — coupling C9 above is the specific hazard. **Amendment round 2 note:** this coordination note is relabeled from T9 to you — T9 itself never landed any code, so the submit-path coordination hazard was never actually exercised until now.

## 7. Resolved inputs

From T1-bis (committed, per `runs/ledger.md` at commit `8d9af01`): nothing you import directly — your dependency on T1-bis is ordering only. Current-state facts you may rely on: `services/pre-filter-worker/app/config.py` defines `PREFILTER_BATCH_SIZE` default 50 via `BISHOP_PREFILTER_BATCH_SIZE`; `services/enrichment-batcher/app/config.py` defines `ENRICHMENT_STAGE1_BATCH_SIZE` and `ENRICHMENT_STAGE2_BATCH_SIZE`, both default 10 (to become 50). The enrichment-batcher runs `stage1_cycle` and `stage2_cycle` concurrently under `asyncio.gather`, so your two enrichment hold clocks must be independent per gate. The pre-filter loop polls `GET /manifest/poll?state=DISCOVERED&limit=<batch size>`; the enrichment loops poll `GET /entries/poll?state=SCRAPED` and `state=ENRICHMENT_STAGE2_QUEUED`. Strategy reference: `.dev/caching_strategy.md` R3 / section 13c.3 suggests considering 50 for the enrichment stages during backfill. **Amendment round 2 addition:** `tests/test_enrichment_batcher_config.py` (repo-root `tests/`) currently contains six tests against `services/enrichment-batcher/app/config.py`, loaded via `importlib.util.spec_from_file_location` (not a package import) — `test_enrichment_stage1_batch_size_default` (line ~26, asserts `== 10`, to become `== 50`), `test_enrichment_stage1_batch_size_env_override` (asserts `== 5` under an explicit env override — untouched), `test_enrichment_stage2_batch_size_default` (asserts `== 10`, to become `== 50`), `test_enrichment_stage2_batch_size_env_override` (asserts `== 7` under an explicit env override — untouched), `test_enrichment_poll_interval_default`, `test_enrichment_poll_interval_env_override`, and `test_state_worker_url_default` (all three untouched, unrelated to batch size). Full HALT context: `.dev/plans/prompt-caching/runs/T9-brief.md`.
