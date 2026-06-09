#!/usr/bin/env bash
# G1 verification gate (M0): compose stack, health, host ports, volume writability.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

if [[ -f .env ]]; then
  set -a
  while IFS= read -r line || [[ -n "${line}" ]]; do
    line="${line//$'\r'/}"
    if [[ "${line}" == $'\ufeff'* ]]; then
      line="${line#$'\ufeff'}"
    fi
    [[ -z "${line}" || "${line}" =~ ^[[:space:]]*# ]] && continue
    export "${line?}"
  done < .env
  set +a
fi

ROOT="${BISHOP_DATA_ROOT:-$HOME/bishop_data}"
if [[ "${ROOT}" == ~* ]]; then
  ROOT="${ROOT/#\~/$HOME}"
fi

QUERY_PORT="${QUERY_API_HOST_PORT:-8080}"
UI_PORT="${UI_HOST_PORT:-8081}"

VOLUME_SUBDIRS=(sqlite lancedb duckdb bm25 profiles logs)
EXPECTED_SERVICES=9
WAIT_ATTEMPTS=60
WAIT_INTERVAL=2

log() {
  echo "[verify-g1] $*"
}

fail() {
  echo "[verify-g1] ERROR: $*" >&2
  exit 1
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || fail "required command not found: $1"
}

require_cmd docker
require_cmd curl
require_cmd bash

if ! docker compose version >/dev/null 2>&1; then
  fail "docker compose is not available (install Docker Desktop or Docker Compose plugin)"
fi

log "Step 1: initialize volume directories"
bash "${SCRIPT_DIR}/init-volumes.sh"

log "Step 2: docker compose up --build -d"
docker compose up --build -d

log "Step 3: wait for ${EXPECTED_SERVICES} running containers (none restarting)"
wait_for_stack() {
  local attempt running restarting
  for ((attempt = 1; attempt <= WAIT_ATTEMPTS; attempt++)); do
    running="$(docker compose ps --status running -q | wc -l | tr -d '[:space:]')"
    restarting="$(docker compose ps --format '{{.State}}' | grep -ci restarting || true)"

    if [[ "${running}" -eq "${EXPECTED_SERVICES}" && "${restarting}" -eq 0 ]]; then
      return 0
    fi

    sleep "${WAIT_INTERVAL}"
  done
  return 1
}

if ! wait_for_stack; then
  docker compose ps
  fail "expected ${EXPECTED_SERVICES} running containers with none restarting"
fi

log "Step 4: state-worker health via in-container curl"
health_body="$(docker compose exec -T state-worker curl -sf "http://localhost:8000/health")"
if [[ "${health_body}" != *"ok"* ]]; then
  fail "state-worker /health body missing ok: ${health_body}"
fi

log "Step 5: query-api reachable on host port ${QUERY_PORT}"
curl -sf "http://localhost:${QUERY_PORT}/" >/dev/null

log "Step 6: ui reachable on host port ${UI_PORT}"
curl -sf "http://localhost:${UI_PORT}/" >/dev/null

log "Step 7: volume writability under ${ROOT}"
for subdir in "${VOLUME_SUBDIRS[@]}"; do
  dir="${ROOT}/${subdir}"
  probe="${dir}/.g1-write-probe"
  if ! echo "g1-probe" >"${probe}"; then
    fail "cannot write probe file in ${dir}"
  fi
  rm -f "${probe}"
done

log "G1 verification passed"
