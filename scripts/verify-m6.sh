#!/usr/bin/env bash
# M6 verification gate: G2 contract slice plus indexing unit and integration tests.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

log() {
  echo "[verify-m6] $*"
}

fail() {
  echo "[verify-m6] ERROR: $*" >&2
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

log "Running M6 unit and integration pytest suite (fixture G5; heavy live gate excluded)"
python -m pytest \
  tests/test_verify_m6.py \
  tests/test_indexing_config.py \
  tests/test_atomic_persist.py \
  tests/test_lancedb_store.py \
  tests/test_bm25_store.py \
  tests/test_duckdb_mirror.py \
  tests/test_vector_writer_config.py \
  tests/test_vector_writer_models.py \
  tests/test_vector_writer_embedding.py \
  tests/test_vector_writer_index_entry.py \
  tests/test_vector_writer_loop.py \
  tests/test_bm25_lock_contention.py \
  tests/test_duckdb_concurrent_read.py \
  tests/test_g5_quality_gate.py \
  tests/test_m6_integration.py \
  -v \
  --tb=short \
  -m "not heavy"

log "M6 verification passed"
log "Optional live G5 gate: BISHOP_G5_LIVE=1 pytest tests/test_g5_quality_gate.py -m heavy"
