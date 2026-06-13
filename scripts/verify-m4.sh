#!/usr/bin/env bash
# M4 verification gate: G2 contract slice plus content-scraper unit and integration tests.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

log() {
  echo "[verify-m4] $*"
}

fail() {
  echo "[verify-m4] ERROR: $*" >&2
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

log "Running M4 unit and integration pytest suite"
python -m pytest \
  tests/test_verify_m4.py \
  tests/test_arxiv_fetch_content.py \
  tests/test_content_scraper_*.py \
  tests/test_m4_provenance_contract.py \
  tests/test_m4_integration.py \
  -v \
  --tb=short

log "M4 verification passed"
