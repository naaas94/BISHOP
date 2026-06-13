#!/usr/bin/env bash
# M7 verification gate: G2 contract slice plus read-path unit and integration tests.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

log() {
  echo "[verify-m7] $*"
}

fail() {
  echo "[verify-m7] ERROR: $*" >&2
  exit 1
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || fail "required command not found: $1"
}

require_cmd python

if ! python -m pytest --version >/dev/null 2>&1; then
  fail "pytest is not available (install project dev dependencies)"
fi

log "Running G2 contract pytest slice"
python -m pytest \
  tests/test_state_worker_contract.py \
  tests/test_state_worker_health.py \
  tests/test_constants.py \
  -v \
  --tb=short

log "Running M7 pydantic models (isolated subprocess — app package collision guard)"
python -m pytest \
  tests/test_query_api_models.py \
  -v \
  --tb=short

log "Running M7 integration gate (isolated subprocess — app package collision guard)"
python -m pytest \
  tests/test_m7_integration.py \
  -v \
  --tb=short

log "Running M7 unit pytest suite"
python -m pytest \
  tests/test_verify_m7.py \
  tests/test_query_config.py \
  tests/test_bm25_tokenize.py \
  tests/test_query_api_bm25_reader.py \
  tests/test_query_api_lancedb_reader.py \
  tests/test_query_api_duckdb_reader.py \
  tests/test_query_api_embedding.py \
  tests/test_problem_shaped.py \
  tests/test_rrf.py \
  tests/test_query_api_routes_search.py \
  tests/test_query_api_routes_recent.py \
  tests/test_query_api_routes_entry.py \
  tests/test_query_api_routes_batches.py \
  tests/test_query_api_routes_escalations.py \
  tests/test_query_api_cold_start.py \
  tests/test_query_api_search_orchestrator.py \
  tests/test_bishop_cli.py \
  tests/test_bishop_cli_config.py \
  tests/test_ui_config.py \
  tests/test_ui_routes.py \
  -v \
  --tb=short

if [ "${BISHOP_M7_REQUIRE_GATES:-0}" = "1" ]; then
  log "Running optional live G5 gate (BISHOP_M7_REQUIRE_GATES=1)"
  BISHOP_G5_LIVE=1 python -m pytest tests/test_g5_quality_gate.py -m heavy -v --tb=short
fi

log "M7 verification passed"
log "Charter G4/G5/G6: manual sign-off before production; optional strict gate via BISHOP_M7_REQUIRE_GATES=1"
log "Optional live G5 gate: BISHOP_G5_LIVE=1 pytest tests/test_g5_quality_gate.py -m heavy"
