"""UI service configuration."""

from __future__ import annotations

import os

from bishop_shared.constants import QUERY_API_HOST_PORT

QUERY_API_URL = os.environ.get("QUERY_API_URL", f"http://localhost:{QUERY_API_HOST_PORT}")
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
