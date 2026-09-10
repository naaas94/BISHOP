"""Replay gate 1 offline against a frozen eval set and score it against human labels.

Runs the real pinned pre-filter model over a frozen item set using a chosen profile, then
scores the parsed decisions against eval labels. Two profiles replayed over the same input
field give an apples-to-apples comparison; the original `system.prefilter_decision` in the
snapshot is NOT a valid control because it was produced on different input text.

Usage:
  python scripts/replay_prefilter.py --profile config/profiles/professional_v1.1.0.yaml
  python scripts/replay_prefilter.py --profile ... --dry-run
  python scripts/replay_prefilter.py --compare <baseline.json> <candidate.json>
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bishop_shared.anthropic_config import (  # noqa: E402
    ANTHROPIC_MODEL_PREFILTER,
    get_anthropic_api_key,
)
from bishop_shared.profile_renderer import (  # noqa: E402
    compute_profile_hash,
    load_profile,
    render_profile_prompt,
)

MAX_TOKENS = 256
_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.S)


def parse_decision(text: str | None) -> dict[str, Any]:
    """Mirror of the batch-poller pre-filter parser: tolerant of a missing tier."""
    if not text:
        return {"decision": 0, "tier": None, "rationale": "empty model response", "parse_failed": True}
    candidate = text.strip()
    try:
        payload = json.loads(candidate)
    except json.JSONDecodeError:
        match = _JSON_OBJECT_RE.search(candidate)
        if match is None:
            return {
                "decision": 0,
                "tier": None,
                "rationale": "malformed JSON response",
                "parse_failed": True,
            }
        try:
            payload = json.loads(match.group(0))
        except json.JSONDecodeError:
            return {
                "decision": 0,
                "tier": None,
                "rationale": "malformed JSON response",
                "parse_failed": True,
            }
    if not isinstance(payload, dict):
        return {
            "decision": 0,
            "tier": None,
            "rationale": "malformed JSON response",
            "parse_failed": True,
        }

    decision = payload.get("decision")
    rationale = payload.get("rationale")
    if decision not in (0, 1) or not isinstance(rationale, str) or not rationale.strip():
        return {
            "decision": 0,
            "tier": None,
            "rationale": "malformed JSON response",
            "parse_failed": True,
        }

    tier = payload.get("tier")
    if decision == 1:
        tier = tier if tier in ("core", "peripheral") else "core"
    else:
        tier = None
    return {
        "decision": int(decision),
        "tier": tier,
        "rationale": rationale.strip(),
        "parse_failed": False,
    }


def score(
    results: dict[str, dict[str, Any]],
    labels: dict[str, dict[str, Any]],
    *,
    only: set[str] | None = None,
) -> dict[str, Any]:
    """Confusion of replayed decision vs human prefilter_should, plus error detail."""
    tp = fp = tn = fn = 0
    fp_ids: list[str] = []
    fn_ids: list[str] = []
    fn_keep_ids: list[str] = []
    tiers: Counter[str] = Counter()
    parse_failures = 0
    tier_hit = tier_total = 0

    for source_id, result in results.items():
        if only is not None and source_id not in only:
            continue
        label = labels.get(source_id)
        if label is None or label.get("status") != "labeled":
            continue
        gold = label.get("prefilter_should")
        predicted = "pass" if result["decision"] == 1 else "reject"
        if result.get("parse_failed"):
            parse_failures += 1
        if result["tier"]:
            tiers[result["tier"]] += 1

        if gold == "pass" and predicted == "pass":
            tp += 1
            gold_tier = label.get("prefilter_tier_should")
            if gold_tier:
                tier_total += 1
                tier_hit += int(result["tier"] == gold_tier)
        elif gold == "reject" and predicted == "pass":
            fp += 1
            fp_ids.append(source_id)
        elif gold == "reject" and predicted == "reject":
            tn += 1
        else:
            fn += 1
            fn_ids.append(source_id)
            if label.get("kb_should") == "keep":
                fn_keep_ids.append(source_id)

    n = tp + fp + tn + fn
    return {
        "n": n,
        "accuracy": (tp + tn) / n if n else 0.0,
        "precision": tp / (tp + fp) if (tp + fp) else 0.0,
        "recall": tp / (tp + fn) if (tp + fn) else 0.0,
        "confusion": {"tp": tp, "fp": fp, "tn": tn, "fn": fn},
        "fn_keep_grade": len(fn_keep_ids),
        "false_positive_ids": sorted(fp_ids),
        "false_negative_ids": sorted(fn_ids),
        "false_negative_keep_ids": sorted(fn_keep_ids),
        "tier_distribution": dict(tiers),
        "tier_agreement_on_true_positives": (tier_hit / tier_total) if tier_total else None,
        "tier_scored": tier_total,
        "parse_failures": parse_failures,
    }


def print_metrics(title: str, metrics: dict[str, Any]) -> None:
    confusion = metrics["confusion"]
    print(f"{title}: n={metrics['n']}")
    print(
        f"  acc={metrics['accuracy']:.3f} prec={metrics['precision']:.3f} "
        f"rec={metrics['recall']:.3f}"
    )
    print(
        f"  tp={confusion['tp']} fp={confusion['fp']} tn={confusion['tn']} "
        f"fn={confusion['fn']}  (keep-grade fn={metrics['fn_keep_grade']})"
    )
    if metrics["tier_distribution"]:
        agreement = metrics.get("tier_agreement_on_true_positives")
        suffix = "" if agreement is None else f"  tier_agree={agreement:.3f} (n={metrics['tier_scored']})"
        print(f"  tiers={metrics['tier_distribution']}{suffix}")
    if metrics["parse_failures"]:
        print(f"  parse_failures={metrics['parse_failures']}")


def do_compare(baseline_path: Path, candidate_path: Path) -> None:
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    candidate = json.loads(candidate_path.read_text(encoding="utf-8"))

    for scope in ("all_items", "excluding_calibration_examples"):
        print(f"=== {scope} ===")
        print_metrics(f"  baseline {baseline['profile_version']}", baseline["metrics"][scope])
        print_metrics(f"  candidate {candidate['profile_version']}", candidate["metrics"][scope])
        base, cand = baseline["metrics"][scope], candidate["metrics"][scope]
        print(
            f"  delta: fp {base['confusion']['fp']} -> {cand['confusion']['fp']}, "
            f"fn {base['confusion']['fn']} -> {cand['confusion']['fn']}, "
            f"keep-grade fn {base['fn_keep_grade']} -> {cand['fn_keep_grade']}, "
            f"acc {base['accuracy']:.3f} -> {cand['accuracy']:.3f}"
        )
        print()

    base_fp = set(baseline["metrics"]["all_items"]["false_positive_ids"])
    cand_fp = set(candidate["metrics"]["all_items"]["false_positive_ids"])
    base_fn = set(baseline["metrics"]["all_items"]["false_negative_ids"])
    cand_fn = set(candidate["metrics"]["all_items"]["false_negative_ids"])
    print("false positives fixed :", ", ".join(sorted(base_fp - cand_fp)) or "none")
    print("false positives added :", ", ".join(sorted(cand_fp - base_fp)) or "none")
    print("false negatives fixed :", ", ".join(sorted(base_fn - cand_fn)) or "none")
    print("false negatives added :", ", ".join(sorted(cand_fn - base_fn)) or "none")


def do_rescore(replay_path: Path) -> None:
    """Recompute a stored replay's metrics against the labels as they are now."""
    run = json.loads(replay_path.read_text(encoding="utf-8"))
    eval_dir = ROOT / "eval" / run["eval_id"]
    labels = json.loads((eval_dir / "labels.json").read_text(encoding="utf-8"))["labels"]

    exemplars = set(run.get("calibration_exemplar_ids") or [])
    non_exemplar = set(run["results"]) - exemplars
    metrics = {
        "all_items": score(run["results"], labels),
        "excluding_calibration_examples": score(run["results"], labels, only=non_exemplar),
    }

    run["metrics_before_rescore"] = run["metrics"]
    run["metrics"] = metrics
    run["rescored_at"] = datetime.now(timezone.utc).isoformat()
    run["rescored_against"] = "labels.json as of rescore time (adjudicated)"
    replay_path.write_text(json.dumps(run, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"rescored {replay_path.name} (profile {run['profile_version']})")
    print_metrics("  all items", metrics["all_items"])
    print_metrics("  excluding exemplars", metrics["excluding_calibration_examples"])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", default="config/profiles/professional_v1.1.0.yaml")
    parser.add_argument("--eval", default="eval/prefilter_v1")
    parser.add_argument("--input-field", default="replay_abstract")
    parser.add_argument("--concurrency", type=int, default=8)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--compare", nargs=2, metavar=("BASELINE", "CANDIDATE"))
    parser.add_argument(
        "--rescore",
        metavar="REPLAY",
        help="Recompute a stored replay's metrics against the current labels, in place. "
        "Needed whenever labels change, since stored metrics are frozen at run time.",
    )
    args = parser.parse_args()

    if args.compare:
        do_compare(Path(args.compare[0]), Path(args.compare[1]))
        return

    if args.rescore:
        do_rescore(ROOT / args.rescore)
        return

    eval_dir = ROOT / args.eval
    profile_path = ROOT / args.profile
    items = json.loads((eval_dir / "items.json").read_text(encoding="utf-8"))["items"]
    labels = json.loads((eval_dir / "labels.json").read_text(encoding="utf-8"))["labels"]

    profile = load_profile(profile_path)
    system_prompt = render_profile_prompt(profile)
    render_hash = compute_profile_hash(profile_path)

    if args.limit:
        items = items[: args.limit]

    missing_input = [i["id"] for i in items if not (i.get(args.input_field) or "").strip()]
    if missing_input:
        raise SystemExit(
            f"{len(missing_input)} items lack '{args.input_field}'; "
            f"refusing to replay on uneven inputs: {missing_input[:5]}"
        )

    # Titles named in the profile's own calibration examples are leaked into the prompt;
    # the honest headline number excludes them.
    exemplar_titles = {" ".join(e.title.split()).lower() for e in profile.calibration_examples}
    exemplar_ids = {
        i["id"] for i in items if " ".join(i["title"].split()).lower() in exemplar_titles
    }
    non_exemplar_ids = {i["id"] for i in items} - exemplar_ids

    print(f"profile={profile.version} hash={render_hash[:12]} model={ANTHROPIC_MODEL_PREFILTER}")
    print(f"items={len(items)} input_field={args.input_field}")
    print(f"calibration exemplars present in set: {len(exemplar_ids)}")
    print(f"system prompt chars={len(system_prompt)}")

    if args.dry_run:
        sample = items[0]
        print("\n--- sample user message ---")
        print(f"{sample['title']}\n{sample[args.input_field]}"[:600])
        print("\ndry run — no API calls made")
        return

    api_key = get_anthropic_api_key()
    if not api_key:
        raise SystemExit("ANTHROPIC_API_KEY is not set")

    from anthropic import Anthropic

    client = Anthropic(api_key=api_key)

    def run_one(item: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        user_message = f"{item['title']}\n{item[args.input_field]}"
        try:
            response = client.messages.create(
                model=ANTHROPIC_MODEL_PREFILTER,
                max_tokens=MAX_TOKENS,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
            )
            text = "".join(block.text for block in response.content if block.type == "text")
        except Exception as exc:  # noqa: BLE001 - record and keep the run going
            return item["id"], {
                "decision": 0,
                "tier": None,
                "rationale": f"api error: {exc}",
                "parse_failed": True,
            }
        return item["id"], parse_decision(text)

    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        results = dict(pool.map(run_one, items))

    metrics = {
        "all_items": score(results, labels),
        "excluding_calibration_examples": score(results, labels, only=non_exemplar_ids),
    }

    print()
    print_metrics("all items (calibration exemplars leaked)", metrics["all_items"])
    print()
    print_metrics("excluding calibration exemplars (honest)", metrics["excluding_calibration_examples"])

    timestamp = datetime.now(timezone.utc)
    out_dir = eval_dir / "replays"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{timestamp:%Y%m%dT%H%M%SZ}_{profile.version}.json"
    out_path.write_text(
        json.dumps(
            {
                "eval_id": eval_dir.name,
                "replayed_at": timestamp.isoformat(),
                "profile_path": str(profile_path.relative_to(ROOT)).replace("\\", "/"),
                "profile_version": profile.version,
                "profile_render_hash": render_hash,
                "model": ANTHROPIC_MODEL_PREFILTER,
                "input_field": args.input_field,
                "item_count": len(items),
                "calibration_exemplar_ids": sorted(exemplar_ids),
                "metrics": metrics,
                "results": results,
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"\nwrote {out_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
