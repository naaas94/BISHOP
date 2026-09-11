---
subtask_id: T8-bis
tier: architectural
model_class: architectural
skills:
  - executor-subtask-execution
decision_log_path: .dev/decision-logs/m8-hardening-scale/T8-backfill-enable.md
round: amendment-2
---

# Executor packet — T8-bis

**Plan:** m8-hardening-scale v1.3
**Executor skill:** executor-subtask-execution

> Continuation of halted T8. Do not re-run packets/T8.md. G6 enrichment is assessed 7/10 with three hook rejects kept. Do not flip flags. Do not require BISHOP_G6_MANUAL=1 green. Do not edit Call 1 prompts.

---

## 1. Task statement

**(a) Active milestone ID:** M8 — Hardening and Scale

**(b) Charter version:** `.dev/bishop_program_charter.md` v0.1.0

**(c) Charter non-goals (verbatim):** All §23 deferred items (graph layer, daily digest, cosine anchor migration, personal domain, cross-domain query, reranker, query expansion, local enrichment path, time-decayed weights, reading history analytics, Redis/Postgres upgrades). All §24 rejected items. `DomainEnum.both` (removed).

Implement remaining source adapters (HuggingFace, PapersWithCode, SemanticScholar, GitHub, OpenReview; LessWrong pending API verification), complete UI (escalation panel with manual retry/permanent-fail, reading status updates, DB explorer), run quality validation gates G5/G6, and enable chunked backfill across all registered sources after gates pass (G7).

**Non-goals:**
- Personal domain scrapers, NL profile, and workflow (§3.2, §19.2).
- Cross-domain query (§19.3).
- Reranker (`ms-marco-MiniLM-L-6-v2`, §16.6), query expansion (§16.5), daily digest (§17.2).
- Graph layer (Kuzu), cosine anchor migration, interest-profile re-enrichment, local Ollama enrichment path.
- Time-decayed retrieval weights, reading history analytics.
- Redis/Postgres infrastructure upgrades.
- `Mark Resolved` escalation action (spec §14.2 — deferred; charter exit gate does not require it).
- Changes to `batch-poller` or enrichment prompt templates except NL profile YAML iteration under T7 if **G6 enrichment** sampling fails (prefilter pin `professional_v1.2.0` is already calibrated — do not bump unless gold replay fails the owner bar).
- Embedding model upgrade to `nomic-embed-text` unless G5 live fails and charter owner authorizes §7 amendment (carry M7 handoff trigger).
- All items in §23 and §24 of `bishop_spec_0_6.md` are non-goals for this plan.
- **Already-landed — do not implement or rewrite:** `config/index_policy.yaml` + `bishop_shared/index_policy.py`; ArXiv category gate (`config/sources/arxiv.yaml`, `bishop_shared/source_config.py`, `apply_category_gate`); gate-split profile pins (`profile_renderer.py`: prefilter → `professional_v1.2.0.yaml`, enrichment → `professional_v1.0.0.yaml`).
- **Do not rebuild G6** as CSV scaffold / 20-item sample / `tests/test_g6_quality_sampling.py` / `scripts/run-g6-quality-sampling.sh` / `.dev/quality/g6-sampling-template.md` (v1.0 T7 paths — retired).
- **Do not rewrite** `tests/test_g5_quality_gate.py` or mutate `eval/prefilter_v1/**`.
- **v1.3:** Do not flip G6 enrichment reject flags to pass the all-true pytest. Do not edit `bishop_shared/enrichment_prompts.py` or `config/profiles/professional_v1.0.0.yaml` in this wave (follow-up `g6-call1-hooks-iteration`).

**Charter row dispositions:**

| Charter row | Disposition |
|-------------|-------------|
| `ADAPTER_REGISTRY` expanded (HF, PwC, SS, GitHub, OpenReview, LessWrong if verified) | §2 `ADAPTER_REGISTRY` (T8-bis) + T2–T4 adapter rows |
| `fetch_manifest` + `fetch_content` per new adapter | §2 adapter rows T2–T4 |
| Escalation panel: `GET /escalations`, `POST /entries/retry`, permanent-fail | §2 T5 + T6 rows |
| Reading status update via UI | §2 T5 + T6 rows |
| Backfill config: per-source `backfill_window_days` from §18.2 | §2 `BACKFILL_CONFIG` (T1-bis) + T8-bis env keys |
| Exit: G7 backfill running / all-sources e2e | §2 T8-bis env + `verify-m8.sh`; `cluster-runtime` owner T8-bis (decision log) |
| Exit: pre-filter quality gate | §2 G6 prefilter gold — landed, T7 consumes |
| Exit: enrichment quality gate (10 entries, `challenge_hooks` + `value_rationale`) | §2 G6 enrichment sampling — T7 template + **v1.3 Landed:** assessed 7/10, all-true waived |
| Exit: escalation panel functional | §2 UI `/escalations` (T6) |
| Entry: G4, G5, G6 satisfied | **v1.3:** T8-bis kill. G4 = live INDEXED corpus (97 rows 2026-09-10). G5 = T7 fixture bind. G6 = assessed + owner waiver (not all-true). |

---

## 2. Shared contracts

### Types / interfaces

**Enforcement default:** every row below is `pytest-enforced`; verification owner = **Owner** column, unless the row says otherwise.

| Symbol | Owner | Typed surface | Test |
|--------|-------|---------------|------|
| `BackfillConfig` | T1-bis | `bishop_shared/scraper_config.py` — frozen dataclass: `window_days: int`, `categories: tuple[str, ...] = ()` | `tests/test_scraper_config_shared.py::test_backfill_config_round_trip` |
| `BACKFILL_CONFIG` | T1-bis | `bishop_shared/scraper_config.py` — `dict[str, BackfillConfig]` per §18.2 (all seven source keys). **v1.2:** `arxiv.window_days=60` is the backfill-window datum, not the incremental default. Incremental `resolve_effective_since(since=None)` stays 7 days (`ARXIV_BACKFILL_WINDOW_DAYS`) until T8-bis enables backfill. | `tests/test_scraper_config_shared.py::test_backfill_config_matches_spec_defaults` |
| `SOURCE_RATE_LIMITS` (all sources) | T1-bis | `services/scraper/app/rate_limit.py` — Appendix B values for arxiv, github, semantic_scholar, huggingface, paperswithcode, openreview, lesswrong | `tests/test_scraper_rate_limit.py::test_all_source_rate_limits_match_appendix_b` |
| `SOURCE_SCHEDULE_INTERVAL_SEC` | T1-bis | `bishop_shared/scraper_config.py` — per-source default seconds (Appendix B table) | `tests/test_scraper_config_shared.py::test_schedule_defaults` |
| `BISHOP_BACKFILL_ENABLED` | T8-bis | `services/scraper/app/config.py` — bool env, default `False` | `tests/test_scraper_config.py::test_backfill_enabled_default_false` |
| `BISHOP_BACKFILL_CHUNK_DAYS` | T8-bis | `services/scraper/app/config.py` — int, default `7` | `tests/test_scraper_config.py::test_backfill_chunk_days_default` |
| `BISHOP_BACKFILL_INTER_CHUNK_DELAY_SEC` | T8-bis | `services/scraper/app/config.py` — int, default `300` | `tests/test_scraper_config.py::test_backfill_inter_chunk_delay_default` |
| `GITHUB_TOKEN` | T3 | `services/scraper/app/config.py` — optional `str \| None` from env | `tests/test_scraper_config.py::test_github_token_from_env` |
| `SEMANTIC_SCHOLAR_API_KEY` | T3 | `services/scraper/app/config.py` — optional | `tests/test_scraper_config.py::test_semantic_scholar_key_from_env` |
| `HUGGINGFACE_TOKEN` | T2 | `services/scraper/app/config.py` — optional | `tests/test_scraper_config.py::test_huggingface_token_from_env` |
| `HuggingFaceAdapter` | T2 | `services/scraper/app/adapters/huggingface.py` — `fetch_manifest` + `fetch_content` | `tests/test_scraper_adapters_huggingface.py` |
| `PapersWithCodeAdapter` | T2 | `services/scraper/app/adapters/paperswithcode.py` | `tests/test_scraper_adapters_paperswithcode.py` |
| `SemanticScholarAdapter` | T3 | `services/scraper/app/adapters/semantic_scholar.py` | `tests/test_scraper_adapters_semantic_scholar.py` |
| `GitHubAdapter` | T3 | `services/scraper/app/adapters/github.py` | `tests/test_scraper_adapters_github.py` |
| `OpenReviewAdapter` | T4 | `services/scraper/app/adapters/openreview.py` | `tests/test_scraper_adapters_openreview.py` |
| `LessWrongAdapter` | T4 | `services/scraper/app/adapters/lesswrong.py` — conditional registry | `tests/test_scraper_adapters_lesswrong.py` (skip if probe fails) |
| `ADAPTER_REGISTRY` | T8-bis | `services/scraper/app/adapters/registry.py` — ArXiv + landed T2–T4 adapters (LessWrong if verified) | `tests/test_scraper_loop.py::test_registry_lists_all_expected_sources` |
| `ReadingStatusPatchRequest` | T5 | `services/state-worker/app/models/http.py` | `tests/test_state_worker_reading_status.py` |
| `PATCH /entries/{source_id}/reading-status` | T5 | state-worker entries router | `tests/test_state_worker_reading_status.py` |
| `PermanentFailPostRequest` | T5 | `services/state-worker/app/models/http.py` | `tests/test_state_worker_permanent_fail.py` |
| `POST /entries/permanent-fail` | T5 | state-worker entries router | `tests/test_state_worker_permanent_fail.py` |
| `POST /entries/{source_id}/retry` | T6 | query-api proxy → state-worker `POST /entries/retry` | `tests/test_query_api_routes_entry_actions.py` |
| `POST /entries/{source_id}/permanent-fail` | T6 | query-api proxy | `tests/test_query_api_routes_entry_actions.py` |
| `PATCH /entries/{source_id}/reading-status` | T6 | query-api proxy | `tests/test_query_api_routes_entry_actions.py` |
| UI `/escalations` | T6 | `services/ui/app/main.py` + templates | `tests/test_ui_escalations.py` |
| UI `/explorer` | T6 | DB explorer filter page | `tests/test_ui_explorer.py` |
| `scripts/verify-m8.sh` | T8-bis | M8 pytest gate script. **v1.3:** invokes G5 fixture + G6 gold bind + G6 enrichment **structural** tests only. Must not set `BISHOP_G6_MANUAL=1` (manual checklist is expected-fail on kept hook rejects). | `tests/test_verify_m8.py` |
| G5 quality harness | LANDED (M6) — T7 consumes | `tests/test_g5_quality_gate.py` (frozen). T7 may add wrapper `scripts/run-g5-quality-gate.sh` only | existing `test_g5_quality_gate_fixture` / `test_g5_fixture_queries_count` — do not rewrite |
| G6 prefilter gold | LANDED — T7 consumes | `eval/prefilter_v1/contract.json` + `items.json` + `labels.json` + `scripts/replay_prefilter.py` | T7 `tests/test_g6_prefilter_gold.py` (existence + count ≥ 129 + replay script importable). **operator-verified** replay already accepted at HEAD `5e04833`. Do not rebuild gold |
| G6 enrichment sampling | T7 (template) + T8-bis (waiver consume) | `.dev/quality/g6-enrichment-template.md` + `tests/test_g6_enrichment_sampling.py` + `scripts/run-g6-enrichment-sampling.sh` | **Split:** `pytest-enforced` structural schema (T7). `operator-verified` 10-entry fill+judge (landed 2026-09-10). **Landed:** 7/10 both-true; hooks reject `arxiv:2606.09483`, `arxiv:2608.14509`, `arxiv:2606.27330`; all 10 rationales accepted. `test_g6_enrichment_manual_checklist` remains the all-true falsifier and is **expected-fail**. Owner waiver (Ale, 2026-09-10): charter G6 "assessed" is satisfied; do not flip flags; do not require `BISHOP_G6_MANUAL=1` green for T8-bis / G7. |
| `index_policy` | LANDED — M8 non-goal | `config/index_policy.yaml` + `bishop_shared/index_policy.py` (module-level loader). `enforce: false`, `keep_min: 0.40` | existing `tests/test_index_policy.py` — do not modify |
| `apply_category_gate` / `SourceCategoryConfig` | LANDED — M8 non-goal | `bishop_shared/source_config.py` + `arxiv.py::apply_category_gate` (module-function). Distinct from `BACKFILL_CONFIG.categories` | existing `tests/test_scraper_arxiv_adapter.py` — T1 must not remove or bypass the call from `_gate_by_category` |
| Gate-split profile pins | LANDED — M8 non-goal | `bishop_shared/profile_renderer.py` `_PROFILE_FILENAME`: prefilter → `professional_v1.2.0.yaml`; enrichment → `professional_v1.0.0.yaml` | existing `tests/test_profile_renderer.py` — do not modify |
| Frozen-adjacent paths | T1-bis, T7, T8-bis | Byte-unchanged from baseline SHA `5e048337b9b7262c604dfce04f3e565d33cf0f4a` through M8 closure. Paths: `config/index_policy.yaml`, `bishop_shared/index_policy.py`, `config/sources/arxiv.yaml`, `bishop_shared/source_config.py`, `bishop_shared/profile_renderer.py`, `config/profiles/professional_v1.2.0.yaml`, `config/profiles/professional_v1.0.0.yaml`, `eval/prefilter_v1/contract.json`, `eval/prefilter_v1/items.json`, `eval/prefilter_v1/labels.json`, `scripts/replay_prefilter.py`, `scripts/build_eval_v1.py`, `scripts/apply_adjudication.py`, `tests/test_index_policy.py`, `tests/test_g5_quality_gate.py` | T8-bis kill: `git diff 5e048337b9b7262c604dfce04f3e565d33cf0f4a -- <paths>` empty. `docs-structural` + T8-bis paste; semantic falsifier = existing pytest on those modules |
| Call 1 `challenge_hooks` prompt iteration | deferred | `bishop_shared/enrichment_prompts.py` `build_call1_system_prompt` | Follow-up ID `g6-call1-hooks-iteration` (post-M8). T8-bis must not edit prompts or `professional_v1.0.0.yaml`. First deferral in v1.3 — may not stay `deferred` across two consecutive later plan versions without an amendment line. |

**Decision log paths (architectural):**
- T1: `.dev/decision-logs/m8-hardening-scale/T1-adapter-foundation.md`
- T4: `.dev/decision-logs/m8-hardening-scale/T4-openreview-lesswrong.md`
- T5: `.dev/decision-logs/m8-hardening-scale/T5-state-worker-ops.md`
- T8 / T8-bis: `.dev/decision-logs/m8-hardening-scale/T8-backfill-enable.md` (T8 never wrote it; T8-bis owns the file)

### Error envelope

| Surface | Contract |
|---------|----------|
| Adapter HTTP failures | Reuse scraper `failure_envelope` + §6.3 / Appendix C classification — no changes to exception types |
| `PATCH /entries/{source_id}/reading-status` | 404 `source_id` not in entries; 422 invalid enum; 409 if no `entries` row (manifest-only) |
| `POST /entries/permanent-fail` | 404 not found; 409 if `processing_state != ESCALATION_FLAGGED` |
| `POST /entries/{source_id}/retry` (proxy) | Pass-through state-worker `RetryPostResponse` or 409/404 |
| query-api upstream errors | 502 `{"error":"upstream_error","status":<code>}` (match M7 escalations proxy) |
| LessWrong probe failure | Not an error — omit adapter; log `WARN` `lesswrong_adapter_skipped` |

### Naming

- Adapter modules: `services/scraper/app/adapters/<source>.py` (snake_case source slug matching `SourceEnum.value`)
- Test modules: `tests/test_scraper_adapters_<source>.py`
- Compose image tags: `bishop/scraper:m8`, `bishop/ui:m8` (state-worker unchanged — hub edits are backward-compatible additions only)
- Env prefix: `BISHOP_` for backfill toggles; source tokens `GITHUB_TOKEN`, `SEMANTIC_SCHOLAR_API_KEY`, `HUGGINGFACE_TOKEN`

### Logging

- Structured `extra` fields: `event`, `source`, `source_id` on adapter fetch, backfill chunk boundaries, escalation actions
- Backfill chunk start/complete: `INFO` with `chunk_start`, `chunk_end`, `source`
- Permanent-fail / manual retry from UI: `INFO` `manual_permanent_fail`, `manual_retry` with `source_id`

### Tests

- Framework: pytest (existing repo convention)
- Location: `tests/test_scraper_adapters_*.py`, `tests/test_state_worker_*.py`, `tests/test_query_api_routes_entry_actions.py`, `tests/test_ui_*.py`, `tests/test_g6_prefilter_gold.py`, `tests/test_g6_enrichment_sampling.py`, `tests/test_verify_m8.py`. Do **not** add `tests/test_g6_quality_sampling.py`.
- Adapter tests: HTTP mocked via `respx` or `httpx.MockTransport` — no live network in default CI
- Optional live probes: `BISHOP_LESSWRONG_PROBE_LIVE=1`, `BISHOP_G5_LIVE=1` (heavy), `BISHOP_G6_MANUAL=1` (enrichment all-true checklist — **expected-fail** after 2026-09-10 review; not a verify-m8 input)
- M8 gate: `scripts/verify-m8.sh` — subprocess isolation pattern from `verify-m7.sh` for `app` package collision hygiene. Invokes G5 fixture + T7 G6 gold + G6 enrichment **structural** tests only. Must not export `BISHOP_G6_MANUAL=1`. Not the retired v1.0 G6 CSV script.

### CLI surface

- Existing `bishop escalations` (M7) unchanged
- No new CLI subcommands required for M8 exit gate
- Frozen in T7 before T8: `scripts/run-g5-quality-gate.sh` (wrapper), `scripts/run-g6-prefilter-replay.sh` (wraps landed `replay_prefilter.py`), `scripts/run-g6-enrichment-sampling.sh`
- **Retired (v1.0):** `scripts/run-g6-quality-sampling.sh` — do not create

---

### T8-bis — Backfill enable + verify-m8 (amendment-2)

| Field | Content |
|--------|---------|
| **ID** | T8-bis |
| **Scope** | Same closer as T8: finalize `ADAPTER_REGISTRY` with all T2–T4 adapters; backfill chunking (§18.4); wire `BISHOP_BACKFILL_*`; compose `m8` tags; `scripts/verify-m8.sh`; mocked multi-source ingest; G7 procedure; refresh `.dev/architecture/bishop/`. When `BISHOP_BACKFILL_ENABLED=1`, ArXiv window is `BACKFILL_CONFIG["arxiv"].window_days` (60). **G6:** consume the filled `.dev/quality/g6-enrichment-template.md` (assessed 7/10). Do **not** flip reject flags, do **not** require `BISHOP_G6_MANUAL=1` green, do **not** edit `enrichment_prompts.py` or `professional_v1.0.0.yaml`. `verify-m8.sh` runs G6 structural tests only. |
| **Files to touch** | `services/scraper/app/adapters/registry.py`, `services/scraper/app/loop.py`, `services/scraper/app/config.py`, `docker-compose.yml`, `scripts/verify-m8.sh`, `tests/test_verify_m8.py`, `tests/test_scraper_backfill_chunking.py`, `tests/test_scraper_loop.py`, `CHANGELOG.MD`, `.dev/decision-logs/m8-hardening-scale/T8-backfill-enable.md`, `.dev/architecture/bishop/` |
| **Contract bindings** | All §2 env keys now owned by T8-bis; `ADAPTER_REGISTRY`; verify script; frozen-adjacent paths; G6 waiver row |
| **Inputs** | T2, T3, T4, T6, T7 (landed). T8 produced nothing. |
| **Outputs** | Backfill orchestration, gate script, compose tags, decision log, architecture refresh |
| **Kill criteria** | Halt if context-map flag 4 is unresolved at execution start (apply §0 frozen resolution). **executor-preflight G6:** halt if `.dev/quality/g6-enrichment-template.md` JSON has fewer than 10 non-empty `source_id`s or any `hooks_acceptable` / `rationale_acceptable` is still `null`. Do **not** halt because any flag is `false`. Do **not** halt because `BISHOP_G6_MANUAL=1 pytest …::test_g6_enrichment_manual_checklist` fails. Halt if about to set those three hook rejects to `true` or edit Call 1 prompts. G4/G5/G6 changelog checkbox meaning: G4 = live INDEXED corpus (97 rows 2026-09-10); G5 = T7 fixture bind (`tests/test_g5_quality_gate.py`); G6 = assessed + this waiver. Halt if any T2–T4 adapter missing `fetch_content` when registry merged. Halt if G5 live run requested (`BISHOP_G5_LIVE=1`) fails — escalate §7 for embedding model, do not enable backfill. Halt if `BISHOP_BACKFILL_ENABLED=1` in compose without chunking landed. Halt if `verify-m8.sh` exports `BISHOP_G6_MANUAL=1`. Halt if `git diff 5e048337b9b7262c604dfce04f3e565d33cf0f4a -- config/index_policy.yaml bishop_shared/index_policy.py config/sources/arxiv.yaml bishop_shared/source_config.py bishop_shared/profile_renderer.py config/profiles/professional_v1.2.0.yaml config/profiles/professional_v1.0.0.yaml eval/prefilter_v1/contract.json eval/prefilter_v1/items.json eval/prefilter_v1/labels.json scripts/replay_prefilter.py scripts/build_eval_v1.py scripts/apply_adjudication.py tests/test_index_policy.py tests/test_g5_quality_gate.py` is non-empty. |
| **Log tier** | architectural |
| **Model class** | architectural — registry merge + backfill enable + G7 |
| **Risks & mitigations** | Volume explosion — chunking + pre-filter as volume gate per §18.3. Known Call 1 hook-quality debt — do not paper it over. |

---

## Filtered 5.2 (T8-bis)

- (G4/G5/G6 satisfied before backfill enable | charter §5 gates + M7 handoff + v1.1 G6 gold absorb | backfill at scale masks pipeline bugs | T8) superseded v1.3
- (G4 live INDEXED + G5 fixture + G6 assessed 7/10 with documented hook rejects is sufficient for G7 | charter G6 "assessed" + owner waiver 2026-09-10 | T8-bis treats BISHOP_G6_MANUAL=1 fail as a start kill | T8-bis) invariant — operator-locked
- (Call 1 challenge_hooks quality debt is accepted for G7; three rejects kept | §2 G6 enrichment Landed | T8-bis flips flags or edits enrichment_prompts.py | T8-bis) invariant — operator-locked
- (content-scraper continues importing scraper ADAPTER_REGISTRY | adapter_resolver.py | fetch_content missing for new source → SCRAPE_FAILED spike | T2,T3,T4,T8,T8-bis) invariant
- (LessWrong GraphQL may be unavailable | §23 defer trigger | registry incomplete vs charter if verified | T4,T8,T8-bis) invariant
- (G6 prefilter evidence is landed eval/prefilter_v1 (129 items), not a 20-item CSV | §2 G6 prefilter gold | T7 rebuilds obsolete scaffold and drifts the gate | T7,T8,T8-bis) invariant — operator-locked
- (index_policy, ArXiv category gate, and split profile pins are already landed and frozen | §2 frozen-adjacent paths | executor reinvents or collapses them into BACKFILL_CONFIG | T1-bis,T7,T8,T8-bis) invariant — operator-locked
- (incremental ArXiv window is 7 days; BACKFILL_CONFIG arxiv.window_days=60 is backfill-only | §0 flag 4 + §2 BACKFILL_CONFIG | T1-bis replaces 7 with 60 and breaks test_resolve_effective_since_uses_backfill_window | T1-bis,T8,T8-bis) invariant — operator-locked

## Filtered 5.4 (T8-bis)

- (fetch_content must ship with each manifest adapter | content-scraper adapter_resolver + scraper registry | SCRAPE_FAILED | T2,T3,T4,T8,T8-bis) confirmed
- (SOURCE_RATE_LIMITS key must exist before failure_envelope | rate_limit.py + loop.py | KeyError | T1-bis,T8,T8-bis) confirmed
- (Parallel T2/T3/T4 registry imports | registry.py | merge conflicts | T2,T3,T4,T8,T8-bis) confirmed — T8-bis sole merger
- (GITHUB_TOKEN required for backfill-scale GitHub | scraper config | anonymous rate limit | T3,T8,T8-bis) confirmed
- (verify-m8 must not invoke BISHOP_G6_MANUAL=1 | scripts/verify-m8.sh + test_g6_enrichment_manual_checklist | gate fails on kept rejects | T8-bis) confirmed — Bound
- (T8-bis must not edit g6-enrichment-template flags or enrichment_prompts.py | §2 G6 Landed + deferred Call 1 | quality signal erased | T8-bis) confirmed — Bound

## Resolved inputs

T2, T3, T4, T6, T7 landed (adapters, UI/proxies, G5 wrapper + G6 gold + filled enrichment template). T8 produced nothing.
G6 template path: `.dev/quality/g6-enrichment-template.md` — 10 filled slots; hooks reject arxiv:2606.09483, arxiv:2608.14509, arxiv:2606.27330.
Flag 4: incremental ArXiv stays 7; when BISHOP_BACKFILL_ENABLED=1 use BACKFILL_CONFIG["arxiv"].window_days (60).
