"""Print GitHub search total_count only. Do not print the token."""
from __future__ import annotations

import os
from pathlib import Path

import httpx

token = None
env_path = Path(".env")
if env_path.exists():
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("GITHUB_TOKEN="):
            token = line.split("=", 1)[1].strip().strip('"').strip("'")
            break
token = token or os.environ.get("GITHUB_TOKEN")
if not token:
    raise SystemExit("no GITHUB_TOKEN")

headers = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "Authorization": f"Bearer {token}",
}
queries = [
    "pushed:>2026-07-17 stars:>50",
    "pushed:>2026-09-15 stars:>50",
    "pushed:2026-07-17..2026-07-24 stars:>50",
    "pushed:2026-08-01..2026-08-31 stars:>50",
    "pushed:>2026-07-17 stars:>10",
]
with httpx.Client(timeout=30) as client:
    for q in queries:
        r = client.get(
            "https://api.github.com/search/repositories",
            params={"q": q, "per_page": 1},
            headers=headers,
        )
        r.raise_for_status()
        data = r.json()
        print(f"{data.get('total_count')}\tincomplete={data.get('incomplete_results')}\t{q}")
