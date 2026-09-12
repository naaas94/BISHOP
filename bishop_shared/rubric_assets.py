"""Rubric asset load, canonical hash, and hash-or-abort verification.

Rubric annexes (`config/prompts/*_rubric_v1.md`) are gate-quality prompt
content authored to help clear Claude Haiku 4.5's cache-floor while adding
real evaluation signal (no padding — §2 Non-goals). This module mirrors the
existing profile hash-or-abort discipline in `bishop_shared.profile_renderer`
but hashes a Markdown-with-front-matter asset instead of a YAML dict, and
the hash covers the body only (front matter, including the stamped hash
itself, is excluded — §2 row 7).
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Final, Literal

from pydantic import BaseModel

PROMPTS_CONTAINER_DIR = Path("/app/config/prompts")

RubricId = Literal["prefilter_rubric", "call1_rubric", "call2_rubric"]

_RUBRIC_FILENAME: dict[RubricId, str] = {
    "prefilter_rubric": "prefilter_rubric_v1.md",
    "call1_rubric": "call1_rubric_v1.md",
    "call2_rubric": "call2_rubric_v1.md",
}

# ---\nrubric_id: ...\nversion: "..."\ncanonical_hash: "..."\n---\n<body>
_FRONT_MATTER_PATTERN: Final = re.compile(
    r"\A---\n(?P<frontmatter>.*?)\n---\n(?P<body>.*)\Z",
    re.DOTALL,
)
_FIELD_PATTERN: Final = re.compile(r'^(\w+):\s*"?([^"\n]*)"?\s*$', re.MULTILINE)


class RubricDocument(BaseModel):
    """Loaded rubric asset — front-matter fields plus normalized body."""

    rubric_id: str
    version: str
    canonical_hash: str
    body: str


def resolve_rubric_path(rubric_id: RubricId) -> Path:
    """Map a rubric id to its container path; unknown ids raise."""
    filename = _RUBRIC_FILENAME.get(rubric_id)
    if filename is None:
        msg = f"Unknown rubric_id: {rubric_id!r}"
        raise ValueError(msg)
    return PROMPTS_CONTAINER_DIR / filename


def _normalize(text: str) -> str:
    """CRLF -> LF. Hashing and prefix-emission must see identical bytes
    regardless of the authoring platform's line endings (§2 row 7, A5)."""
    return text.replace("\r\n", "\n")


def _split_front_matter(raw_text: str) -> tuple[dict[str, str], str]:
    match = _FRONT_MATTER_PATTERN.match(_normalize(raw_text))
    if match is None:
        msg = "Rubric asset is missing the required '---' front-matter block"
        raise ValueError(msg)
    fields = dict(_FIELD_PATTERN.findall(match.group("frontmatter")))
    return fields, match.group("body")


def load_rubric(path: Path) -> RubricDocument:
    """Load and validate a rubric asset into a RubricDocument."""
    fields, body = _split_front_matter(path.read_text(encoding="utf-8"))
    for required in ("rubric_id", "version", "canonical_hash"):
        if required not in fields:
            msg = f"Rubric asset front matter missing required field: {required!r}"
            raise ValueError(msg)
    return RubricDocument(
        rubric_id=fields["rubric_id"],
        version=fields["version"],
        canonical_hash=fields["canonical_hash"],
        body=_normalize(body),
    )


def compute_rubric_hash(rubric: Path | str) -> str:
    """SHA-256 of the rubric body only, LF-normalized, front matter excluded.

    Accepts either a path to a rubric asset (front matter is parsed off and
    discarded) or a raw body string (assumed already front-matter-free).
    """
    if isinstance(rubric, Path):
        _, body = _split_front_matter(rubric.read_text(encoding="utf-8"))
    else:
        body = rubric
    normalized = _normalize(body)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def verify_rubric_hash(
    rubric_id: RubricId,
    *,
    rubric_path: Path | None = None,
) -> tuple[str, str, str] | None:
    """Recompute a rubric's hash and compare against its stamped value.

    Returns ``(rubric_id, version, canonical_hash)`` from the loaded
    document on match, or ``None`` on mismatch. Callers (the three gates)
    treat ``None`` as hash-or-abort per §2 row 12.
    """
    path = rubric_path if rubric_path is not None else resolve_rubric_path(rubric_id)
    doc = load_rubric(path)
    if compute_rubric_hash(path) != doc.canonical_hash:
        return None
    return (doc.rubric_id, doc.version, doc.canonical_hash)
