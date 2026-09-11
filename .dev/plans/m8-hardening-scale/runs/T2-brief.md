# T2 brief

**Subtask ID:** T2  
**Status:** complete  
**Files changed:** `services/scraper/app/adapters/huggingface.py`, `services/scraper/app/adapters/paperswithcode.py`, `services/scraper/app/adapters/registry.py` (import-only), `tests/test_scraper_adapters_huggingface.py`, `tests/test_scraper_adapters_paperswithcode.py`, `CHANGELOG.MD`  
**Tests run:** 29 passed (HF/PwC adapters + arxiv/adapter regression)  
**Commit SHA:** `7a836cb`  
**Changelog:** `CHANGELOG.MD` · `## m8-hardening-scale — 2026-09-10`  
**Decision log:** none  
**Kill-criterion evidence:** HF Hub URL cited from spec §3.1 L90; flag 1 N/A.  
**Summary:** HuggingFace and PapersWithCode adapters landed with mocked HTTP tests. Registry staging import-only; ADAPTER_REGISTRY merge left to T8. HUGGINGFACE_TOKEN typed config row deferred (Files-to-touch).
