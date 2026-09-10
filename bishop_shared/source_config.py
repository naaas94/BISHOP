"""Per-source category gate config: YAML load and category matching.

A zero-cost structural filter applied in the scraper *before* an item is handed
onward for LLM pre-filtering. Matching is intentionally scoped to a single
category string per item — the ArXiv **primary** category — because
cross-listings are noisy and produce false drops (see
``config/sources/arxiv.yaml`` for the measured counts).

Semantics:

* ``exclude_categories`` is evaluated first and always wins.
* ``include_categories`` empty means "allow all"; non-empty means the item's
  category must match at least one entry.
* A pattern ending in ``.*`` matches any category with that archive prefix
  (``cs.*`` matches ``cs.CV``). All other patterns are exact.
* An item with no category metadata is allowed through (fail open) — the gate
  never destroys an item it cannot evaluate.
* A missing config file yields ``None`` from :func:`load_source_config`, which
  callers treat as "gate absent, behave as before".
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict

SOURCES_CONTAINER_DIR = Path("/app/config/sources")
SOURCES_REPO_DIR = Path(__file__).resolve().parent.parent / "config" / "sources"

_WILDCARD_SUFFIX = ".*"


def category_matches(category: str, pattern: str) -> bool:
    """True if ``category`` satisfies ``pattern`` (exact or ``cs.*`` wildcard)."""
    if pattern.endswith(_WILDCARD_SUFFIX):
        archive = pattern[: -len(_WILDCARD_SUFFIX)]
        return category == archive or category.startswith(f"{archive}.")
    return category == pattern


class SourceCategoryConfig(BaseModel):
    """Contract surface for ``config/sources/<source>.yaml``."""

    model_config = ConfigDict(extra="ignore")

    version: str
    include_categories: list[str] = []
    exclude_categories: list[str] = []
    enforce: bool = False

    def allows(self, category: str | None) -> bool:
        """Gate verdict for one item; ``None`` category always passes."""
        if category is None:
            return True
        if any(category_matches(category, pattern) for pattern in self.exclude_categories):
            return False
        if not self.include_categories:
            return True
        return any(category_matches(category, pattern) for pattern in self.include_categories)


def resolve_source_config_path(source: str) -> Path:
    """Container path when present, else the repo-relative path (dev/tests)."""
    container_path = SOURCES_CONTAINER_DIR / f"{source}.yaml"
    if container_path.is_file():
        return container_path
    return SOURCES_REPO_DIR / f"{source}.yaml"


def _load_yaml_dict(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        msg = f"Source config YAML must be a mapping: {path}"
        raise TypeError(msg)
    return data


def load_source_config(source: str, *, path: Path | None = None) -> SourceCategoryConfig | None:
    """Load a source's category gate config, or ``None`` when the file is absent."""
    config_path = path if path is not None else resolve_source_config_path(source)
    if not config_path.is_file():
        return None
    return SourceCategoryConfig.model_validate(_load_yaml_dict(config_path))
