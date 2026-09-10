"""Compute prefilter_v0 metrics from frozen items + human labels.

Usage:
  python scripts/eval_prefilter_metrics.py
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVAL = ROOT / "eval" / "prefilter_v0"


def main() -> None:
    items = json.loads((EVAL / "items.json").read_text(encoding="utf-8"))["items"]
    labels = json.loads((EVAL / "labels.json").read_text(encoding="utf-8"))["labels"]
    by_id = {item["id"]: item for item in items}

    labeled = [(sid, lab) for sid, lab in labels.items() if lab.get("status") == "labeled"]
    print(f"items={len(items)} labeled={len(labeled)}")
    if not labeled:
        return

    tp = fp = tn = fn = 0
    reasons: Counter[str] = Counter()
    kb: Counter[str] = Counter()

    for sid, lab in labeled:
        item = by_id.get(sid)
        if item is None:
            print(f"orphan label: {sid}")
            continue
        system = "pass" if item["system"]["prefilter_decision"] == 1 else "reject"
        gold = lab.get("prefilter_should")
        if gold == "pass" and system == "pass":
            tp += 1
        elif gold == "reject" and system == "pass":
            fp += 1
        elif gold == "reject" and system == "reject":
            tn += 1
        elif gold == "pass" and system == "reject":
            fn += 1
        for reason in lab.get("reasons") or []:
            reasons[reason] += 1
        if lab.get("kb_should"):
            kb[lab["kb_should"]] += 1

    n = tp + fp + tn + fn
    acc = (tp + tn) / n if n else 0
    prec = tp / (tp + fp) if (tp + fp) else 0
    rec = tp / (tp + fn) if (tp + fn) else 0
    print(f"prefilter  acc={acc:.3f} prec={prec:.3f} rec={rec:.3f}")
    print(f"confusion  tp={tp} fp={fp} tn={tn} fn={fn}")
    print("kb_should ", dict(kb))
    print("reasons   ", dict(reasons))


if __name__ == "__main__":
    main()
