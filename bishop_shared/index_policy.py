"""Gate 2 index policy: enrichment_score bands, the enforce knob, and the YAML loader."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, model_validator

INDEX_POLICY_CONTAINER_PATH = Path("/app/config/index_policy.yaml")

IndexClass = Literal["keep", "skim", "drop"]

_FALLBACK_VERSION = "0.0.0-fallback"


class IndexPolicy(BaseModel):
    """Contract surface for config/index_policy.yaml (gate 2 thresholds)."""

    model_config = ConfigDict(extra="ignore")

    version: str
    keep_min: float
    skim_min: float
    enforce: bool = False

    @model_validator(mode="after")
    def _check_thresholds(self) -> IndexPolicy:
        for name, bound in (("keep_min", self.keep_min), ("skim_min", self.skim_min)):
            if not 0.0 <= bound <= 1.0:
                msg = f"{name} must be within 0.0-1.0, got {bound!r}"
                raise ValueError(msg)
        if self.skim_min > self.keep_min:
            msg = f"skim_min ({self.skim_min}) must not exceed keep_min ({self.keep_min})"
            raise ValueError(msg)
        return self

    def classify(self, score: float | None) -> IndexClass:
        """Band an enrichment_score. Bounds are inclusive; a missing score skims."""
        if score is None:
            return "skim"
        if score >= self.keep_min:
            return "keep"
        if score >= self.skim_min:
            return "skim"
        return "drop"


def permissive_policy() -> IndexPolicy:
    """Fallback used when no policy YAML is present: classify and log, never enforce."""
    return IndexPolicy(version=_FALLBACK_VERSION, keep_min=0.40, skim_min=0.25, enforce=False)


def _load_yaml_dict(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        msg = f"Index policy YAML must be a mapping: {path}"
        raise TypeError(msg)
    return data


def load_index_policy(path: Path = INDEX_POLICY_CONTAINER_PATH) -> IndexPolicy:
    """Load and validate policy YAML; absent file falls back to permissive defaults."""
    if not path.is_file():
        return permissive_policy()
    return IndexPolicy.model_validate(_load_yaml_dict(path))
