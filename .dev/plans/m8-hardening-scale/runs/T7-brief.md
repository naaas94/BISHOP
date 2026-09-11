# T7 brief

**Subtask ID:** T7  
**Status:** complete  
**Files changed:** `scripts/run-g5-quality-gate.sh`, `scripts/run-g6-prefilter-replay.sh`, `scripts/run-g6-enrichment-sampling.sh`, `tests/test_g6_prefilter_gold.py`, `tests/test_g6_enrichment_sampling.py`, `.dev/quality/g6-enrichment-template.md`, `CHANGELOG.MD`  
**Tests run:** 9 passed, 1 skipped (`BISHOP_G6_MANUAL` unset)  
**Commit SHA:** `b064f72`  
**Changelog:** `CHANGELOG.MD` · `## m8-hardening-scale — 2026-09-10`  
**Decision log:** none  
**Kill-criterion evidence:** Gold artifacts + count ≥ 129; replay importable; no retired v1.0 paths; frozen gold/G5/index_policy/pins untouched.  
**Summary:** Bound landed G5 fixture and 129-item prefilter gold; added enrichment 10-entry template. Manual G6 enrichment checklist remains for T8.
