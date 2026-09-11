## Completion Brief

- **Subtask ID · Status:** T10-bis · **complete**
- **Files changed:** `CHANGELOG.MD`, `services/scraper/app/adapters/huggingface.py`, `services/scraper/app/config.py`, `tests/test_scraper_adapters_huggingface.py`, `tests/test_scraper_config.py`
- **Tests run + result:** `tests/test_scraper_config.py` + `tests/test_scraper_adapters_huggingface.py` — **39 passed**. Mutation-checked `test_fetch_manifest_sends_huggingface_token_header`: restoring `os.environ.get` in `_auth_headers` fails with `'' == 'Bearer hf_test_token'`; mutation reverted, suite re-run green.
- **Commit SHA:** `9f183675d6a713d76c3f822dcabb813f012d5c4d`
- **Changelog entry location:** `CHANGELOG.MD` → `## m8-hardening-scale — 2026-09-10` (T10-bis bullet; T11/T9/T12 left intact)
- **Decision log path:** N/A (standard tier)
- **Kill-criterion evidence:**
 - Adapter no raw env read: `rg 'os.environ.get\("HUGGINGFACE_TOKEN"' services/scraper/app/adapters/huggingface.py` → no matches
 - Typed optional `str | None`: `HUGGINGFACE_TOKEN = _optional_str_from_env("HUGGINGFACE_TOKEN")` (same helper as `GITHUB_TOKEN`)
 - Both config tests exist and pass: `test_huggingface_token_from_env`, `test_huggingface_token_default_none`
 - Header test no post-import setenv: `monkeypatch.setattr(hf, "HUGGINGFACE_TOKEN", "hf_test_token")` after `_load_hf_stack()`; `rg setenv\("HUGGINGFACE_TOKEN"` in that file → no matches
 - No edit to `GITHUB_TOKEN` / `SEMANTIC_SCHOLAR_API_KEY` rows: config diff is the new `HUGGINGFACE_TOKEN` line only
 - Commit confined to Files-to-touch: `git show --name-only -1` lists exactly the five paths above
- **Summary:** Consumed T10’s uncommitted typed-surface partial and closed audit F1 in one commit: `HUGGINGFACE_TOKEN` is a typed optional env constant, `HuggingFaceAdapter._auth_headers()` imports that constant instead of reading the environment, the two config tests stay, and the header test now patches `hf.HUGGINGFACE_TOKEN` after stack load (GitHub precedent). `fetch_content` README Authorization is not separately asserted — deferred to m8 auditor-review with a README GET header-capture observable.
