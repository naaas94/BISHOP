"""State-worker runtime configuration (env overrides with typed defaults)."""

import os

RETRY_MAX_ATTEMPTS: int = int(os.environ.get("BISHOP_RETRY_MAX_ATTEMPTS", "3"))
SWEEP_INTERVAL_SEC: int = int(os.environ.get("BISHOP_SWEEP_INTERVAL_SEC", "300"))
STUCK_THRESHOLD_SEC: int = int(os.environ.get("BISHOP_STUCK_THRESHOLD_SEC", "900"))
