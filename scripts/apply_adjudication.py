"""Apply the human adjudication verdicts for the 31 prefilter_v1 disagreements.

The 31 model/label disagreements were clustered into 7 recurring policy boundaries and
adjudicated as policy rather than item by item, so each correction below cites the group
it came from. Gold gains an explicit tier (prefilter_tier_should); the pre-adjudication
label is preserved on each touched record so the change is auditable.

Policy decided:
  G1 engine/agent RL   pass when the SUBJECT is an agent, tool-use loop, prompt or
                       retrieval system; reject when it is the base model's own
                       reasoning, weights or reward model
  G2 engine internals  reject, EXCEPT context compression (context budgeting is a real
                       API-boundary concern)
  G3 benchmarks        failure-mode and measurement benchmarks pass at tier peripheral
  G4 verticals         clinical and other vertical applications reject regardless of
                       the LLM technique used
  G5 interpretability  passes at tier peripheral, never core
  G6 stimulus reads    philosophy / alignment / society / econ pass at tier peripheral
  G7 applied systems   applied LLM systems in other domains pass; adds the
                       applied_systems anchor to the profile

Usage:
  python scripts/apply_adjudication.py [--dry-run]
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LABELS = ROOT / "eval" / "prefilter_v1" / "labels.json"

# source_id -> (prefilter_should, tier, kb_should, reasons, group)
VERDICTS: dict[str, tuple[str, str | None, str, list[str], str]] = {
    # G1 — subject test. Subject is the base model: reject.
    "arxiv:2606.08854": ("reject", None, "drop", ["base_model_science"], "G1"),
    "arxiv:2606.09052": ("reject", None, "drop", ["base_model_science"], "G1"),
    "arxiv:2606.09073": ("reject", None, "drop", ["base_model_science"], "G1"),
    "arxiv:2606.10126": ("reject", None, "drop", ["base_model_science"], "G1"),
    "arxiv:2608.03092": ("reject", None, "drop", ["base_model_science"], "G1"),
    # G1 — subject is an agent loop or a prompt: pass core.
    "arxiv:2606.11119": ("pass", "core", "keep", ["agent_orchestration"], "G1"),
    "arxiv:2606.11459": ("pass", "core", "keep", ["agent_orchestration"], "G1"),
    # G1 — subject is robustness / behaviour characterisation: peripheral (see G3).
    "arxiv:2606.09701": ("pass", "peripheral", "skim", ["failure_modes"], "G1"),
    "arxiv:2606.11270": ("pass", "peripheral", "skim", ["failure_modes"], "G1"),
    # G2 — engine internals reject.
    "arxiv:2606.09937": ("reject", None, "drop", ["base_model_science"], "G2"),
    "arxiv:2606.10820": ("reject", None, "drop", ["base_model_science"], "G2"),
    "arxiv:2606.10890": ("reject", None, "drop", ["base_model_science"], "G2"),
    # G2 — context compression is the carve-out.
    "arxiv:2606.09659": (
        "pass",
        "core",
        "keep",
        ["inference_economics", "architecture_tradeoffs"],
        "G2",
    ),
    # G3 — failure-mode and measurement benchmarks: peripheral.
    "arxiv:2606.10159": ("pass", "peripheral", "skim", ["failure_modes"], "G3"),
    "arxiv:2606.10852": ("pass", "peripheral", "skim", ["failure_modes"], "G3"),
    "arxiv:2609.00064": ("pass", "peripheral", "skim", ["eval_observability"], "G3"),
    "arxiv:2606.10554": ("pass", "peripheral", "skim", ["eval_observability"], "G3"),
    # G4 — verticals reject regardless of technique.
    "arxiv:2606.09030": ("reject", None, "drop", ["wrong_domain"], "G4"),
    "arxiv:2606.10279": ("reject", None, "drop", ["wrong_domain", "base_model_science"], "G4"),
    "arxiv:2608.14792": ("reject", None, "drop", ["wrong_domain"], "G4"),
    # G5 — interpretability peripheral, except the multimodal one which stays rejected.
    "arxiv:2606.11375": ("pass", "peripheral", "skim", ["llm_internals"], "G5"),
    "arxiv:2608.04980": ("pass", "peripheral", "skim", ["llm_internals"], "G5"),
    "arxiv:2608.13167": ("reject", None, "drop", ["wrong_domain", "llm_internals"], "G5"),
    # G6 — stimulus reads: peripheral.
    "arxiv:2606.12032": ("pass", "peripheral", "skim", ["adjacent_stimulus"], "G6"),
    "arxiv:2607.27232": ("pass", "peripheral", "skim", ["adjacent_stimulus"], "G6"),
    "arxiv:2607.00924": ("pass", "peripheral", "skim", ["adjacent_stimulus"], "G6"),
    "arxiv:2608.00123": ("pass", "peripheral", "skim", ["adjacent_stimulus"], "G6"),
    "arxiv:2606.11893": ("pass", "peripheral", "skim", ["adjacent_stimulus"], "G6"),
    # G7 — applied systems in other domains.
    "arxiv:2606.10736": ("pass", "core", "keep", ["applied_systems"], "G7"),
    "arxiv:2606.09672": ("pass", "peripheral", "skim", ["applied_systems"], "G7"),
    "arxiv:2606.08153": ("pass", "peripheral", "skim", ["applied_systems"], "G7"),
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    doc = json.loads(LABELS.read_text(encoding="utf-8"))
    labels = doc["labels"]
    now = datetime.now(timezone.utc).isoformat()

    missing = [source_id for source_id in VERDICTS if source_id not in labels]
    if missing:
        raise SystemExit(f"verdicts reference unknown ids: {missing}")

    flips = 0
    tier_only = 0
    for source_id, (should, tier, kb, reasons, group) in VERDICTS.items():
        record = labels[source_id]
        before = {
            "prefilter_should": record["prefilter_should"],
            "kb_should": record["kb_should"],
            "reasons": list(record["reasons"]),
        }
        if before["prefilter_should"] != should:
            flips += 1
        else:
            tier_only += 1

        record["prefilter_should"] = should
        record["prefilter_tier_should"] = tier
        record["kb_should"] = kb
        record["reasons"] = reasons
        record["adjudicated"] = {
            "group": group,
            "at": now,
            "was": before,
        }

    # Every untouched pass predates the tier field; the model/label agreement on those
    # was 'core' by construction, so record that rather than leaving the field absent.
    backfilled = 0
    for record in labels.values():
        if "prefilter_tier_should" in record:
            continue
        if record["prefilter_should"] == "pass":
            record["prefilter_tier_should"] = "core" if record["kb_should"] == "keep" else "peripheral"
        else:
            record["prefilter_tier_should"] = None
        backfilled += 1

    doc["updated_at"] = now
    doc["adjudication"] = {
        "at": now,
        "source": "eval/prefilter_v1/adjudication_queue.json",
        "method": "31 disagreements clustered into 7 policy boundaries, decided as policy",
        "verdict_count": len(VERDICTS),
        "decision_flips": flips,
        "confirmations": tier_only,
        "tier_backfilled": backfilled,
    }

    gold_pass = sum(1 for r in labels.values() if r["prefilter_should"] == "pass")
    tiers = {
        "core": sum(1 for r in labels.values() if r.get("prefilter_tier_should") == "core"),
        "peripheral": sum(
            1 for r in labels.values() if r.get("prefilter_tier_should") == "peripheral"
        ),
    }
    print(f"verdicts applied={len(VERDICTS)}  decision flips={flips}  confirmations={tier_only}")
    print(f"tier backfilled on untouched records={backfilled}")
    print(f"gold now: pass={gold_pass} reject={len(labels) - gold_pass}  tiers={tiers}")

    if args.dry_run:
        print("\ndry run — nothing written")
        return

    LABELS.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"\nwrote {LABELS.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
