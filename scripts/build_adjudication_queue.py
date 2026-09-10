"""Emit the human adjudication queue for a replay: every model/label disagreement.

A replay disagreement is either a model error or a label error, and we cannot tell which
from the aggregate metrics. This writes one reviewable record per disagreement, carrying the
model's own rationale next to the existing human label and note, so the boundary can be
settled by a person instead of guessed at by another prompt edit.

Usage:
  python scripts/build_adjudication_queue.py eval/prefilter_v1/replays/<run>.json
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("replay")
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    replay_path = ROOT / args.replay
    run = json.loads(replay_path.read_text(encoding="utf-8"))
    eval_dir = ROOT / "eval" / run["eval_id"]
    items = {i["id"]: i for i in json.loads((eval_dir / "items.json").read_text(encoding="utf-8"))["items"]}
    labels = json.loads((eval_dir / "labels.json").read_text(encoding="utf-8"))["labels"]

    metrics = run["metrics"]["all_items"]
    queue: list[dict[str, object]] = []

    for kind, ids in (
        ("model_rejected_label_pass", metrics["false_negative_ids"]),
        ("model_passed_label_reject", metrics["false_positive_ids"]),
    ):
        for source_id in ids:
            label = labels[source_id]
            item = items[source_id]
            note = (label.get("notes") or "").strip()
            queue.append(
                {
                    "source_id": source_id,
                    "disagreement": kind,
                    "title": item["title"],
                    "url": item.get("url"),
                    "primary_category": item.get("primary_category"),
                    "current_label": {
                        "prefilter_should": label.get("prefilter_should"),
                        "kb_should": label.get("kb_should"),
                        "reasons": label.get("reasons"),
                        "notes": note,
                    },
                    "label_confidence": "noted" if note else "bulk_unnoted",
                    "model": {
                        "decision": run["results"][source_id]["decision"],
                        "tier": run["results"][source_id]["tier"],
                        "rationale": run["results"][source_id]["rationale"],
                    },
                    "verdict": None,
                    "verdict_options": [
                        "label_stands",
                        "label_was_wrong",
                        "genuinely_ambiguous",
                    ],
                    "adjudicator_note": "",
                }
            )

    unnoted = sum(1 for row in queue if row["label_confidence"] == "bulk_unnoted")
    payload = {
        "eval_id": run["eval_id"],
        "replay": str(replay_path.relative_to(ROOT)).replace("\\", "/"),
        "profile_version": run["profile_version"],
        "built_at": datetime.now(timezone.utc).isoformat(),
        "count": len(queue),
        "bulk_unnoted_count": unnoted,
        "how_to_use": (
            "For each row set verdict to label_stands (the model is wrong), label_was_wrong "
            "(the original label is wrong; correct it in labels.json), or genuinely_ambiguous "
            "(the boundary is undecidable from title plus abstract, so neither side should be "
            "scored on it). Rows marked bulk_unnoted came from the fast tail of the labeling "
            "pass and carry no written justification, so treat them as unsettled by default."
        ),
        "items": queue,
    }

    out_path = ROOT / args.out if args.out else eval_dir / "adjudication_queue.json"
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {out_path.relative_to(ROOT)}  ({len(queue)} rows, {unnoted} unnoted)")


if __name__ == "__main__":
    main()
