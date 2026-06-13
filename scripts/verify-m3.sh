#!/usr/bin/env bash
# M3 verification gate: G2 contract slice, G3 model string (mocked or live), M3 unit tests.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

log() {
  echo "[verify-m3] $*"
}

fail() {
  echo "[verify-m3] ERROR: $*" >&2
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

log "Running G3 model-string gate (mocked; live probe when ANTHROPIC_API_KEY set)"
"${SCRIPT_DIR}/verify-g3.sh"

log "Running M3 unit and integration pytest suite"
python -m pytest \
  tests/test_verify_m3.py \
  tests/test_profile_renderer.py \
  tests/test_prefilter_*.py \
  tests/test_batch_poller_*.py \
  tests/test_state_worker_batches_register.py \
  tests/test_m3_integration.py \
  -v \
  --tb=short

log "M3 verification passed"
