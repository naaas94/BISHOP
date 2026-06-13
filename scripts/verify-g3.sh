#!/usr/bin/env bash
# G3 verification gate (M3): live Anthropic Messages API probe for pinned pre-filter model.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

log() {
  echo "[verify-g3] $*"
}

fail() {
  echo "[verify-g3] ERROR: $*" >&2
  exit 1
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || fail "required command not found: $1"
}

require_cmd python

if ! python -m pytest --version >/dev/null 2>&1; then
  fail "pytest is not available (install project dev dependencies)"
fi

log "Running G3 unit tests (mocked Anthropic client)"
python -m pytest tests/test_anthropic_config.py tests/test_verify_g3.py -v --tb=short

if [ -z "${ANTHROPIC_API_KEY:-}" ]; then
  log "SKIP: ANTHROPIC_API_KEY not set — live G3 model verification skipped (CI-safe)"
  exit 0
fi

log "Live G3 probe: model ${ANTHROPIC_MODEL_PREFILTER:-claude-haiku-4-5-20251001}"
if ! python - <<'PY'
from bishop_shared.anthropic_config import ANTHROPIC_MODEL_PREFILTER, verify_model_string
import sys

EXPECTED = "claude-haiku-4-5-20251001"
if ANTHROPIC_MODEL_PREFILTER != EXPECTED:
    print(
        f"ANTHROPIC_MODEL_PREFILTER mismatch: {ANTHROPIC_MODEL_PREFILTER!r} != {EXPECTED!r}",
        file=sys.stderr,
    )
    sys.exit(1)

if not verify_model_string():
    print(
        f"Anthropic Messages API returned HTTP 400 for model {ANTHROPIC_MODEL_PREFILTER!r}",
        file=sys.stderr,
    )
    sys.exit(1)
PY
then
  fail "G3 model string verification failed — M3 Anthropic work blocked"
fi

log "G3 verification passed"
