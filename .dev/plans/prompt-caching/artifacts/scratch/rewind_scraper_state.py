"""One-shot: POST scraper_state.timestamp = now-60d for selected sources."""
from __future__ import annotations

import json
import urllib.request
from datetime import UTC, datetime, timedelta

SOURCES = (
    "arxiv",
    "github",
    "lesswrong",
    "openreview",
    "semantic_scholar",
)
BASE = "http://state-worker:8000"
ts = (datetime.now(UTC) - timedelta(days=60)).isoformat()
body = json.dumps({"timestamp": ts}).encode()

for source in SOURCES:
    req = urllib.request.Request(
        f"{BASE}/scraper-state/{source}",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        print(source, resp.status, ts)
