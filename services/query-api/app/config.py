"""Query-api service configuration."""

from __future__ import annotations

import os

STATE_WORKER_BASE_URL = os.environ.get("STATE_WORKER_URL", "http://state-worker:8000")
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
