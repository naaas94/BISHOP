#!/usr/bin/env bash
# G2 verification gate (M1): state-worker contract tests and M0 health compatibility.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

log() {
  echo "[verify-g2] $*"
}

fail() {
  echo "[verify-g2] ERROR: $*" >&2
  exit 1
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || fail "required command not found: $1"
}

require_cmd python

if ! python -m pytest --version >/dev/null 2>&1; then
  fail "pytest is not available (install project dev dependencies)"
fi

log "Running G2 contract pytest suite"
python -m pytest \
  tests/test_state_worker_contract.py \
  tests/test_state_worker_health.py \
  tests/test_constants.py \
  -v \
  --tb=short

log "G2 verification passed"
