"""Bishop CLI configuration — host-side query-api client settings."""

from __future__ import annotations

import os

QUERY_API_BASE_URL = os.environ.get("QUERY_API_BASE_URL", "http://localhost:8080")
