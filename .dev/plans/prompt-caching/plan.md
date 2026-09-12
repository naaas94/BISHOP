# Plan — prompt-caching

**Version:** 1.0.0
**run_status:** `complete`
**audit_status:** `not_run`
**Mode:** Standard (non-charter; caching is not an M8/M9 charter row)
**Baseline SHA:** `b919fdba09e07a77700d57cf3b360c001058bb84` (branch `dev`)
**Declared subtask budget:** 4–10 (orchestrator-planning §Budget). This plan declares **10 executable subtasks + 1 gate node** — at the ceiling, no split proposal required.
**Skill version:** orchestrator-planning v1.2

---

## 0. Context map intake

- **Path consumed:** `.dev/plans/prompt-caching/context-map.md`
- **Readiness verdict:** CONDITIONAL
- **Skill version + SHA the map was generated against:** pre-plan-exploration v0.6 @ `b919fdba09e07a77700d57cf3b360c001058bb84`
- **Staleness check:** HEAD == map SHA (`b919fdb`). **Zero committed drift.** Divergence is dirty-working-tree only; the in-scope dirty paths are enumerated in D9 below.
- **Scope-area labels flagged in §Ambiguity flags:** prefix authoring, pins, pre-filter prefix, hash-or-abort, Call 2 prefix, enrichment pin, stage1, `scripts/profile_hash.py`, spec, charter drift, observability, enrichment config, all packets.

### 0.1 Binding-artifact resolvability

| Artifact | Tracked at planning time? | Disposition |
|---|---|---|
| `.dev/plans/prompt-caching/context-map.md` | **No** (`?? .dev/plans/prompt-caching/`) | **D1** — operator elected *commit*. The map, this plan, `dag.json`, and all packets are committed together before the first dispatch. Until that commit exists, this plan is not dispatchable regardless of `run_status`. |
| `.dev/caching_strategy.md` | Yes | Binding for rejected-alternatives and the 4,096 floor. |
| `.dev/llm-models-and-cache.md` | Yes | Informational (as-built, stale on profile size; T10 refreshes). |
| `bishop_spec_0_6.md` | Yes (dirty) | **Informational for this plan, not binding** — see D6. |
| `.dev/decision-logs/ops/soft-launch-precision-overlay.md` | **No** (untracked) | **D2** — downgraded to *informational*. No §2 row rests on its bindingness. Its factual content (pin is ad hoc, revert target is `v1.2.0`) is restated directly in D3 so the plan does not depend on an unreadable artifact. |
| `config/profiles/professional_v1.2.0_soft_launch.yaml` | **No** (untracked) | **D3** — T1 commits it. See below. |

### 0.2 Numbered dispositions

Every map instruction — numbered flag or prose handoff note — carries a disposition. Flags 1–7 were resolved by operator decision in the planning session; Flag 8 is resolved by a §2 vocabulary row.

| # | Map item | Class | Disposition |
|---|---|---|---|
| **D1** | Context map untracked | binding-artifact | **resolved** — commit `.dev/plans/prompt-caching/` (map + plan + dag + packets) before first dispatch. |
| **D2** | Overlay decision log untracked | binding-artifact | **resolved** — downgraded to informational; content restated in D3. |
| **D3** | **Flag 1** — which file is cache key A? | ownership | **resolved** — the live pin `config/profiles/professional_v1.2.0_soft_launch.yaml` **stays** the pre-filter pin and **T1 commits it to git**. Rationale: it matches the running stack and the host-mounted copy byte-for-byte (both SHA-256 `1FD10EA6…04A7`, verified at planning time), so authoring against it changes no live behavior. The overlay's "revert to v1.2.0 next week" intent becomes a **known re-plan trigger**, recorded in §5.2 A6, not a reason to author against a pin the stack does not serve. |
| **D4** | **Flag 2** — where do the extra pre-filter tokens live? | ownership | **resolved** — a new annex `config/prompts/prefilter_rubric_v1.md`, content = **source-shape law** (paper / repo / model card / article / hub dump), per operator intent and strategy §16. **Not** YAML growth. Owner T2. |
| **D5** | **Flag 3** — Call 2 prefix shape | coexisting_model_versions | **resolved** — new annex `config/prompts/call2_rubric_v1.md` (eval schema + relevance-scoring few-shots). **Enrichment pin stays `professional_v1.0.0.yaml`.** No pin bump, so no un-evaluated gate-2 quality shift. Owner T4. |
| **D6** | **Flag 5** — does this plan edit `bishop_spec_0_6.md` §12.1/§12.3? | implicit contract | **deferred (operator decision: no)** — the spec keeps saying Phase 1.5 needs "no code change". This plan does **not** edit it. Consequence bound as a §2 `deferred` row (row 19) with follow-up **`FU-CACHE-SPEC-01`**, owner = operator, outside this plan. Every packet carries an explicit line telling the executor the spec is *informational and known-stale on this point*, so no executor HALTs on the contradiction. |
| **D7** | **Flag 4** — hash-or-abort for rubric assets | ownership | **resolved** — per-asset hash in the rubric file's own YAML front-matter, verified by a new shared `verify_rubric_hash`. Profile `canonical_hash` semantics are **untouched**; no composite, no fold. Call 1 gains a hash-or-abort path it does not have today. Owner T1 (contract), T6 (Call 1 path). |
| **D8** | **Flag 6** — poller cache usage | ownership | **resolved** — **logs only** (strategy §15 minimum) + zero-cache-read warning. No `BatchRecord` columns, no Alembic, no state-worker writer change. This *disproves* map Surface 12 by the map's own stated condition: no `domain.py` / `http.py` / `transitions.py` / `alembic/**` path appears in any subtask's Files to touch. Owner T8. |
| **D9** | **Flag 7** — batch size / amortization | missing_test_coverage (ops) | **resolved, expanded** — **in scope**, and the operator additionally asked for batch *scheduling* / minimum-volume thresholds, treating stage 1 and stage 2 separately, to maximize cache reuse. This is T9 and carries its own starvation risk (§5.4 C9). |
| **D10** | **Flag 8** — vocabulary collision (`prefix` / `4k` / `hash` / `system`) | vocabulary_collision | **resolved** — §2 row 20 is a binding glossary, copied verbatim into every packet. |
| **D11** | Operator discussion notes (source-shape law, no padding, three keys separate, Call 1 needs its own rubric, Call 2 must not inherit the gate-1 overlay) | prose handoff | **resolved** — absorbed as D4/D5/D7 and §2 rows 4–6. The "Call 2 must not silently inherit gate-1" instruction is what surfaces §5.4 **C4**, which this plan treats as a code defect to fix, not just a content preference. |
| **D12** | Measured token table (`cl100k_base`, 2026-09-11) | prose handoff | **resolved, re-measured at planning time** — every number reproduced exactly: v1.0.0=383, v1.1.0=1324, v1.1.1=1444, v1.2.0=1882, soft_launch=2280, Call 1 system=267, Call 2 post-breakpoint=82. Gaps to the 4,096 floor: key A 1816, key B 3829, key C 3631. Labeled `derived` in §5.2 A6. |
| **D13** | Dirty in-scope paths | prose handoff | **resolved** — in-scope dirty paths at planning time: `bishop_shared/profile_renderer.py` (M), `tests/test_profile_renderer.py` (M), `bishop_spec_0_6.md` (M), `services/batch-poller/app/models.py` (M, parked field only), `config/profiles/professional_v1.2.0_soft_launch.yaml` (??). T1 and T8 edit files that are already dirty; each names this in its packet so the executor does not mistake pre-existing overlay changes for its own. **Checklist row** in §Validation: §8.1 verification must run on a clean worktree, so the closure run cannot rest on these local edits. |
| **D14** | Kill-criterion candidates from exclusions | prose handoff | **resolved** — §2 row 18 (frozen paths) + T10's declared-scope sweep. |
| **D15** | "New files the map cannot list" | prose handoff | **resolved** — `config/prompts/prefilter_rubric_v1.md` (T2), `config/prompts/call1_rubric_v1.md` (T3), `config/prompts/call2_rubric_v1.md` (T4) are in Files to touch. Map correctly predicted the annex names; D4/D5 adopt them. |
| **D16** | **G7 / wet-run**: map says "compose is down; wet-run is not in this exploration" | prose handoff | **resolved and corrected** — **the map is wrong on this point.** Compose was verified **up** at planning time (nine containers, 17 min uptime, `state-worker` healthy). This changes the plan materially: a live gate is available, so §3 carries gate node **G1** rather than deferring live verification. Recorded as a map-vs-reality divergence, not a silent fix. |
| **D17** | Operator gates to re-surface | prose handoff | **none signed** — the map states no gate is signed and the overlay log remains "ad hoc / not the intended machine". No dual-greenlight or sign-off text to copy. G1 is a plan-introduced gate, not a charter one. |

### 0.3 Planning-time discovery not in the map

Two facts were established at planning time that the map did not have. Both changed contracts, so they are recorded here rather than absorbed silently.

- **P1 — profile deployment is a host bind mount, not the repo.** `docker-compose.yml:52,84` mount `${BISHOP_DATA_ROOT}/profiles → /app/config/profiles` on `pre-filter-worker` and `enrichment-batcher`, which **masks** the image-baked `config/profiles` from each Dockerfile's `COPY config/profiles ./config/profiles`. The host dir `C:/Users/Ale/bishop_data/profiles` holds exactly the two pinned files, hand-placed; no script in the repo populates it. The map's Surface 11 predicted a container-vs-repo path hazard but got the mechanism wrong (it assumed repo-relative test paths, not a data-root mount). Consequence: **§2 row 15 forbids a bind mount for `config/prompts`** — rubric assets are image-baked only, because mounting an empty host dir over baked assets is a silent total-failure mode for all three gates.
- **P2 — SDK `ttl` support is real but the pin floor is not.** `anthropic` 0.100.0 is installed and `CacheControlEphemeralParam` carries `ttl: Literal["5m","1h"]` on the **GA** param type (no beta header required). But all three service `requirements.txt` files pin `anthropic>=0.40`, a floor low enough to resolve an SDK that rejects `ttl`. §2 row 1a raises the floor and pins it with a test.

**No BLOCKED flag.** Planning proceeded under CONDITIONAL with every pre-execution decision written above.

---

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

---

## 2. Shared contracts

Binding on every subagent. Enforcement mode is one token per row; rows whose verification would mix modes are split.

### Types / interfaces

| # | Contract | Owner | Binding site | Enforcement | Falsifier |
|---|---|---|---|---|---|
| 1 | **New** `bishop_shared/prompt_cache.py`: `HAIKU_CACHE_MIN_TOKENS: Final[int] = 4096`; `CACHE_TTL: Final[str] = "1h"`; `cached_system_blocks(*texts: str) -> list[dict[str, object]]` | T1 | `module-function` (+ two module constants) | `pytest-enforced` | `tests/test_prompt_cache.py`: (a) N inputs → N blocks; (b) `cache_control` present on **last** block only; (c) equals `{"type": "ephemeral", "ttl": "1h"}` exactly; (d) two calls return **equal but not identical** dicts (no aliasing across requests); (e) empty input raises `ValueError` |
| 1a | `anthropic` pin floor raised `>=0.40` → `>=0.100` in all three service `requirements.txt` **and** `pyproject.toml` dev extra | T1 | `parser-key` (requirements line) | `pytest-enforced` | `tests/test_prompt_cache.py::test_sdk_supports_1h_ttl` asserts `"ttl" in anthropic.types.cache_control_ephemeral_param.CacheControlEphemeralParam.__annotations__`. Falsifies P2 directly. |
| 2 | **New** `bishop_shared/rubric_assets.py`: `PROMPTS_CONTAINER_DIR = Path("/app/config/prompts")`; `RubricId = Literal["prefilter_rubric", "call1_rubric", "call2_rubric"]`; `_RUBRIC_FILENAME: dict[RubricId, str]`; `RubricDocument` (pydantic: `rubric_id: str`, `version: str`, `canonical_hash: str`, `body: str`); `resolve_rubric_path(rubric_id: RubricId) -> Path`; `load_rubric(path: Path) -> RubricDocument`; `compute_rubric_hash(rubric: Path \| str) -> str`; `verify_rubric_hash(rubric_id: RubricId, *, rubric_path: Path \| None = None) -> tuple[str, str, str] \| None` | T1 | `module-function` ×5, `pydantic-model` ×1, `dataclass-field` n/a | `pytest-enforced` | `tests/test_rubric_assets.py`: front-matter parse; `resolve_rubric_path` for all three IDs; stamp→verify round trip; mismatch returns `None`; unknown `rubric_id` raises `ValueError` |
| 3 | `render_profile_prompt(profile: ProfileDocument, *, include_output: bool = True) -> str` — new keyword-only param. Default `True` preserves current byte-for-byte output. | T1 | `module-function` (signature extension) | `pytest-enforced` | `tests/test_profile_renderer.py`: (a) default render of `professional_v1.2.0_soft_launch.yaml` is **byte-identical** to the pre-change render (pin the current 10,799-char / 2,280-token render); (b) `include_output=False` omits the `## Output format` section and nothing else |
| 4 | `AnthropicBatchResultItem` gains `input_tokens: int \| None = None`, `output_tokens: int \| None = None`, `cache_creation_input_tokens: int \| None = None`, `cache_read_input_tokens: int \| None = None` | T8 | `pydantic-model` fields | `pytest-enforced` | `tests/test_batch_poller_anthropic_client.py`: construction round-trip with and without `usage`; extraction from a fixture whose `message.usage` carries all four |
| 5 | `build_requests` / `build_stage2_requests` accept the system prefix as `list[dict[str, object]]`; `params["system"]` is a block list on **all three** gates. Pre-filter: `build_requests(*, system_blocks: list[dict[str, object]], entries: list[PreFilterBatchEntry])` — the `system_prompt: str` parameter is **retired**. Enrichment Call 1: `build_requests(*, entries: list[Stage1BatchEntry])` signature unchanged; blocks are assembled inside. Call 2: `build_stage2_requests(*, profile_prompt: str, rubric_body: str, entries: list[Stage2BatchEntry])`. | T5 / T6 / T7 | `instance-method` ×3 | `pytest-enforced` | Per-gate payload tests asserting `isinstance(params["system"], list)` and the retired `system_prompt` kwarg raising `TypeError` |

### Naming

| # | Contract | Owner | Enforcement | Falsifier |
|---|---|---|---|---|
| 6 | New assets: `config/prompts/prefilter_rubric_v1.md` (T2), `config/prompts/call1_rubric_v1.md` (T3), `config/prompts/call2_rubric_v1.md` (T4). New script `scripts/rubric_hash.py` (T1). New modules `bishop_shared/prompt_cache.py`, `bishop_shared/rubric_assets.py` (T1). | T1–T4 | `docs-structural` | Path-existence assertions in each owner's test. **Semantic falsifier** (structural presence proves nothing about content): row 8's token-floor gate plus row 7's hash round-trip. |
| 7 | Rubric front-matter schema, exactly: `---\nrubric_id: <RubricId>\nversion: "<semver>"\ncanonical_hash: "<64-hex>"\n---\n<body>`. `compute_rubric_hash` hashes **body only**, LF-normalized (`\r\n` → `\n`), excluding front matter. | T1 | `parser-key` | `pytest-enforced` | `tests/test_rubric_assets.py`: CRLF body and LF body yield the **same** hash; a front-matter `version` edit does **not** change the hash; a one-character body edit **does** |

### Cache-shape contracts

| # | Contract | Owner | Enforcement | Falsifier |
|---|---|---|---|---|
| 8 | **Token floor.** Total measured system-prefix tokens per cache key ≥ **4,506** (`cl100k_base`) = 4,096 × 1.10. The 10% margin exists because `cl100k_base` is a proxy for Anthropic's tokenizer, not the tokenizer itself. Measured on the **total prefix**, not the annex, so the contract cannot go stale when a profile render changes. | T10 (gate); T2/T3/T4 size their annexes to meet it | `pytest-enforced` | **New** `tests/test_prompt_cache_token_floor.py`: one point-literal assertion per key (A, B, C) that the assembled prefix ≥ 4506, printing the measured margin. **Named semantic gap:** a proxy tokenizer cannot prove Anthropic cached anything — the live falsifier is G1's `cache_creation_input_tokens > 0`. |
| 9 | **Single emitter.** No `cache_control` dict literal may appear anywhere outside `bishop_shared/prompt_cache.py`. All three gates obtain blocks from `cached_system_blocks`. | T1 | `pytest-enforced` | `tests/test_prompt_cache.py::test_no_inline_cache_control_literals` — tree grep over `bishop_shared/**` and `services/**` excluding `prompt_cache.py`; asserts zero hits. This is the mechanical guard for §5.4 C1. |
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
| 16 | **Rubric assets are image-baked, never bind-mounted.** `services/pre-filter-worker/Dockerfile` and `services/enrichment-batcher/Dockerfile` gain `COPY config/prompts ./config/prompts`. `docker-compose.yml` **must not** contain any mount whose target is `/app/config/prompts`. Rationale (P1): the profiles mount already masks image-baked files with a hand-populated host dir; an empty-dir mount over baked rubrics would make all three gates abort with no repo-visible cause. Consequence accepted: a rubric change requires an image rebuild, which correctly couples the asset and its stamped hash to one artifact. | T1; verified T10 | `pytest-enforced` | `tests/test_prompt_cache.py::test_no_prompts_bind_mount` parses `docker-compose.yml` and asserts no mount targets `/app/config/prompts`. T1 additionally creates `config/prompts/` at its own commit so the new `COPY` cannot break the build in the window before T2–T4 land. |
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

**`.dev/decision-logs/prompt-caching/T<n>-<slug>.md`** — required for every `architectural` subtask (T1, T2, T3, T4, T6, T7, T9). This path is a contract anchor; drift between `decision-logs/` and `decisions/` is a violation, not cleanup.

### CHANGELOG convention

`CHANGELOG.MD` is a Files-to-touch entry on **every** subtask in this plan, not only T10. Each subtask appends its own bullet in its own commit.

---

## 3. Dependency DAG

```mermaid
graph TD
    T1[T1 shared cache + rubric contract] --> T2[T2 author prefilter rubric]
    T1 --> T3[T3 author call1 rubric]
    T1 --> T4[T4 author call2 rubric]
    T1 --> T8[T8 poller cache usage]
    T1 --> T9[T9 batch amortization]
    T2 --> T5[T5 pre-filter wiring]
    T3 --> T6[T6 Call 1 wiring]
    T4 --> T7[T7 Call 2 wiring]
    T5 --> T10[T10 closeout + token gate + sweep]
    T6 --> T10
    T7 --> T10
    T8 --> T10
    T9 --> T10
    T10 --> G1{{G1 operator live cache gate}}
```

**Parallel groups.**

- **`{T2, T3, T4, T8, T9}`** — rank 1, all depend only on T1. **Throughput-only.** No HALT-isolation claim is made: a single operator executing serially never exercises concurrency, so claiming isolation here would be unfalsifiable.
- **`{T5, T6, T7}`** — rank 2. **Throughput-only.**

**Soft dependencies (coordination notes, never ordering constraints).** Declared as `soft_edges` in `dag.json`, not encoded in mermaid edge styling.

- `T2 ~ T3 ~ T4` — shared surface: `config/prompts/` directory conventions and the front-matter schema. Each packet states, with the same strength and in its own §4 block, that the front-matter schema is row 7's literal and may not be locally varied.
- `T5 ~ T6 ~ T7` — shared surface: `bishop_shared/prompt_cache.py::cached_system_blocks`. Each packet carries the identical instruction, in its own §4 block, that no gate may inline a `cache_control` literal (row 9).
- `T9 ~ T5,T6,T7` — shared surface: the submit path in each loop. T9 changes *when* a submit happens; T5/T6/T7 change *what* is submitted.

**Commit-order guards.**

1. **Prose-coupled group `{T2, T3, T4}`** — all three append `CHANGELOG.MD` and all three create files under `config/prompts/`. Commit order is ascending `Tn`; whichever lands second or third reconciles the shared CHANGELOG section as part of its own definition of done. Parallel execution otherwise permits a CHANGELOG describing annexes that do not exist yet, and no test observes that.
2. **Prose-coupled group `{T5, T6, T7}`** — same rule for `CHANGELOG.MD`, ascending `Tn`.
3. **Cross-subtask import guard.** T5, T6, T7, T8 and T9 all import symbols owned by T1 (`prompt_cache`, `rubric_assets`, the extended `render_profile_prompt`). None of them may land, and §8.1 may not freeze closure, while T1 remains uncommitted — even if the whole suite passes in a dirty in-tree run. This is listed as an explicit risk in §5.3.

**Gate node.**

- **`G1`** — `kind: gate`, owns **no packet**, is **never dispatched**. **Condition:** after T10, the operator rebuilds `pre-filter-worker` and `enrichment-batcher` images, restarts compose, and lets each gate submit **two** batches on the same cache key. G1 passes when the poller's completion log line for the second batch of at least one key reports `cache_read_tokens > 0`; it fails if all keys report `cache_read_zero` across two consecutive batches. A failure is a §7 amendment trigger, not a waiver. An explicit operator budget waiver ("accept full input price for now") is the only alternative close, and it must be recorded against this condition by name.

---

## 4. Subtask specs

### T1 — Shared cache-block and rubric-asset contract

| Field | Content |
|---|---|
| **ID** | `T1` |
| **Scope** | Introduce the two shared modules every other subtask depends on (`prompt_cache`, `rubric_assets`), the stamping script, the `render_profile_prompt` signature extension, the Dockerfile bake, the SDK pin bump, and commit the untracked live pre-filter profile so the whole plan rests on a tracked asset. |
| **Files to touch** | `bishop_shared/prompt_cache.py` (new), `bishop_shared/rubric_assets.py` (new), `bishop_shared/profile_renderer.py` (**already dirty** — overlay pin edits present; do not revert them), `scripts/rubric_hash.py` (new), `config/prompts/` (new dir + `README.md` stub so the new `COPY` cannot break the build before T2–T4 land), `config/profiles/professional_v1.2.0_soft_launch.yaml` (**untracked → `git add`**, content unchanged), `services/pre-filter-worker/Dockerfile`, `services/enrichment-batcher/Dockerfile`, `services/pre-filter-worker/requirements.txt`, `services/enrichment-batcher/requirements.txt`, `services/batch-poller/requirements.txt`, `pyproject.toml`, `tests/test_prompt_cache.py` (new), `tests/test_rubric_assets.py` (new), `tests/test_profile_renderer.py` (**already dirty**), `CHANGELOG.MD`, `.dev/decision-logs/prompt-caching/T1-cache-and-rubric-contract.md` |
| **Contract bindings** | Rows 1, 1a, 2, 3, 6, 7, 9, 16, 21, 22. Owner of rows 1, 1a, 2, 3, 7, 9, 16. |
| **Inputs** | None |
| **Outputs** | Two shared modules; `scripts/rubric_hash.py` with frozen CLI `python scripts/rubric_hash.py <path> [--render]`; `config/prompts/` created; tracked soft-launch profile; two Dockerfiles baking `config/prompts`; SDK floor at `>=0.100`; three new/extended test modules; decision log |
| **Kill criteria** | **(runtime-invariant)** HALT if `cached_system_blocks` cannot place `cache_control` on the last block without mutating a module-level dict shared across requests. **(executor-preflight)** HALT if `anthropic>=0.100` cannot be satisfied in this environment. **(mechanical post-check)** After adding `COPY config/prompts`, run `docker build -f services/pre-filter-worker/Dockerfile .` and **paste the exit code** — asserting the build works is not evidence it does. **(mechanical post-check)** After `git add config/profiles/professional_v1.2.0_soft_launch.yaml`, run `git ls-files config/profiles/professional_v1.2.0_soft_launch.yaml` and paste the output; empty output means the tracking claim is false. **(runtime-invariant)** HALT if extending `render_profile_prompt` changes the default render by even one byte. HALT if any change would touch a row-20 frozen path. |
| **Log tier** | `architectural` |
| **Model class** | `architectural` — every downstream subtask's contract surface originates here; a wrong breakpoint helper propagates to all three gates |
| **Risks & mitigations** | The `cache_control` dict is the single most-copied literal in the plan; row 9's grep test is the structural guard. CRLF line endings on this Windows checkout could destabilise the rubric body hash — row 7's LF normalisation plus a CRLF-vs-LF equality test. `render_profile_prompt` is consumed by pre-filter, stage2, and `scripts/profile_hash.py`; the keyword-only default-`True` param is chosen precisely so no existing call site changes. |

### T2 — Author `prefilter_rubric_v1.md` (cache key A)

| Field | Content |
|---|---|
| **ID** | `T2` |
| **Scope** | Author the pre-filter rubric annex as **source-shape law** — how to judge relevance differently for a paper vs a repo vs a model card vs an article vs a hub dump — and stamp its hash. |
| **Files to touch** | `config/prompts/prefilter_rubric_v1.md` (new), `tests/test_rubric_assets.py` (extend), `CHANGELOG.MD`, `.dev/decision-logs/prompt-caching/T2-prefilter-rubric.md` |
| **Contract bindings** | Rows 6, 7, 8, 21, 22. Sizes its annex so key A's **total** prefix ≥ 4,506. |
| **Inputs** | T1 (`rubric_assets`, `scripts/rubric_hash.py`) |
| **Outputs** | Stamped annex; measured token report for key A (annex tokens, total prefix tokens, margin over 4,506); decision log recording why each source shape earned its space |
| **Kill criteria** | HALT rather than pad — no filler, whitespace, or lorem to reach the floor (strategy §17). If genuine source-shape content cannot reach the floor, HALT and report the shortfall. **(mechanical post-check)** Run `python scripts/rubric_hash.py config/prompts/prefilter_rubric_v1.md` and paste its output; then re-run and paste the "already current" line. HALT if the annex contradicts the live profile's exclusions or peripheral-tier disposition rather than extending them. HALT if the annex names a specific source not in the M8 adapter set. |
| **Log tier** | `architectural` |
| **Model class** | `architectural` — quality-bearing gate-1 content whose only mechanical falsifier is a token count |
| **Risks & mitigations** | Measured gap is 1,816 tokens against the soft-launch render (the smallest of the three gaps), so this is the most achievable annex. The live pre-filter gate has a gold set (`eval/prefilter_v*`) that may be **read** for calibration but never modified (row 20). |

### T3 — Author `call1_rubric_v1.md` (cache key B)

| Field | Content |
|---|---|
| **ID** | `T3` |
| **Scope** | Author the Call 1 extraction rubric: per-`entry_type` extraction guidance, per-source content-shape notes, and worked examples for `summary` / `concepts` / `tags` / `entry_type` / `challenge_hooks`. Call 1 has no profile, so this annex carries almost the entire prefix. |
| **Files to touch** | `config/prompts/call1_rubric_v1.md` (new), `tests/test_rubric_assets.py` (extend), `CHANGELOG.MD`, `.dev/decision-logs/prompt-caching/T3-call1-rubric.md` |
| **Contract bindings** | Rows 6, 7, 8, 21, 22. Sizes its annex so key B's **total** prefix ≥ 4,506. Must not restate or edit `TAG_TAXONOMY_ORDERED`; the taxonomy is injected by `build_call1_system_prompt` and duplicating it into the annex would double the tokens and create a second copy to drift. |
| **Inputs** | T1 |
| **Outputs** | Stamped annex; measured token report for key B; **a manual spot-check artifact** at `.dev/plans/prompt-caching/artifacts/T3-call1-spotcheck.md` comparing Call 1 output fields for at least 5 real entries before and after the annex; decision log |
| **Kill criteria** | HALT rather than pad. **(mechanical post-check)** paste `scripts/rubric_hash.py` output as in T2. HALT if the annex would change the Appendix A JSON schema in `build_call1_system_prompt` — the annex adds guidance, never a second schema. HALT if the spot-check shows `challenge_hooks` degrading in specificity; spec §13.1 names it the most load-bearing field for Layer 2 retrieval and there is **no automated Call 1 eval gate** to catch this. |
| **Log tier** | `architectural` |
| **Model class** | `architectural` |
| **Risks & mitigations** | Largest gap of the three (3,829 tokens) and the weakest verification story — see §5.3, where this is named the highest re-plan risk. The spot-check artifact is the mitigation, and it is a required Output rather than a suggestion. |

### T4 — Author `call2_rubric_v1.md` (cache key C)

| Field | Content |
|---|---|
| **ID** | `T4` |
| **Scope** | Author the Call 2 relevance-scoring rubric: score-band definitions, pass/marginal/reject worked examples with scores, and `value_rationale` guidance. Must explicitly govern relevance **scoring** (0–1 float), not the gate-1 binary decision. |
| **Files to touch** | `config/prompts/call2_rubric_v1.md` (new), `tests/test_rubric_assets.py` (extend), `CHANGELOG.MD`, `.dev/decision-logs/prompt-caching/T4-call2-rubric.md` |
| **Contract bindings** | Rows 6, 7, 8, 21, 22. Sizes its annex so key C's **total** prefix ≥ 4,506, measured against the `include_output=False` profile render (row 3) that T7 will use — **not** against the current 383-token render. |
| **Inputs** | T1 |
| **Outputs** | Stamped annex; measured token report for key C stating which render variant it measured; decision log |
| **Kill criteria** | HALT rather than pad. **(mechanical post-check)** paste `scripts/rubric_hash.py` output. HALT if the annex reintroduces a `{"decision": 0 or 1}` output contract — that is the gate-1 contract this plan is removing from the Call 2 prefix (§5.4 C4). HALT if measuring against the wrong render variant, since the resulting margin would be wrong in the unsafe direction. |
| **Log tier** | `architectural` |
| **Model class** | `architectural` |
| **Risks & mitigations** | Enrichment pin stays `v1.0.0` (D5), so the profile contribution to key C is only ~330–383 tokens and the annex carries ~3,700. Depends on T1's `include_output` param for its measurement baseline — stated as a resolved input in the packet. |

### T5 — Pre-filter wiring (cache key A)

| Field | Content |
|---|---|
| **ID** | `T5` |
| **Scope** | Convert pre-filter `params.system` from a plain string to cached content blocks, and add rubric hash-or-abort to the pre-filter cycle. |
| **Files to touch** | `services/pre-filter-worker/app/anthropic_batch_client.py`, `services/pre-filter-worker/app/loop.py`, `tests/test_prefilter_anthropic_client.py`, `tests/test_prefilter_loop.py`, `CHANGELOG.MD` |
| **Contract bindings** | Rows 1, 2, 5, 8, 9, 10, 11, 12, 21, 22. |
| **Inputs** | T1 (`cached_system_blocks`, `verify_rubric_hash`), T2 (stamped `prefilter_rubric_v1.md`) |
| **Outputs** | Block-shaped pre-filter payload with `cache_control` + `ttl: "1h"` on the last block; rubric abort wired ahead of Anthropic with the existing CRITICAL alert; updated tests |
| **Kill criteria** | **(runtime-invariant)** HALT if any code path can still submit a plain-string `system`. HALT if the rubric abort lands *after* the Anthropic call rather than before it — the abort is worthless downstream of submit. HALT if `emit_profile_hash_mismatch_alert`'s existing profile behaviour changes. Must update `tests/test_prefilter_anthropic_client.py:73` (`assert requests[0]["params"]["system"] == "system text"`), which fails by construction. No inline `cache_control` literal (row 9). |
| **Log tier** | `standard` — applies T1's established pattern; no new design fork |
| **Model class** | `standard` |
| **Risks & mitigations** | `build_requests`' `system_prompt: str` kwarg is consumed by `submit_pre_filter_batch`, `submit_pre_filter_batch_or_fatal`, and two test modules; retiring it is a signature break that must cascade in one commit. |

### T6 — Enrichment Call 1 wiring (cache key B)

| Field | Content |
|---|---|
| **ID** | `T6` |
| **Scope** | Convert Call 1 `params.system` to cached content blocks including the Call 1 rubric, and give stage 1 a rubric hash-or-abort path it does not currently have — without altering `_profile_render_hash`. |
| **Files to touch** | `bishop_shared/enrichment_prompts.py`, `services/enrichment-batcher/app/anthropic_batch_client.py`, `services/enrichment-batcher/app/stage1_loop.py`, `tests/test_enrichment_prompts.py`, `tests/test_enrichment_batcher_stage1_loop.py`, `CHANGELOG.MD`, `.dev/decision-logs/prompt-caching/T6-call1-wiring.md` |
| **Contract bindings** | Rows 1, 2, 5, 8, 9, 10, 11, 12, 13, 21, 22. Owner of row 13. |
| **Inputs** | T1, T3 (stamped `call1_rubric_v1.md`) |
| **Outputs** | Block-shaped Call 1 payload; new stage-1 rubric abort (log-only, no CRITICAL); regression test pinning `_profile_render_hash` semantics; decision log |
| **Kill criteria** | **(runtime-invariant)** HALT if `_profile_render_hash` starts calling `compute_profile_hash` — that is a separate contract change the M5 T4 log explicitly left open, and doing it here silently widens scope. HALT if the abort path emits a CRITICAL alert (pre-filter's asymmetry must not be copied here — row 12). HALT if `build_call1_system_prompt`'s Appendix A schema text or injected taxonomy changes. `tests/test_enrichment_prompts.py::test_call1_includes_taxonomy` asserts `tag in prompt` against a **string**; if the builder's return type changes, that assertion silently passes or breaks in the wrong direction — it must be re-pointed at the specific block, not at the block list. |
| **Log tier** | `architectural` — introduces a failure mode (batch abort) in a path that previously could not abort |
| **Model class** | `architectural` |
| **Risks & mitigations** | Stage 1 and stage 2 run in the same service via `asyncio.gather`; a stage-1 abort must not take down stage 2's cycle. Covered by an explicit test. |

### T7 — Enrichment Call 2 wiring (cache key C)

| Field | Content |
|---|---|
| **ID** | `T7` |
| **Scope** | Move the Call 2 `cache_control` breakpoint from the first system block to the **last**, add `ttl: "1h"`, insert the Call 2 rubric, and stop caching the gate-1 output contract that the v1.0.0 profile render currently drags into the Call 2 prefix. |
| **Files to touch** | `bishop_shared/enrichment_prompts.py`, `services/enrichment-batcher/app/anthropic_batch_client.py`, `services/enrichment-batcher/app/stage2_loop.py`, `tests/test_enrichment_prompts.py`, `tests/test_enrichment_batcher_stage2_loop.py`, `CHANGELOG.MD`, `.dev/decision-logs/prompt-caching/T7-call2-breakpoint-move.md` |
| **Contract bindings** | Rows 1, 2, 3, 5, 8, 9, 10, 11, 12, 21, 22. |
| **Inputs** | T1 (`include_output` param), T4 (stamped `call2_rubric_v1.md`) |
| **Outputs** | Three-block Call 2 system with one `cache_control` on the last block; profile rendered with `include_output=False`; rubric abort (log-only); updated tests; decision log recording the breakpoint move **and** the output-contract removal as two distinct decisions |
| **Kill criteria** | **(runtime-invariant)** HALT if more than one block carries `cache_control`, or if it is not on the last block. HALT if the cached prefix contains a `{"decision": 0 or 1}` instruction — v1.0.0's `output.instruction` is a **gate-1** contract and caching it ahead of the relevance schema ships a contradiction to the model on every row (§5.4 C4). HALT if the enrichment pin moves off `professional_v1.0.0.yaml` (D5). Must update both `tests/test_enrichment_prompts.py:29-32` and `tests/test_enrichment_batcher_stage2_loop.py:178-179`, which assert `blocks[0]["cache_control"] == {"type": "ephemeral"}` and fail by construction. |
| **Log tier** | `architectural` — a schema-stable **semantic inversion**: which content is billed at cache-read price versus full price reverses, and the removal of the gate-1 output contract changes what the model is told to produce. No structural or AST test can see either change. |
| **Model class** | `architectural` |
| **Risks & mitigations** | This is the only gate where caching is already partially wired, so it is the one most likely to look correct while being wrong. Row 10's paired assertions (count **and** index) exist for this subtask. |

### T8 — Batch-poller cache-usage observability

| Field | Content |
|---|---|
| **ID** | `T8` |
| **Scope** | Parse Anthropic `message.usage` cache fields in the poller, aggregate them per batch, add them to the three existing completion log lines, and warn when a completed batch reports no cache usage at all. |
| **Files to touch** | `services/batch-poller/app/clients/anthropic.py`, `services/batch-poller/app/models.py` (**already dirty** — a `parked` overlay field is present; do not revert it), `services/batch-poller/app/loop.py`, `tests/test_batch_poller_anthropic_client.py`, `tests/test_batch_poller_loop.py`, `tests/test_batch_poller_enrichment.py`, `CHANGELOG.MD` |
| **Contract bindings** | Rows 4, 14, 15, 21, 22. Owner of rows 4, 14, 15. |
| **Inputs** | T1 |
| **Outputs** | Four new optional fields on `AnthropicBatchResultItem`; `usage` extraction in `fetch_batch_results` following the existing `getattr(...) or ...get(...)` idiom; an aggregation helper used by all three handlers; five new `extra` keys per completion line; `cache_read_zero` warning |
| **Kill criteria** | **(runtime-invariant)** HALT if any of the five log keys collides with a `logging.LogRecord` reserved attribute — that raises at emit time, turning an observability feature into a crash. HALT if fields are added to the model but not extracted, or extracted but not logged (§5.4 C6 — the seam has three stages and all three need a falsifier). HALT if usage is attributed **per entry** by re-deriving `custom_id`: aggregation is batch-level only, so an encode drift in `source_id_to_batch_custom_id` cannot silently mis-attribute (§5.4 C5). HALT if any `BatchRecord`, `BatchPatchRequest`, `domain.py`, or `alembic/**` change becomes necessary — that is D8's excluded path and a scope HALT, not a judgement call. |
| **Log tier** | `standard` — but the five log field names are a contract anchor consumed by G1, so the tier floor is `standard` regardless of how mechanical the diff looks |
| **Model class** | `standard` |
| **Risks & mitigations** | `models.py` is already dirty from the parked overlay; the packet names this so the executor does not attribute those lines to itself. Pre-filter's completion line uses `event="batch_complete"` while both enrichment lines share `event="enrichment_batch_complete"`; that pre-existing collision is **not** fixed here (out of scope), and G1's log query must therefore key on `batch_id`, not `event`. |

### T9 — Batch amortization: minimum volume and maximum hold

| Field | Content |
|---|---|
| **ID** | `T9` |
| **Scope** | Make batches big enough to be worth a cache write. Raise the enrichment batch-size defaults, and add a per-gate minimum-volume threshold with a bounded maximum hold so entries never starve. Stage 1 and stage 2 are configured and timed independently. |
| **Files to touch** | `services/pre-filter-worker/app/config.py`, `services/pre-filter-worker/app/loop.py`, `services/enrichment-batcher/app/config.py`, `services/enrichment-batcher/app/stage1_loop.py`, `services/enrichment-batcher/app/stage2_loop.py`, `tests/test_prefilter_loop.py`, `tests/test_enrichment_batcher_stage1_loop.py`, `tests/test_enrichment_batcher_stage2_loop.py`, `CHANGELOG.MD`, `.dev/decision-logs/prompt-caching/T9-batch-amortization.md` |
| **Contract bindings** | Rows 18, 19, 21, 22. Owner of rows 18, 19. |
| **Inputs** | T1 |
| **Outputs** | Nine env keys through typed parse paths (three per gate, stage 1 and stage 2 separate); hold-deadline logic per gate; raised stage-1/stage-2 defaults 10 → 50; tests including the starvation and abort-interaction cases; decision log recording the in-process clock choice and its restart behaviour |
| **Kill criteria** | **(runtime-invariant)** HALT if an entry can be held indefinitely — the maximum-hold deadline must be reachable on every path, including when inflow is permanently below the minimum. **(runtime-invariant)** HALT if a hash abort (T5/T6/T7) can prevent the hold clock from ever advancing, which would convert one bad hash into permanent starvation (§5.4 C9). HALT if raising stage-1 batch size to 50 requires touching `content_truncation.py` (row 20 frozen) or changes any Anthropic per-request limit assumption. HALT if a `getattr`-papered default is used instead of the typed parse path (row 18). |
| **Log tier** | `architectural` — introduces a new class of failure (deliberate withholding of work) into three loops that previously always submitted what they claimed |
| **Model class** | `architectural` |
| **Risks & mitigations** | The in-process clock resets on restart, so a restart loop could keep batches small; documented rather than solved, because a persisted clock would mean a state-worker schema change that D8 excludes. Larger batches widen the blast radius of one bad prefix — G1 verifies on a real batch before backfill is considered. |

### T10 — Closeout: token-floor gate, docs, tracked artifacts, scope sweep

| Field | Content |
|---|---|
| **ID** | `T10` |
| **Scope** | Prove all three cache keys clear the floor, refresh the as-built caching docs, ensure every plan artifact is tracked, and run the declared-scope sweep. Writes no production code. |
| **Files to touch** | `tests/test_prompt_cache_token_floor.py` (new), `.dev/llm-models-and-cache.md`, `.dev/caching_strategy.md` (checklist boxes only — §18 wiring/ops items this plan lands; the **spec** group stays unchecked per D6), `.dev/plans/prompt-caching/plan.md` (§8 back-fill), `.dev/plans/prompt-caching/artifacts/T10-closure-report.md` (new), `CHANGELOG.MD` |
| **Contract bindings** | Rows 8, 16, 20, 21. Owner of rows 8, 20 verification. |
| **Inputs** | T5, T6, T7, T8, T9 |
| **Outputs** | Token-floor gate with one point-literal assertion per key and the measured margins; refreshed as-built table; checked strategy §18 boxes for landed items only; closure report carrying the clean-worktree test counts, the collected-test count, the frozen-path `git log` output, and the declared-scope `git diff --stat`; §8.1–§8.5 back-filled |
| **Kill criteria** | **(mechanical post-check)** Run the §8.1 verification in a **detached worktree** at the closure SHA — not the working tree — and paste raw passed/failed/skipped/errored counts. In-tree counts do not discharge this: `config/prompts/**` is baked-and-tracked, but the profiles the tests read come from a host directory, so a fresh checkout is the only way to see what a clone sees. **(mechanical post-check)** Re-run `git log b919fdb..HEAD -- <full row-20 path list, literalized inline in this packet>` and paste the output; the frozen-path assumption expires and a partial path list is not a discharge. **(mechanical post-check)** Run `git diff --stat b919fdb..HEAD` and fail on any tracked change outside the union of all ten subtasks' declared Files to touch. **No production edits during verification** — if the sweep surfaces a defect, HALT and route to §7; do not fix it inside the verification window. HALT if any strategy §18 **spec** checkbox is ticked (D6 leaves them open). |
| **Log tier** | `standard` |
| **Model class** | `standard` |
| **Risks & mitigations** | This subtask writes narrative and therefore must **not** own any self-hash recomputation; none is asserted in this plan, so no terminal hash subtask is required. Its own Files-to-touch excludes every production path, which makes the "no production edits during verification" fence mechanically checkable. |

---

## 5. Adversarial pass

Answered through the **packet-only executor persona**: findings are framed as "if I only had this packet, I would halt because …". The lens did real work here — it produced C4 (the cached gate-1 output contract) and C9 (abort-versus-hold starvation), neither of which appears in the context map.

### 5.1 Rejected decompositions

1. **Two subtasks: "wire caching everywhere" + "author all prefixes."** Rejected. It fuses three independent cache keys into one commit, so a HALT on any single gate blocks all three, and it puts roughly 11,000 tokens of quality-bearing content authoring into one packet. It also makes the commit-order guard impossible: one commit cannot reconcile a CHANGELOG against itself.
2. **One shared rubric file consumed by all three gates.** Rejected on contract grounds, not taste: strategy §11b rejects merging, and §14 requires three distinct keys. A single file either gets duplicated into three prefixes (bloat with no cache benefit, since the keys differ anyway) or genuinely shares text across keys, which is the prefix-merging the task statement forbids.
3. **Wire the `cache_control` blocks now, author the annexes later.** Rejected — strategy §17 already rejects this as "rely on Phase 1.5 no code change", and it reproduces today's exact Call 2 failure: `cache_control` is emitted, the prefix is under the floor, and nothing caches. Wiring without content is indistinguishable from doing nothing, while looking done.
4. **Fold rubric hashes into the profile `canonical_hash`.** Rejected by operator decision D7, and independently: a composite would make every rubric edit invalidate the profile hash, aborting *both* gates that read that profile even when only one gate's rubric changed.

### 5.2 Load-bearing assumptions

Tuple shape: `(claim | contract surface | failure mode | subtask IDs)`.

**A1** · `invariant` after T1
```
(The Anthropic SDK accepts ttl:"1h" on the GA cache_control param with no beta header | §2 row 1a + services/*/requirements.txt anthropic pin | an install resolved from the old >=0.40 floor rejects or silently drops ttl; all three keys write 5-minute entries, pay the write premium repeatedly, and the 1h benefit never materialises | T1,T5,T6,T7)
```
Confirmed at planning time on `anthropic` 0.100.0: `CacheControlEphemeralParam.ttl: Literal["5m","1h"]` on the GA type. Row 1a's test is the standing falsifier.

**A2** · `derived` — premise: strategy §1b citing Anthropic docs as of 2026-06-14
```
(Claude Haiku 4.5's minimum cacheable prefix is 4096 tokens | §2 row 8 token-floor gate | if the real floor is higher or has changed, all three annexes are authored to a wrong target and nothing caches while every test is green | T2,T3,T4,T10)
```
Falsifiable only by G1's live `cache_creation_input_tokens`. The 10% margin in row 8 exists to absorb a small error in this premise, not a large one.

**A3** · `derived` — premise: `cl100k_base` approximates Anthropic's tokenizer
```
(cl100k_base token counts are a safe proxy for Anthropic's own tokenization | §2 row 8 + tests/test_prompt_cache_token_floor.py | an annex measured at 4,100 tokens could be under 4,096 for Anthropic and silently not cache, with a green test suite asserting otherwise | T2,T3,T4,T10)
```
This is why row 8 targets **4,506** rather than 4,096. G1 is the real falsifier; the gate test is a proxy check that can only fail loudly, never pass truthfully.

**A4** · `invariant`
```
(The host-mounted profile copy and the repo copy stay byte-identical | docker-compose.yml:52,84 mount ${BISHOP_DATA_ROOT}/profiles + profile_renderer._verify_profile_hash | a host-side profile edit changes cache key A with no repo diff and no image rebuild; hash-or-abort catches it only if the stamped hash also moved | T5,T10)
```
Verified at planning time — both pinned files hash-match between host and repo (`1FD10EA6…04A7`, `1B46A23C…EE9D`). Bound as deferred §2 row 24 / `FU-CACHE-MOUNT-01`.

**A5** · `invariant`
```
(Rubric body bytes are line-ending stable between authoring, hashing, and prompt emission | §2 row 7 compute_rubric_hash LF normalisation | a CRLF checkout on this Windows host changes both the stamped hash and the model-visible prefix bytes, aborting every gate and churning every cache key | T1,T2,T3,T4)
```

**A6** · `derived` — premise: the pin choice in D3 and the current taxonomy
```
(The measured floor gaps are 1816 / 3829 / 3631 tokens for keys A / B / C | §2 row 8 + the D12 token table | a pre-filter pin change (the overlay's own stated revert intent), a TAG_TAXONOMY_ORDERED edit, or an enrichment pin bump moves the gap and silently eats an annex's margin | T2,T3,T4)
```
Re-measured at planning time; all figures reproduced exactly. Row 8 deliberately binds the **total prefix**, not the annex size, so this premise's collapse produces a loud gate failure instead of a stale number. A pin revert is an explicit re-plan trigger.

**A7** · `invariant`
```
(config/prompts has no compose bind mount | §2 row 16 + docker-compose.yml | mounting an empty host dir over the baked rubrics makes resolve_rubric_path point at nothing, and all three gates abort with no repo-visible cause — exactly the masking that already hides the baked config/profiles | T1,T10)
```
Confirmed mechanism at planning time: the container's `/app/config` holds only `profiles`, and its two files come from the host mount, not the image.

**A8** · `invariant`
```
(The spec's Phase 1.5 "no code change" language stays uncorrected and executors will not halt on it | §2 row 23 deferred + D6 | an executor reads bishop_spec_0_6.md §12.3 as authority and halts, or hedges its implementation to match a document the operator has chosen not to fix | all subtasks)
```
Mitigated structurally: every packet carries an explicit line marking the spec informational and known-stale on caching.

**A9** · `derived` — premise: compose state observed at planning time
```
(A live stack is available for G1 | §3 gate G1 | if compose is down or the ANTHROPIC_API_KEY is unset at gate time, G1 cannot run and the plan's only real cache falsifier disappears, leaving A2 and A3 unfalsified | T10,G1)
```
Compose was verified up (nine containers, `state-worker` healthy). Note `.env` leaves `ANTHROPIC_API_KEY` commented, so it must come from a Windows user env var — G1's condition includes confirming the key resolves before the run counts.

### 5.3 Highest re-plan risk

**T3 — the Call 1 rubric.** Not merely the largest authoring job (3,829 tokens, the biggest of the three gaps); the one with the weakest falsifier.

The predicted failure mode is specific, and it is *not* a token shortfall: **T3 reaches the floor and degrades extraction quality, with nothing in the plan able to detect it.** Pre-filter has a labelled gold set (`eval/prefilter_v*`) that T2 can calibrate against. Call 2 produces a bounded float that a human can eyeball. Call 1 produces `summary`, `concepts`, `tags`, `entry_type`, and `challenge_hooks` — and spec §13.1 names `challenge_hooks` the most semantically load-bearing field for Layer 2 retrieval — yet there is **no Call 1 eval harness anywhere in the repo**. The concrete divergence that fires this: an annex full of plausible per-`entry_type` guidance that biases `challenge_hooks` toward generic framings, passing row 8's token gate and every hash test, and surfacing only as degraded retrieval weeks later.

Mitigation is structural rather than hopeful: T3's spot-check artifact is a required **Output**, not a suggestion, and its kill criteria halt on observed `challenge_hooks` degradation. If T3 HALTs, the likely re-plan is to split it into "author" and "validate against a new Call 1 eval slice", which would push this plan past its subtask ceiling and therefore become a new plan version rather than an amendment.

**Process risk, kept out of 5.3 deliberately** and routed to §5.4 / commit-order guards: three parallel subtasks appending one CHANGELOG, and the T1-import commit-order hazard.

### 5.4 Hidden couplings

**C1** · **confirmed**
```
(params.system wire shape: string vs content-block list | bishop_shared/prompt_cache.py:cached_system_blocks vs the three clients' build_requests | if any one gate inlines its own cache_control dict instead of calling the helper, that gate's breakpoint rule silently diverges from the other two and no per-gate test notices, because each gate only tests itself | T5,T6,T7)
```
**Bound** — §2 row 9 plus `tests/test_prompt_cache.py::test_no_inline_cache_control_literals`, a tree grep asserting zero `cache_control` literals outside the one module. Kill criterion on all three wiring subtasks.

**C2** · **confirmed**
```
(existing tests assert the pre-move cache shape | tests/test_enrichment_prompts.py:29-32, tests/test_enrichment_batcher_stage2_loop.py:178-179, tests/test_prefilter_anthropic_client.py:73 | these fail by construction the moment the breakpoint moves or the system becomes a list; an executor that "fixes" them by loosening the assertion removes the only guard on breakpoint placement | T5,T7)
```
**Bound** — each assertion is named with its file:line in the owning subtask's kill criteria, and row 10 requires the replacement to assert **both** the count and the index, so loosening is not an available fix.

**C3** · **confirmed**
```
(three hash notions diverge further | profile_renderer.compute_profile_hash vs pre-filter loop._verify_profile_hash vs stage2_loop._verify_profile_hash vs stage1_loop._profile_render_hash vs the new rubric_assets.compute_rubric_hash | stage 1 will recompute the rubric hash while still trusting the profile's YAML field without recompute, so the same loop enforces two different disciplines and a future reader cannot tell which is intended | T1,T6)
```
**Bound** — §2 row 13 plus a T6 regression test pinning `_profile_render_hash` to `load_profile(path).canonical_hash`, and a T6 kill criterion forbidding the change. The asymmetry is documented in T6's decision log rather than silently inherited.

**C4** · **confirmed** — *found by the packet-only lens; absent from the context map's flag list*
```
(the Call 2 cached prefix would include a gate-1 output contract | profile_renderer.render_profile_prompt appends ProfileOutput.instruction, and professional_v1.0.0.yaml's instruction is the gate-1 {"decision": 0 or 1} JSON, while build_call2_system_prompt then supplies the real relevance schema | moving the breakpoint to the last block caches the contradiction, so every Call 2 row is told to emit a binary decision and a relevance float; today the contradiction exists but only the profile block is marked cacheable, so "just move the breakpoint" makes an existing latent bug permanent and prepaid | T1,T4,T7)
```
**Bound** — §2 row 3 adds `include_output` to `render_profile_prompt` (default `True`, so pre-filter is untouched); T7 renders Call 2 with `include_output=False`; T7 carries a kill criterion forbidding a `{"decision": ...}` instruction inside the cached prefix, and T4 carries the mirror criterion forbidding the annex from reintroducing one.

**C5** · **confirmed**
```
(custom_id encode/re-encode symmetry | bishop_shared/batch_custom_id.py:source_id_to_batch_custom_id + both submit clients + batch-poller/app/loop.py | attaching usage per entry by re-deriving custom_id fails silently as a mis-attribution, not as an error, if the encoding ever drifts | T8)
```
**Bound** — T8 aggregates usage at batch level only; a kill criterion forbids per-entry attribution by re-derived `custom_id`. `batch_custom_id.py` is additionally frozen (row 20).

**C6** · **confirmed**
```
(AnthropicBatchResultItem is the only result seam | batch-poller/app/models.py:AnthropicBatchResultItem + clients/anthropic.py:fetch_batch_results + three _handle_*_complete | the seam has three stages, so fields can land on the model but never be extracted, or be extracted but never logged, and either way the feature reports nothing while looking implemented | T8)
```
**Bound** — three paired falsifiers required by row 4 and row 14: a model round-trip, an extraction test against a fixture carrying `usage`, and a `caplog` assertion on the exact emitted key names.

**C7** · **confirmed** — *found by the packet-only lens*
```
(logging extra dict versus LogRecord reserved attributes | services/batch-poller/app/loop.py logger.info(..., extra={...}) + §2 row 14's five new keys | stdlib logging raises at emit time if an extra key shadows a reserved LogRecord attribute, so an observability addition becomes a crash in the completion handler — the worst possible place, since it runs after results are already posted | T8)
```
**Bound** — row 14 names the exact five keys and requires a reserved-name test.

**C8** · **confirmed**
```
(Call 1 taxonomy injection | enrichment_prompts.build_call1_system_prompt + tag_taxonomy.TAG_TAXONOMY_ORDERED | a taxonomy edit changes key B's prefix bytes, which is both a cache write and a stale call1_rubric hash if the annex restates the taxonomy | T3,T6)
```
**Bound** — T3 is forbidden from restating the taxonomy in the annex, which keeps a taxonomy edit a one-file change rather than a two-copy drift.

**C9** · **confirmed** — *found by the packet-only lens; not in the context map*
```
(minimum-volume hold interacts with hash-or-abort | T9's per-gate hold clock in the three loops vs T5/T6/T7's abort-before-submit paths | a hash mismatch aborts the cycle before submit, so if the hold clock only advances on a successful submit, one bad hash converts a temporary abort into permanent starvation: entries accumulate, the deadline never fires, and the gate looks merely idle | T5,T6,T7,T9)
```
**Bound** — T9 kill criterion requires the maximum-hold deadline to be reachable on every path including the abort path, with an explicit negative test.

**C10** · **suspected**
```
(larger batches widen single-prefix blast radius | services/enrichment-batcher/app/config.py stage1/stage2 defaults 10 -> 50 | one malformed cached prefix now spoils 50 entries per batch instead of 10, and Anthropic batch results are all-or-nothing per request but the wasted spend scales with batch size | T9)
```
**What would disprove it:** G1 confirming a healthy prefix on a real batch before any backfill tranche. Not bound as a kill criterion because the exposure is cost, not correctness, and G7 enablement is explicitly a non-goal of this plan.

**C11** · **ruled out**
```
(BatchRecord / BatchPatchRequest / Alembic if usage columns were chosen | state-worker domain.py + http.py + transitions.py + alembic m1_001/m3_001)
```
**Ruled out** by the context map's own stated disproof condition: operator chose logs-only (D8), and no `domain.py`, `http.py`, `transitions.py`, or `alembic/**` path appears in any subtask's Files to touch. Additionally frozen by row 20, so the premise cannot quietly reappear mid-execution.

**C12** · **ruled out**
```
(4096 cache floor confused with the 4000-token Call 1 user tail | bishop_shared/content_truncation.py cl100k_base 4000 vs the Haiku 4096 floor)
```
**Ruled out** by the map's own condition: `content_truncation.py` appears in no subtask's Files to touch and is frozen (row 20), and §2 row 22 binds the two numbers as distinct terms in every packet.

### 5.4a Standard probe results

| Probe | Fired? | Tuple |
|---|---|---|
| Concurrency fan-out | **yes** | `enrichment-batcher` runs stage 1 and stage 2 under `asyncio.gather`; both may submit in the same tick and both now hold their own rubric verification and hold clock → covered by T6's kill criterion (a stage-1 abort must not take down stage 2) and T9's per-gate independent clocks |
| Test side-effect writes | no | No new harness with a default output directory; T3's spot-check artifact writes to a declared path under `.dev/plans/prompt-caching/artifacts/` |
| Dual-store parity | no | No schema change (D8) |
| Generated-catalog identity | **yes** | Rubric `canonical_hash` is derived from body bytes; every path that reconstructs it (`scripts/rubric_hash.py` stamp, `verify_rubric_hash` read) must normalise line endings identically → A5, row 7 |
| Mutated shared data | **yes** | `config/profiles/professional_v1.2.0_soft_launch.yaml` becomes tracked in T1; `tests/test_profile_renderer.py` already pins the pin table and is already dirty → T1 names both, and row 3 requires the default render to stay byte-identical |
| Typed producer-vs-hub mismatch | **yes** | `cache_hit_ratio` is a float written into a log field alongside integer token counts; no int-typed column receives it (D8 excludes columns), so no silent truncation surface exists → row 14 types it `float \| None` explicitly, `None` when both counts are zero rather than a division-by-zero or a misleading `0.0` |

---

## 6. Executor packets

Ten packets at `.dev/plans/prompt-caching/packets/T<n>.md`, plus the machine surface `.dev/plans/prompt-caching/dag.json`. `G1` owns no packet and is never dispatched.

Each packet contains, in order: YAML frontmatter (`subtask_id`, `tier`, `model_class`, `skills`, `decision_log_path` for architectural tiers); §1 verbatim; §2 verbatim including the row-22 glossary; that subtask's own §4 block verbatim; only the §5.2 assumptions and §5.4 couplings whose tuples name that subtask; and resolved inputs. Every packet also carries the D6 note marking `bishop_spec_0_6.md` informational and known-stale on caching, so no executor halts on the "no code change" language.

**Pre-dispatch byte-parity check.** Every literal this plan quotes as what a subtask will write — the `cache_control` dict, the front-matter schema in row 7, the five log key names in row 14, the nine env keys in row 18, the row-20 frozen path list, the named test file:line references in C2 — is diffed between the plan §2/§4 text and the emitted packet before dispatch. Mismatch is a re-emit, not a judgement call.

**Retired-string sweep targets** for this plan: `system_prompt=` as a pre-filter kwarg (retired by row 5), `{"type": "ephemeral"}` without `ttl` (retired by row 1), `params.system` described as a string, and `anthropic>=0.40`.

---

## 7. Amendment subtasks

None. `run_status` is `complete` at version 1.0.0 with no amendment round.

Routing for what comes later, so the path is not invented under pressure:

- A **G1 failure** (all keys report `cache_read_zero` across two consecutive batches) is a §7 amendment with explicit DAG edges from G1 into the amendment node, not a waiver and not a silent retry. The likely root causes are A1 (SDK/ttl), A2/A3 (floor or tokenizer premise), or a per-request prefix that is not byte-identical — each implies a different amendment scope, so the amendment names which before it starts.
- A **failed kill criterion** on any subtask opens a §7 row **at the time it happens**, with its own packet and its own kill criteria. A retrospective row added at the next pickup is archaeology.
- A **continued HALT** takes a new node (`T3` → `T3-bis`), the original packet is retained unmodified, and the prior decision log gets a supersession banner at its first mention.
- **Producer-versus-output rule:** if a rubric asset turns out to be emitting bad guidance, correcting the annex text without correcting whatever authoring rule produced it is a data-only fix; the §2 row moves too.
- A **pre-filter pin revert** (the overlay's stated intent) is a **re-plan trigger**, not an amendment: it falsifies A6 and moves key A's entire prefix.

---

## 8. Auditor handoff

**`audit_status: not_run`.** No typed audit vocabulary appears anywhere in this section — nothing here is `pending`, `clean`, or `accepted`, so any downstream gate keyed on that vocabulary fails by construction rather than reading a placeholder as a verdict. The milestone handoff record is not written and *Complete* is not declared until an auditor run has finished and the recorded verdict is the auditor's own.

§8 is handoff **preparation**, not verification. It is assembled from the same executor narratives that produced the artifacts, so it cannot see a defect those narratives do not mention. No coverage verdict is claimed below; per-row evidence pointers only.

### 8.1 Completion snapshot — *to be back-filled by T10 at closure*

| Field | Value |
|---|---|
| Closure tree SHA | `<T10 fills>` |
| Verification command (declared **and** operative — identical, no waiver) | `pytest tests/ -m "not heavy"` |
| Run environment | detached worktree at the closure SHA — **not** the working tree |
| Raw counts | `<T10 pastes passed / failed / skipped / errored / exit code>` |
| Collected count | `<T10 fills>` — must confirm `tests/test_prompt_cache.py`, `tests/test_rubric_assets.py`, and `tests/test_prompt_cache_token_floor.py` are actually collected |
| Per-subtask commit map | `<T10 fills from `git log` / `git blame`, not from dispatch order; any commit carrying more than one subtask names every subtask ID in its message>` |

**Plan-time collection parity check (done now):** `pyproject.toml` declares `testpaths = ["tests"]`, `pythonpath = ["."]`, no `addopts`, and no declared markers. `-m "not heavy"` therefore filters only the single `@pytest.mark.heavy` test in `tests/test_g5_quality_gate.py` and collects everything else in `tests/`, including new modules. The command gates what it claims to gate.

The handoff SHA must contain only this plan's declared scope. If the closure commit also carries unrelated content — and note that the working tree at planning time held substantial unrelated overlay and parked-route changes (D13) — §8.1 must disclose and justify it, or name a different commit.

### 8.2 Artifact chain

Every path must satisfy `git show HEAD:<path>` at the §8.1 SHA. `<T10 verifies>`

1. `.dev/plans/prompt-caching/context-map.md` — **staleness disposition: refreshed-not-required.** The map's recorded SHA `b919fdb` **equals** the planning HEAD, so zero committed files in direct scope diverged. Pin semantics: the SHA means code HEAD at scouting time, and it is still code HEAD at plan time. If the closure SHA diverges from `b919fdb` on files in direct scope — which it will, since this plan edits them — T10 records **deferred** with the diverged file list and follow-up **`FU-CACHE-MAP-01`**, per §8.2's requirement that divergence be a decision rather than a note. Two planning-time corrections to the map are already recorded: D16 (compose is up, not down) and P1 (the profiles mount mechanism).
2. `.dev/plans/prompt-caching/plan.md` — this file
3. `.dev/plans/prompt-caching/dag.json`
4. `.dev/plans/prompt-caching/packets/T1.md` … `T10.md`
5. `.dev/decision-logs/prompt-caching/T1-cache-and-rubric-contract.md`, `T2-prefilter-rubric.md`, `T3-call1-rubric.md`, `T4-call2-rubric.md`, `T6-call1-wiring.md`, `T7-call2-breakpoint-move.md`, `T9-batch-amortization.md`
6. `.dev/plans/prompt-caching/artifacts/T3-call1-spotcheck.md`, `.dev/plans/prompt-caching/artifacts/T10-closure-report.md`
7. `.dev/caching_strategy.md` — binding for rejected alternatives and the 4,096 floor
8. Not consumed: no audit file exists at version 1.0.0

**Operator-attested evidence.** T3's spot-check artifact and T10's closure report are operator/executor-produced evidence, and *Complete* requires both **tracked at the closure SHA**. Handoff halts if either exists only in an uncommitted working tree. G1's log evidence is likewise pasted into the closure report rather than left in a terminal scrollback.

### 8.3 §2 evidence — *per-row pointers to be back-filled by T10*

One row per §2 contract (1, 1a, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 18, 19, 20, 21, 22), each naming the shipped `file:symbol` and the test or check that proves it. Rows 17, 23, 24, 25 are `deferred` and carry their follow-up ID instead of evidence.

### 8.4 §5 disposition — *to be back-filled by T10*

Every A1–A9 and C1–C12 item must be marked **closed** (evidence cited), **open** (with what would close it and whether it blocks merge), or **treat-as-prediction**. Pre-marked where the disposition is already determined:

| Item | Pre-marked | Basis |
|---|---|---|
| A1 | **closed** | `CacheControlEphemeralParam.ttl` read directly on the installed SDK 0.100.0; row 1a pins it |
| A2, A3 | **open** — does not block merge, blocks G1 | Only a live `usage` reading can close either; the gate test is a proxy |
| A4 | **closed** | Host and repo copies hash-matched at planning time; residual risk bound as row 24 |
| A7 | **closed** | Container `/app/config` inspected directly; row 16's compose test is the standing guard |
| A9 | **treat-as-prediction** | Compose was up at planning time; the auditor re-verifies rather than trusting the observation |
| C11, C12 | **ruled-out** | Each by the context map's own stated disproof condition, and additionally frozen by row 20 — the premise was shown not to apply, not merely judged compatible |

No item is closed as `verified-compatible` in this plan, because no comparand file was read for that purpose. A false-positive closure would remove a surface from the auditor's list that an honest `open` keeps on it.

### 8.5 Cold-read seeds

Recommended for the auditor's narrative-blind Phase 0 read, chosen where contract-versus-code drift surfaces first:

1. `bishop_shared/enrichment_prompts.py` — the Call 2 breakpoint move and the removal of the gate-1 output contract from the cached prefix (C4). The substantive failure mode to look for is **semantic**: a prefix that caches contradictory output instructions, not a naming or vocabulary difference.
2. `bishop_shared/prompt_cache.py` — whether `cache_control` genuinely lands on the last block and whether the returned dicts are unaliased across requests (row 1).
3. `services/pre-filter-worker/app/loop.py` — whether the rubric abort precedes the Anthropic call or merely precedes the *return* (row 12).
4. `services/enrichment-batcher/app/stage1_loop.py` — whether `_profile_render_hash` semantics survived T6 untouched while a rubric recompute was added beside it (C3, row 13).
5. `services/batch-poller/app/loop.py` — whether all three stages of the usage seam actually connect, and whether the five log keys are the literal names in row 14 (C6, C7).
6. `config/prompts/call1_rubric_v1.md` — the highest re-plan risk surface (§5.3); read for extraction-quality plausibility, since no automated Call 1 eval exists.

### 8.6 Audit remediation cross-link

Omitted — no §7 amendment fired during version 1.0.0.

---

## Validation before finalizing

| # | Rule | Status |
|---|---|---|
| 1 | Every subtask has all required fields; no TBD in kill criteria or contract bindings | **pass** |
| 2 | DAG has no cycles, no orphans; every node has correct intent | **pass** — 10 executable + 1 gate, single sink `G1` |
| 3 | Parallel safety: no two parallel subtasks touch the same interface | **pass with documented merge strategy** — `{T2,T3,T4}` and `{T5,T6,T7}` share only `CHANGELOG.MD`, governed by the ascending-`Tn` commit-order guards in §3 |
| 4 | At least one rejected alternative and one load-bearing assumption | **pass** — 4 rejected, 9 assumptions |
| 5 | Log tiers match scope; no `trivial` subtask owns a contract-anchor string | **pass** — no `trivial` tier in this plan; T8 held at `standard` because its five log keys are consumed by G1 |
| 6 | Packet emission completed; self-containment verified | **pending §6 emission** |
| 7 | Typed-surface binding satisfied for every §2 key | **pass** — rows 1, 2, 4, 7, 14, 18 each name owner, typed site, and test; no prose-only keys, no `getattr` defaults |
| 8 | CLI strings frozen before downstream packets emit | **pass** — `scripts/rubric_hash.py <path> [--render]` frozen in T1 (row 6) before T2/T3/T4 packets, which consume it to stamp |
| 9 | Amendment DoD includes narrative back-annotation | **n/a** — no amendment at 1.0.0; the rule is stated in §7 for when one fires |
| 10 | Wire contract matches shipped behaviour; no illustrative values presented as binding | **pass** — row 1 fixes `{"type": "ephemeral", "ttl": "1h"}` as the single binding literal; there are no illustrative wire examples in §2 |
| 11 | Decision log paths frozen; architectural log preambles current | **pass** — `.dev/decision-logs/prompt-caching/T<n>-<slug>.md` for T1, T2, T3, T4, T6, T7, T9. **Supersession obligation recorded:** T7 changes the behaviour narrated by `.dev/decision-logs/m5-enrichment/T4-call2-cache-control.md` (which records the breakpoint on the profile block only, and rejects omitting `cache_control` for short profiles). T7's Outputs must add a supersession banner to that log at its first mention, not only append to §2 |
| 12 | §5.2/§5.4 conform to tuple shape and name explicit `Tn` IDs; §2 internally consistent | **pass** — all 21 items are tuples with `Tn` lists. §2 rows read against each other: row 20 freezes `content_truncation.py` while row 22 separates 4000 from 4096, so no row requires editing a frozen file; row 16's no-mount rule and row 8's token gate are jointly satisfiable because the gate measures repo files, not container files; row 21 forbids new `conftest.py` and no row requires one |
| 13 | §5 answered through the packet-only executor lens | **pass** — and it earned its place: C4, C7, and C9 were produced by it and appear in no map flag |
| 14 | Context map present where required | **pass** — no subtask's Files to touch is "unknown — discovery required" |
| 15 | §8.1 snapshot valid; gate-command collection parity confirmed | **pass at plan time** for collection parity (see §8.1); the snapshot itself is T10's to fill on a detached worktree |
| 16 | §8.2 chain resolves at HEAD; no out-of-tree binding artifacts | **conditional — D1 must land first.** The map and this plan are untracked at the moment of writing; committing `.dev/plans/prompt-caching/` is a precondition to dispatch, not a closeout task |
| 17 | §8.4 disposition complete with matching closure vocabulary | **pending T10** — pre-marked items in §8.4 use `ruled-out` only where the premise was shown not to apply; no `verified-compatible` claims are made anywhere |
| 18 | Charter binding declared | **n/a** — non-charter plan (Standard mode); no milestone stub in the inputs |
| 19 | Carryability check | **pass** — 10 executable subtasks, at the ceiling of the 4–10 budget. No split proposal required, no `merge-candidate` flag. Any amendment that adds a subtask crosses the ceiling and requires an explicit budget-amendment line in this header first |
| 20 | Declared-scope sweep at closure | **assigned** — T10, with the frozen path list literalized inline in its packet and a "no production edits during verification" fence in its own kill criteria |




