#!/usr/bin/env bash
# G5 embedding quality gate — fixture (CI) and optional live probe (M6/M8).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

log() {
  echo "[run-g5-quality-gate] $*"
}

fail() {
  echo "[run-g5-quality-gate] ERROR: $*" >&2
  exit 1
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || fail "required command not found: $1"
}

require_cmd python

if ! python -m pytest --version >/dev/null 2>&1; then
  fail "pytest is not available (install project dev dependencies)"
fi

log "Running G5 fixture gate (mocked vectors; heavy live gate excluded)"
python -m pytest \
  tests/test_g5_quality_gate.py::test_g5_fixture_queries_count \
  tests/test_g5_quality_gate.py::test_g5_quality_gate_fixture \
  -v \
  --tb=short \
  -m "not heavy"

if [ "${BISHOP_G5_LIVE:-0}" = "1" ]; then
  log "Running optional live G5 gate (BISHOP_G5_LIVE=1)"
  BISHOP_G5_LIVE=1 python -m pytest tests/test_g5_quality_gate.py -m heavy -v --tb=short
fi

log "G5 quality gate passed (fixture)"
log "Optional live gate: BISHOP_G5_LIVE=1 ${0}"
