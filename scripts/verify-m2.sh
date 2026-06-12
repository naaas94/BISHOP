#!/usr/bin/env bash
# M2 verification gate: G2 contract tests plus scraper unit tests (no live ArXiv).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

log() {
  echo "[verify-m2] $*"
}

fail() {
  echo "[verify-m2] ERROR: $*" >&2
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

log "Running M2 scraper pytest suite"
python -m pytest \
  tests/test_scraper_*.py \
  tests/test_shared_enums.py \
  -v \
  --tb=short

log "M2 verification passed"
