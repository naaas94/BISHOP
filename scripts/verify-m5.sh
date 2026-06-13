#!/usr/bin/env bash
# M5 verification gate: G2 contract slice plus enrichment unit and integration tests.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

log() {
  echo "[verify-m5] $*"
}

fail() {
  echo "[verify-m5] ERROR: $*" >&2
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

log "Running M5 unit and integration pytest suite"
python -m pytest \
  tests/test_verify_m5.py \
  tests/test_anthropic_config.py \
  tests/test_enrichment_truncation.py \
  tests/test_tag_taxonomy.py \
  tests/test_enrichment_prompts.py \
  tests/test_enrichment_parsers.py \
  tests/test_state_worker_enrichment_hub.py \
  tests/test_enrichment_batcher_config.py \
  tests/test_enrichment_batcher_stage1_loop.py \
  tests/test_enrichment_batcher_stage2_loop.py \
  tests/test_batch_poller_startup.py \
  tests/test_batch_poller_enrichment.py \
  tests/test_batch_poller_loop.py \
  tests/test_m5_integration.py \
  -v \
  --tb=short

log "M5 verification passed"
