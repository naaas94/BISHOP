#!/usr/bin/env bash
# Create host volume directories under BISHOP_DATA_ROOT (spec §8.5).
set -euo pipefail

ROOT="${BISHOP_DATA_ROOT:-$HOME/bishop_data}"

mkdir -p \
  "${ROOT}/sqlite" \
  "${ROOT}/lancedb" \
  "${ROOT}/duckdb" \
  "${ROOT}/bm25" \
  "${ROOT}/profiles" \
  "${ROOT}/logs"

echo "Bishop volume directories ready under: ${ROOT}"
