"""Recompute and stamp a profile's canonical_hash (§11.3), then render its prompt.

Usage:
  python scripts/profile_hash.py config/profiles/professional_v1.1.0.yaml [--render]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bishop_shared.profile_renderer import (  # noqa: E402
    compute_profile_hash,
    load_profile,
    render_profile_prompt,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("profile")
    parser.add_argument("--render", action="store_true")
    args = parser.parse_args()

    path = Path(args.profile)
    if not path.is_absolute():
        path = ROOT / path

    digest = compute_profile_hash(path)
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

    profile = load_profile(path)
    if compute_profile_hash(path) != profile.canonical_hash:
        raise SystemExit("hash still mismatched after stamping")
    print(f"verified {path.name} version={profile.version}")

    if args.render:
        print("-" * 80)
        print(render_profile_prompt(profile))


if __name__ == "__main__":
    main()
