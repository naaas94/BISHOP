#!/usr/bin/env bash
# M8 verification gate: adapter registry, backfill chunking, and G5/G6 quality gates.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

log() {
  echo "[verify-m8] $*"
}

fail() {
  echo "[verify-m8] ERROR: $*" >&2
  exit 1
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || fail "required command not found: $1"
}

require_cmd python

if ! python -m pytest --version >/dev/null 2>&1; then
  fail "pytest is not available (install project dev dependencies)"
fi

log "Running M8 scraper adapter, registry, config, and backfill-chunking pytest suite"
python -m pytest \
  tests/test_scraper_adapters_huggingface.py \
  tests/test_scraper_adapters_paperswithcode.py \
  tests/test_scraper_adapters_semantic_scholar.py \
  tests/test_scraper_adapters_github.py \
  tests/test_scraper_adapters_openreview.py \
  tests/test_scraper_adapters_lesswrong.py \
  tests/test_scraper_adapters.py \
  tests/test_scraper_loop.py \
  tests/test_scraper_backfill_chunking.py \
  tests/test_scraper_config.py \
  -v \
  --tb=short

log "Running M8 state-worker ops pytest suite"
python -m pytest \
  tests/test_state_worker_reading_status.py \
  tests/test_state_worker_permanent_fail.py \
  -v \
  --tb=short

log "Running M8 query-api and UI pytest suite"
python -m pytest \
  tests/test_query_api_routes_entry_actions.py \
  tests/test_ui_escalations.py \
  tests/test_ui_explorer.py \
  -v \
  --tb=short

log "Running G5 quality gate (fixture; optional live probe via BISHOP_G5_LIVE=1)"
bash scripts/run-g5-quality-gate.sh

log "Running G6 prefilter gold binding (landed eval/prefilter_v1, not a rebuilt CSV scaffold)"
python -m pytest tests/test_g6_prefilter_gold.py -v --tb=short

log "Running G6 enrichment structural gate (manual all-true checklist NOT invoked by this script)"
python -m pytest \
  tests/test_g6_enrichment_sampling.py::test_g6_enrichment_template_schema \
  tests/test_g6_enrichment_sampling.py::test_g6_enrichment_template_entry_slots \
  -v \
  --tb=short

log "Running verify-m8 gate self-test"
python -m pytest tests/test_verify_m8.py -v --tb=short

log "M8 verification passed (structural)."
log "G6 enrichment: assessed 7/10 in .dev/quality/g6-enrichment-template.md (three challenge_hooks rejects kept, owner-waived 2026-09-10)."
log "The BISHOP_G6_MANUAL operator checklist (all-true) is expected-fail and intentionally not run by this script."
log "Optional live G5 gate: BISHOP_G5_LIVE=1 ${0}"
