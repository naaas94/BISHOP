#!/usr/bin/env bash
# Copy repo NL profiles into BISHOP_DATA_ROOT when host volume is empty (M3 C1).
set -euo pipefail

ROOT="${BISHOP_DATA_ROOT:-$HOME/bishop_data}"
DEST="${ROOT}/profiles"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="${REPO_ROOT}/config/profiles"

mkdir -p "${DEST}"

if [ -z "$(find "${DEST}" -mindepth 1 -maxdepth 1 2>/dev/null || true)" ]; then
  cp -r "${SRC}/." "${DEST}/"
  echo "Seeded profiles into: ${DEST}"
else
  echo "Profiles directory not empty, skipping seed: ${DEST}"
fi
