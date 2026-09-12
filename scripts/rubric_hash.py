"""Recompute and stamp a rubric asset's canonical_hash, then optionally print its body.

Usage:
  python scripts/rubric_hash.py config/prompts/prefilter_rubric_v1.md [--render]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bishop_shared.rubric_assets import (  # noqa: E402
    compute_rubric_hash,
    load_rubric,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("rubric")
    parser.add_argument("--render", action="store_true")
    args = parser.parse_args()

    path = Path(args.rubric)
    if not path.is_absolute():
        path = ROOT / path

    digest = compute_rubric_hash(path)
    text = path.read_text(encoding="utf-8")
    stamped, count = re.subn(
        r'^canonical_hash:.*$',
        f'canonical_hash: "{digest}"',
        text,
        count=1,
        flags=re.MULTILINE,
    )
    if count != 1:
        raise SystemExit("could not locate canonical_hash line")
    if stamped != text:
        path.write_text(stamped, encoding="utf-8")
        print(f"stamped canonical_hash: {digest}")
    else:
        print(f"canonical_hash already current: {digest}")

    doc = load_rubric(path)
    if compute_rubric_hash(path) != doc.canonical_hash:
        raise SystemExit("hash still mismatched after stamping")
    print(f"verified {path.name} rubric_id={doc.rubric_id} version={doc.version}")

    if args.render:
        print("-" * 80)
        print(doc.body)


if __name__ == "__main__":
    main()
