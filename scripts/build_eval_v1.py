"""Rebuild the prefilter eval snapshot with uniform, leakage-free replay inputs.

Why this exists: eval/prefilter_v0/items.json froze two different projections. All 57
prefilter_pass items carry abstract=null plus an enrichment-generated `summary`, while all
72 prefilter_reject items carry a real `abstract` and no summary. The presence of the field
therefore predicts the original system decision perfectly, and the summary is a post-hoc
positive gloss written *after* the item passed. Replaying gate 1 on those fields would leak
the label. This script refetches the canonical arXiv abstract for every id so all 129 items
share one input field, and writes the result as a new eval_id (v0 stays frozen).

Usage:
  python scripts/build_eval_v1.py [--dry-run]
"""

from __future__ import annotations

import argparse
import html
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "eval" / "prefilter_v0"
DST = ROOT / "eval" / "prefilter_v1"
ARXIV_API = "https://export.arxiv.org/api/query"
CHUNK = 40
SLEEP_SECONDS = 3.0

_ENTRY_RE = re.compile(r"<entry>(.*?)</entry>", re.S)
_ID_RE = re.compile(r"<id>(.*?)</id>", re.S)
_TITLE_RE = re.compile(r"<title>(.*?)</title>", re.S)
_SUMMARY_RE = re.compile(r"<summary>(.*?)</summary>", re.S)
_PRIMARY_RE = re.compile(r'<arxiv:primary_category[^>]*term="([^"]+)"')
_CATEGORY_RE = re.compile(r'<category[^>]*term="([^"]+)"')


def _norm(text: str) -> str:
    return " ".join(text.split()).strip().lower()


def _bare_id(source_id: str) -> str:
    return source_id.split(":", 1)[1]


def fetch_batch(client: httpx.Client, bare_ids: list[str]) -> dict[str, dict[str, object]]:
    """Fetch metadata for a chunk of arXiv ids, keyed by versionless bare id."""
    response = client.get(
        ARXIV_API,
        params={"id_list": ",".join(bare_ids), "max_results": len(bare_ids)},
        timeout=60,
        follow_redirects=True,
    )
    response.raise_for_status()

    found: dict[str, dict[str, object]] = {}
    for block in _ENTRY_RE.findall(response.text):
        id_match = _ID_RE.search(block)
        title_match = _TITLE_RE.search(block)
        summary_match = _SUMMARY_RE.search(block)
        if not (id_match and title_match and summary_match):
            continue
        raw_id = id_match.group(1).rsplit("/abs/", 1)[-1]
        key = raw_id.split("v")[0] if re.match(r"^\d+\.\d+v\d+$", raw_id) else raw_id
        primary = _PRIMARY_RE.search(block)
        found[key] = {
            "title": html.unescape(" ".join(title_match.group(1).split())),
            "abstract": html.unescape(" ".join(summary_match.group(1).split())),
            "primary_category": primary.group(1) if primary else None,
            "categories": sorted(set(_CATEGORY_RE.findall(block))),
        }
    return found


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    src_items_doc = json.loads((SRC / "items.json").read_text(encoding="utf-8"))
    src_labels_doc = json.loads((SRC / "labels.json").read_text(encoding="utf-8"))
    items = src_items_doc["items"]

    bare_to_source = {_bare_id(item["id"]): item["id"] for item in items}
    bare_ids = list(bare_to_source)
    print(f"fetching {len(bare_ids)} arxiv abstracts in chunks of {CHUNK}")

    fetched: dict[str, dict[str, object]] = {}
    with httpx.Client(headers={"User-Agent": "bishop-eval-rebuild/1.0"}) as client:
        for index in range(0, len(bare_ids), CHUNK):
            chunk = bare_ids[index : index + CHUNK]
            batch = fetch_batch(client, chunk)
            fetched.update(batch)
            print(f"  chunk {index // CHUNK + 1}: requested {len(chunk)}, matched {len(batch)}")
            if index + CHUNK < len(bare_ids):
                time.sleep(SLEEP_SECONDS)

    missing: list[str] = []
    title_mismatch: list[tuple[str, str, str]] = []
    new_items: list[dict[str, object]] = []

    for item in items:
        bare = _bare_id(item["id"])
        meta = fetched.get(bare)
        rebuilt = dict(item)
        if meta is None:
            missing.append(item["id"])
            rebuilt["replay_abstract"] = None
            rebuilt["replay_abstract_source"] = "unavailable"
        else:
            if _norm(str(meta["title"])) != _norm(item["title"]):
                title_mismatch.append((item["id"], item["title"], str(meta["title"])))
            rebuilt["replay_abstract"] = meta["abstract"]
            rebuilt["replay_abstract_source"] = "arxiv_api"
            rebuilt["primary_category"] = meta["primary_category"]
            rebuilt["categories"] = meta["categories"]
        new_items.append(rebuilt)

    print()
    print(f"matched={len(items) - len(missing)}  missing={len(missing)}")
    if missing:
        print("  missing ids:", ", ".join(missing))
    print(f"title mismatches={len(title_mismatch)}")
    for source_id, frozen, live in title_mismatch:
        print(f"  {source_id}\n    frozen: {frozen}\n    arxiv : {live}")

    covered = sum(1 for item in new_items if item.get("replay_abstract"))
    print(f"replay_abstract present on {covered}/{len(new_items)} items")
    with_cat = sum(1 for item in new_items if item.get("primary_category"))
    print(f"primary_category present on {with_cat}/{len(new_items)} items")

    if args.dry_run:
        print("\ndry run — nothing written")
        return

    now = datetime.now(timezone.utc).isoformat()
    DST.mkdir(parents=True, exist_ok=True)

    items_doc = {
        "eval_id": "prefilter_v1",
        "derived_from": "eval/prefilter_v0/items.json",
        "built_at": now,
        "source_db_snapshot": src_items_doc.get("source_db_snapshot"),
        "profile_under_test": src_items_doc.get("profile_under_test"),
        "count": len(new_items),
        "splits": src_items_doc.get("splits"),
        "replay_input_field": "replay_abstract",
        "why_rebuilt": (
            "v0 froze asymmetric inputs: pass-split items had abstract=null plus an "
            "enrichment-generated summary, reject-split items had real abstracts. Field "
            "presence predicted the original decision, and the summary was written after "
            "the item passed. replay_abstract is the canonical arXiv abstract for every "
            "item, refetched from the arXiv API, so gate-1 replay sees one uniform input."
        ),
        "items": new_items,
    }
    (DST / "items.json").write_text(
        json.dumps(items_doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    labels_doc = dict(src_labels_doc)
    labels_doc["eval_id"] = "prefilter_v1"
    labels_doc["carried_from"] = "eval/prefilter_v0/labels.json"
    labels_doc["carried_at"] = now
    labels_doc["carry_note"] = (
        "Labels are unchanged and keyed by source_id. They were made against title plus "
        "the v0 body (summary for pass-split items, abstract for reject-split items); the "
        "verdicts are judgments about the item, not about a specific text rendering."
    )
    (DST / "labels.json").write_text(
        json.dumps(labels_doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    print(f"\nwrote {DST / 'items.json'}")
    print(f"wrote {DST / 'labels.json'}")


if __name__ == "__main__":
    main()
