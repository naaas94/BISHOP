---
subtask_id: T10-bis
tier: standard
model_class: standard
skills:
  - executor-subtask-execution
round: amendment-4
---

# Executor packet — T10-bis

**Plan:** m8-hardening-scale v1.5
**Executor skill:** executor-subtask-execution

> Continuation of halted T10. Do not re-run packets/T10.md. Closes audit F1 (major). Files-to-touch now includes `tests/test_scraper_adapters_huggingface.py`. Consume the existing uncommitted T10 working-tree partial — do not discard it. Do not re-dispatch T1, T2, T8, T8-bis, or T10. Do not touch `SEMANTIC_SCHOLAR_API_KEY`, `GITHUB_TOKEN`, or any other already-landed token row.

---

## 1. Task statement

**(a)** Active milestone ID: M8 — Hardening and Scale

**(b)** Charter version: `.dev/bishop_program_charter.md` v0.1.0

**(c)** Charter non-goals (verbatim): All §23 deferred items (graph layer, daily digest, cosine anchor migration, personal domain, cross-domain query, reranker, query expansion, local enrichment path, time-decayed weights, reading history analytics, Redis/Postgres upgrades). All §24 rejected items. `DomainEnum.both` (removed).

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
- **v1.4 (amendment-3):** Do not re-dispatch T1, T2, T8, or any earlier halted/superseded/landed node. Do not touch `SEMANTIC_SCHOLAR_API_KEY`, `GITHUB_TOKEN`, or any other already-landed token row.
- **v1.5 (amendment-4):** Do not re-dispatch T10. Do not discard T10's uncommitted working-tree partial.

**Charter row dispositions:**

| Charter row | Disposition |
|-------------|-------------|
| `ADAPTER_REGISTRY` expanded (HF, PwC, SS, GitHub, OpenReview, LessWrong if verified) | §2 `ADAPTER_REGISTRY` (T8-bis module / T9 test coverage) + T2–T4 adapter rows |
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
| `HUGGINGFACE_TOKEN` | **T10-bis** (T10 halted 2026-09-11: Files-to-touch omitted `tests/test_scraper_adapters_huggingface.py`) | `services/scraper/app/config.py` — optional `str \| None` via `_optional_str_from_env`, same shape as `GITHUB_TOKEN`/`SEMANTIC_SCHOLAR_API_KEY` | `tests/test_scraper_config.py::test_huggingface_token_from_env` + `test_huggingface_token_default_none` + `tests/test_scraper_adapters_huggingface.py::test_fetch_manifest_sends_huggingface_token_header` |
| `HuggingFaceAdapter` | T2 | `services/scraper/app/adapters/huggingface.py` — `fetch_manifest` + `fetch_content` | `tests/test_scraper_adapters_huggingface.py` |
| `PapersWithCodeAdapter` | T2 | `services/scraper/app/adapters/paperswithcode.py` | `tests/test_scraper_adapters_paperswithcode.py` |
| `SemanticScholarAdapter` | T3 | `services/scraper/app/adapters/semantic_scholar.py` | `tests/test_scraper_adapters_semantic_scholar.py` |
| `GitHubAdapter` | T3 | `services/scraper/app/adapters/github.py` | `tests/test_scraper_adapters_github.py` |
| `OpenReviewAdapter` | T4 | `services/scraper/app/adapters/openreview.py` | `tests/test_scraper_adapters_openreview.py` |
| `LessWrongAdapter` | T4 | `services/scraper/app/adapters/lesswrong.py` — conditional registry | `tests/test_scraper_adapters_lesswrong.py` (skip if probe fails) |
| `ADAPTER_REGISTRY` | T8-bis (module landed) / T9 (test coverage — audit F2) | `services/scraper/app/adapters/registry.py` — ArXiv + landed T2–T4 adapters (LessWrong if verified) | `tests/test_scraper_loop.py::test_registry_lists_all_expected_sources` + `tests/test_scraper_adapters.py`'s rewritten registry assertion |
| `ReadingStatusPatchRequest` | T5 | `services/state-worker/app/models/http.py` | `tests/test_state_worker_reading_status.py` |
| `PATCH /entries/{source_id}/reading-status` | T5 | state-worker entries router | `tests/test_state_worker_reading_status.py` |
| `PermanentFailPostRequest` | T5 | `services/state-worker/app/models/http.py` | `tests/test_state_worker_permanent_fail.py` |
| `POST /entries/permanent-fail` | T5 | state-worker entries router | `tests/test_state_worker_permanent_fail.py` |
| `POST /entries/{source_id}/retry` | T6 | query-api proxy → state-worker `POST /entries/retry` | `tests/test_query_api_routes_entry_actions.py` |
| `POST /entries/{source_id}/permanent-fail` | T6 | query-api proxy | `tests/test_query_api_routes_entry_actions.py` |
| `PATCH /entries/{source_id}/reading-status` | T6 | query-api proxy | `tests/test_query_api_routes_entry_actions.py` |
| UI `/escalations` | T6 | `services/ui/app/main.py` + templates | `tests/test_ui_escalations.py` |
| UI `/explorer` | T6 | DB explorer filter page | `tests/test_ui_explorer.py` |
| `scripts/verify-m8.sh` | T8-bis (script landed) / T11 (gate-completeness extension — audit F3) | M8 pytest gate script. Must not set `BISHOP_G6_MANUAL=1`. | `tests/test_verify_m8.py` (extended by T11) |
| G5 quality harness | LANDED (M6) — T7 consumes | `tests/test_g5_quality_gate.py` (frozen) | existing `test_g5_quality_gate_fixture` / `test_g5_fixture_queries_count` — do not rewrite |
| G6 prefilter gold | LANDED — T7 consumes | `eval/prefilter_v1/contract.json` + `items.json` + `labels.json` + `scripts/replay_prefilter.py` | T7 `tests/test_g6_prefilter_gold.py` — do not rebuild gold |
| G6 enrichment sampling | T7 (template) + T8-bis (waiver consume) | `.dev/quality/g6-enrichment-template.md` + `tests/test_g6_enrichment_sampling.py` + `scripts/run-g6-enrichment-sampling.sh` | **Landed:** 7/10 both-true; hooks reject `arxiv:2606.09483`, `arxiv:2608.14509`, `arxiv:2606.27330`. Owner waiver — do not flip flags. |
| `index_policy` | LANDED — M8 non-goal | `config/index_policy.yaml` + `bishop_shared/index_policy.py` | existing `tests/test_index_policy.py` — do not modify |
| `apply_category_gate` / `SourceCategoryConfig` | LANDED — M8 non-goal | `bishop_shared/source_config.py` + `arxiv.py::apply_category_gate` | existing `tests/test_scraper_arxiv_adapter.py` — must not remove or bypass |
| Gate-split profile pins | LANDED — M8 non-goal | `profile_renderer.py` `_PROFILE_FILENAME` | existing `tests/test_profile_renderer.py` — do not modify |
| Frozen-adjacent paths | T1-bis, T7, T8-bis | Byte-unchanged from baseline SHA `5e048337b9b7262c604dfce04f3e565d33cf0f4a` through M8 closure. Paths: `config/index_policy.yaml`, `bishop_shared/index_policy.py`, `config/sources/arxiv.yaml`, `bishop_shared/source_config.py`, `bishop_shared/profile_renderer.py`, `config/profiles/professional_v1.2.0.yaml`, `config/profiles/professional_v1.0.0.yaml`, `eval/prefilter_v1/contract.json`, `eval/prefilter_v1/items.json`, `eval/prefilter_v1/labels.json`, `scripts/replay_prefilter.py`, `scripts/build_eval_v1.py`, `scripts/apply_adjudication.py`, `tests/test_index_policy.py`, `tests/test_g5_quality_gate.py` | `git diff 5e048337b9b7262c604dfce04f3e565d33cf0f4a -- <paths>` empty |
| Call 1 `challenge_hooks` prompt iteration | deferred | `bishop_shared/enrichment_prompts.py` `build_call1_system_prompt` | Follow-up ID `g6-call1-hooks-iteration` (post-M8). Must not edit prompts or `professional_v1.0.0.yaml`. |

**Decision log paths (architectural):**
- T1: `.dev/decision-logs/m8-hardening-scale/T1-adapter-foundation.md`
- T4: `.dev/decision-logs/m8-hardening-scale/T4-openreview-lesswrong.md`
- T5: `.dev/decision-logs/m8-hardening-scale/T5-state-worker-ops.md`
- T8 / T8-bis: `.dev/decision-logs/m8-hardening-scale/T8-backfill-enable.md`

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
- Compose image tags: `bishop/scraper:m8`, `bishop/ui:m8`. **v1.4 Landed (T12 — audit F4):** T12 owns `docker-compose.yml` and `tests/test_compose.py` together.
- Env prefix: `BISHOP_` for backfill toggles; source tokens `GITHUB_TOKEN`, `SEMANTIC_SCHOLAR_API_KEY`, `HUGGINGFACE_TOKEN`

### Logging

- Structured `extra` fields: `event`, `source`, `source_id` on adapter fetch, backfill chunk boundaries, escalation actions
- Backfill chunk start/complete: `INFO` with `chunk_start`, `chunk_end`, `source`
- Permanent-fail / manual retry from UI: `INFO` `manual_permanent_fail`, `manual_retry` with `source_id`

### Tests

- Framework: pytest (existing repo convention)
- Location: `tests/test_scraper_adapters_*.py`, `tests/test_state_worker_*.py`, `tests/test_query_api_routes_entry_actions.py`, `tests/test_ui_*.py`, `tests/test_g6_prefilter_gold.py`, `tests/test_g6_enrichment_sampling.py`, `tests/test_verify_m8.py`. Do **not** add `tests/test_g6_quality_sampling.py`.
- Adapter tests: HTTP mocked via `respx` or `httpx.MockTransport` — no live network in default CI
- Optional live probes: `BISHOP_LESSWRONG_PROBE_LIVE=1`, `BISHOP_G5_LIVE=1` (heavy), `BISHOP_G6_MANUAL=1` (expected-fail; not a verify-m8 input)
- M8 gate: `scripts/verify-m8.sh` — subprocess isolation pattern from `verify-m7.sh` for `app` package collision hygiene.
- **v1.5:** `test_fetch_manifest_sends_huggingface_token_header` must `monkeypatch.setattr(hf, "HUGGINGFACE_TOKEN", ...)` after `_load_hf_stack()`, mirroring `tests/test_scraper_adapters_github.py::test_fetch_manifest_sends_bearer_token`. Post-import `setenv` is the T10 failure mode.

### CLI surface

- Existing `bishop escalations` (M7) unchanged
- No new CLI subcommands required for M8 exit gate
- Frozen in T7 before T8: `scripts/run-g5-quality-gate.sh`, `scripts/run-g6-prefilter-replay.sh`, `scripts/run-g6-enrichment-sampling.sh`
- **Retired (v1.0):** `scripts/run-g6-quality-sampling.sh` — do not create

---

### T10-bis — HUGGINGFACE_TOKEN typed config (amendment-4)

| Field | Content |
|--------|---------|
| **ID** | T10-bis |
| **Scope** | Continue halted T10. Close audit F1: land typed `HUGGINGFACE_TOKEN` via `_optional_str_from_env`, switch `huggingface.py::_auth_headers()` off raw env read, add the two config tests, **and** update `tests/test_scraper_adapters_huggingface.py::test_fetch_manifest_sends_huggingface_token_header` to `monkeypatch.setattr(hf, "HUGGINGFACE_TOKEN", ...)` after `_load_hf_stack()` — mirror `tests/test_scraper_adapters_github.py::test_fetch_manifest_sends_bearer_token`. Consume the existing uncommitted T10 working-tree diff; do not discard it. Re-append the CHANGELOG bullet (T10's was lost to parallel T9/T12 commits). |
| **Files to touch** | `services/scraper/app/config.py`, `services/scraper/app/adapters/huggingface.py`, `tests/test_scraper_config.py`, `tests/test_scraper_adapters_huggingface.py`, `CHANGELOG.MD` |
| **Contract bindings** | `HUGGINGFACE_TOKEN` §2 row (reassigned T10 → T10-bis) |
| **Inputs** | T10 HALT brief `.dev/plans/m8-hardening-scale/runs/T10-brief.md`; uncommitted working-tree partial on the three source/config/test-config files. T10 produced no commit. |
| **Outputs** | Typed constant + adapter switch + config tests + header-test setattr, one commit |
| **Kill criteria** | **HALT if `huggingface.py` still reads `os.environ.get("HUGGINGFACE_TOKEN")` (or any raw env access for this token).** HALT if `HUGGINGFACE_TOKEN` is typed as anything other than optional `str \| None`. HALT if `test_huggingface_token_from_env` and `test_huggingface_token_default_none` do not both exist and pass. **HALT if `test_fetch_manifest_sends_huggingface_token_header` still uses post-import `monkeypatch.setenv("HUGGINGFACE_TOKEN", ...)`** — that is the T10 failure mode; the test must patch `hf.HUGGINGFACE_TOKEN` after load. HALT if this subtask edits `SEMANTIC_SCHOLAR_API_KEY`, `GITHUB_TOKEN`, or any other already-landed token row. HALT if `git diff` on this subtask's commit touches any file outside this subtask's Files-to-touch. |
| **Log tier** | standard |
| **Model class** | standard — same pattern as T10 plus one-line GitHub-precedent test fix |
| **Risks & mitigations** | Risk: discarding T10's uncommitted typed-surface diff and re-deriving it would fork the same-commit invariant — consume the working tree. Risk: `setenv` left in place while only config tests pass — header-test kill above. |

---

## Filtered 5.2 (T10-bis)

- (HUGGINGFACE_TOKEN's typed surface must land in the same commit as the adapter call-site switch, not typed-only | services/scraper/app/config.py + adapters/huggingface.py::_auth_headers | T10 lands the constant but leaves the adapter reading os.environ.get directly, reproducing F1's exact shape | T10) invariant — operator-locked; v1.5 live owner T10-bis
- (HF adapter header test must patch the imported module constant, not post-import setenv | tests/test_scraper_adapters_huggingface.py::test_fetch_manifest_sends_huggingface_token_header + tests/test_scraper_adapters_github.py::test_fetch_manifest_sends_bearer_token | T10-bis leaves setenv in place and the header test fails with empty Authorization | T10-bis) invariant — operator-locked

## Filtered 5.4 (T10-bis)

- (HUGGINGFACE_TOKEN typed surface and the huggingface.py call-site switch must land in the same commit | services/scraper/app/config.py + adapters/huggingface.py | HF requests run unauthenticated mid-migration if split across commits | T10) confirmed — Bound: T10 kill. v1.5 live owner T10-bis
- (HF header test patches hf.HUGGINGFACE_TOKEN after _load_hf_stack, not setenv | tests/test_scraper_adapters_huggingface.py | module-level import binds None; setenv is a no-op | T10-bis) confirmed — Bound: T10-bis kill

## Resolved inputs

- T10 HALT brief: `.dev/plans/m8-hardening-scale/runs/T10-brief.md`
- Uncommitted T10 partial (do not discard): `services/scraper/app/config.py`, `services/scraper/app/adapters/huggingface.py`, `tests/test_scraper_config.py`
- Precedent: `tests/test_scraper_adapters_github.py::test_fetch_manifest_sends_bearer_token` uses `monkeypatch.setattr(gh, "GITHUB_TOKEN", ...)` after `_load_github_stack()`
- T10 CHANGELOG bullet is **not** on disk (lost to T9/T12 parallel commits) — re-append as T10-bis
