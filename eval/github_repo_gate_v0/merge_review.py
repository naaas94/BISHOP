"""Merge corpus + agent proposal batches into proposals.json and review.html."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def load_proposals() -> dict[str, dict]:
    by_id: dict[str, dict] = {}
    for path in sorted((ROOT / "proposals").glob("batch_*.json")):
        if path.name.endswith("_input.json"):
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        for item in data.get("items", []):
            sid = item.get("source_id")
            if sid:
                by_id[sid] = item
    return by_id


def main() -> None:
    corpus = json.loads((ROOT / "corpus.json").read_text(encoding="utf-8"))
    proposals = load_proposals()
    merged_items = []
    missing = []
    for item in corpus["items"]:
        sid = item["source_id"]
        proposal = proposals.get(sid)
        if proposal is None:
            missing.append(sid)
            proposal = {
                "source_id": sid,
                "agent_verdict": "unsure",
                "confidence": "low",
                "why": "No agent proposal for this row yet.",
                "signals": [],
                "citations": [],
            }
        merged_items.append({**item, "proposal": proposal})

    proposals_out = {
        "eval_id": "github_repo_gate_v0",
        "merged_at": datetime.now(UTC).isoformat(),
        "count": len(proposals),
        "missing_proposals": missing,
        "items": list(proposals.values()),
    }
    (ROOT / "proposals.json").write_text(
        json.dumps(proposals_out, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    packet = {
        "eval_id": "github_repo_gate_v0",
        "question": corpus["question"],
        "exported_at": corpus["exported_at"],
        "merged_at": proposals_out["merged_at"],
        "count": len(merged_items),
        "missing_proposals": missing,
        "items": merged_items,
    }
    (ROOT / "packet.json").write_text(
        json.dumps(packet, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    html_path = ROOT / "review.html"
    js_path = ROOT / "packet.js"
    injected = json.dumps(packet, ensure_ascii=False)
    js_path.write_text(
        "window.BISHOP_PACKET = " + injected + ";\n",
        encoding="utf-8",
    )
    print(
        "proposals",
        len(proposals),
        "missing",
        len(missing),
        "items",
        len(merged_items),
        "html_bytes",
        html_path.stat().st_size,
        "packet_js_bytes",
        js_path.stat().st_size,
    )


if __name__ == "__main__":
    main()
