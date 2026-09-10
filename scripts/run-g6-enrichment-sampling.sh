#!/usr/bin/env bash
# G6 enrichment quality sampling — structural template gate (CI) + optional manual checklist.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

log() {
  echo "[run-g6-enrichment-sampling] $*"
}

fail() {
  echo "[run-g6-enrichment-sampling] ERROR: $*" >&2
  exit 1
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || fail "required command not found: $1"
}

require_cmd python

if ! python -m pytest --version >/dev/null 2>&1; then
  fail "pytest is not available (install project dev dependencies)"
fi

log "Running G6 enrichment template structural gate"
python -m pytest \
  tests/test_g6_enrichment_sampling.py::test_g6_enrichment_template_schema \
  tests/test_g6_enrichment_sampling.py::test_g6_enrichment_template_entry_slots \
  -v \
  --tb=short

if [ "${BISHOP_G6_MANUAL:-0}" = "1" ]; then
  log "Running operator enrichment checklist (BISHOP_G6_MANUAL=1)"
  BISHOP_G6_MANUAL=1 python -m pytest \
    tests/test_g6_enrichment_sampling.py::test_g6_enrichment_manual_checklist \
    -v \
    --tb=short
else
  log "Manual checklist skipped — set BISHOP_G6_MANUAL=1 after filling .dev/quality/g6-enrichment-template.md"
fi

log "G6 enrichment sampling gate passed (structural)"
