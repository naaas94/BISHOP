#!/usr/bin/env bash
# G6 prefilter gold replay — wraps landed scripts/replay_prefilter.py (API key required).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

log() {
  echo "[run-g6-prefilter-replay] $*"
}

fail() {
  echo "[run-g6-prefilter-replay] ERROR: $*" >&2
  exit 1
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || fail "required command not found: $1"
}

require_cmd python

DEFAULT_PROFILE="config/profiles/professional_v1.2.0.yaml"
DEFAULT_EVAL="eval/prefilter_v1"

if [ "$#" -eq 0 ]; then
  log "No args — defaulting to pinned prefilter profile ${DEFAULT_PROFILE}"
  set -- --profile "${DEFAULT_PROFILE}" --eval "${DEFAULT_EVAL}"
fi

exec python scripts/replay_prefilter.py "$@"
