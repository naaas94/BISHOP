"""Export live INDEXED github entries for the repo-gate spotcheck (read-only)."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

DB = Path("C:/Users/Ale/bishop_data/sqlite_live/bishop.db")
OUT = Path(__file__).resolve().parent / "corpus.json"
EXCERPT_CHARS = 2200
BATCH_SIZE = 16


def excerpt(text: str | None) -> str:
    if not text:
        return ""
    cleaned = text.replace("\r\n", "\n").strip()
    if len(cleaned) <= EXCERPT_CHARS:
        return cleaned
    return cleaned[:EXCERPT_CHARS].rstrip() + "\n…[truncated]"


def decode_json(value: object) -> object:
    if isinstance(value, str) and value[:1] in "[{":
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def main() -> None:
    uri = f"file:{DB.as_posix()}?mode=ro"
    con = sqlite3.connect(uri, uri=True)
    con.row_factory = sqlite3.Row
    rows = list(
        con.execute(
            """
            SELECT source_id, title, url, published_at, ingested_at,
                   relevance_score, relevance_reason, value_rationale,
                   entry_type, tags, concepts, challenge_hooks, summary,
                   pre_filter_rationale, pre_filter_tier, content_raw
            FROM entries
            WHERE source_id LIKE 'github:%' AND processing_state = 'INDEXED'
            ORDER BY relevance_score DESC, source_id
            """
        )
    )
    items = []
    for row in rows:
        d = dict(row)
        items.append(
            {
                "source_id": d["source_id"],
                "title": d["title"],
                "url": d["url"],
                "github_url": f"https://github.com/{d['source_id'].split(':', 1)[1]}",
                "bishop_ui": f"http://localhost:8081/entries/{d['source_id']}",
                "published_at": d["published_at"],
                "ingested_at": d["ingested_at"],
                "relevance_score": d["relevance_score"],
                "relevance_reason": d["relevance_reason"],
                "value_rationale": d["value_rationale"],
                "entry_type": d["entry_type"],
                "tags": decode_json(d["tags"]) or [],
                "concepts": decode_json(d["concepts"]) or [],
                "challenge_hooks": decode_json(d["challenge_hooks"]) or [],
                "summary": d["summary"] or "",
                "pre_filter_rationale": d["pre_filter_rationale"] or "",
                "pre_filter_tier": d["pre_filter_tier"],
                "content_excerpt": excerpt(d["content_raw"]),
            }
        )

    payload = {
        "eval_id": "github_repo_gate_v0",
        "exported_at": datetime.now(UTC).isoformat(),
        "db": str(DB),
        "count": len(items),
        "question": (
            "Would I actually study or steal from this codebase? "
            "keep = yes; junk = on-topic noise; unsure = cannot tell from excerpt."
        ),
        "do_not": [
            "Do not treat relevance_score as gold",
            "Do not treat pre_filter_rationale as gold",
            "Agent proposals are suggestions only",
        ],
        "items": items,
    }
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    batch_dir = OUT.parent / "proposals"
    batch_dir.mkdir(exist_ok=True)
    for i in range(0, len(items), BATCH_SIZE):
        chunk = items[i : i + BATCH_SIZE]
        n = i // BATCH_SIZE + 1
        path = batch_dir / f"batch_{n:02d}_input.json"
        path.write_text(
            json.dumps({"batch": n, "items": chunk}, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(path.name, len(chunk))
    print("corpus", len(items), "->", OUT)


if __name__ == "__main__":
    main()
