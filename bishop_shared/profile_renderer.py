"""NL profile load, canonical hash, and deterministic system-prompt rendering (§11)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict

from bishop_shared.enums import DomainEnum

PROFILES_CONTAINER_DIR = Path("/app/config/profiles")

_PROFILE_FILENAME: dict[DomainEnum, str] = {
    DomainEnum.PROFESSIONAL: "professional_v1.0.0.yaml",
}


class ProfileAnchor(BaseModel):
    id: str
    label: str
    rationale: str
    weight: float


class ProfileOutput(BaseModel):
    format: str
    include_rationale: bool
    rationale_max_tokens: int
    instruction: str


class ProfileDocument(BaseModel):
    """Contract surface for NL profile YAML (§11.2 core fields)."""

    model_config = ConfigDict(extra="ignore")

    version: str
    domain: str
    canonical_hash: str
    context: str
    principles: list[str]
    anchors: list[ProfileAnchor]
    exclusions: list[str]
    output: ProfileOutput


def resolve_profile_path(domain: DomainEnum) -> Path:
    """Map domain to container profile path; M3 supports professional only."""
    filename = _PROFILE_FILENAME.get(domain)
    if filename is None:
        msg = f"No profile configured for domain {domain.value!r}"
        raise ValueError(msg)
    return PROFILES_CONTAINER_DIR / filename


def _load_yaml_dict(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        msg = f"Profile YAML must be a mapping: {path}"
        raise TypeError(msg)
    return data


def _hashable_dict(data: dict[str, Any]) -> dict[str, Any]:
    """Profile content for §11.3 canonical hash (canonical_hash field excluded)."""
    return {key: value for key, value in data.items() if key != "canonical_hash"}


def compute_profile_hash(profile: Path | dict[str, Any]) -> str:
    """SHA-256 of JSON-canonical profile dict per §11.3."""
    if isinstance(profile, Path):
        payload_dict = _hashable_dict(_load_yaml_dict(profile))
    else:
        payload_dict = _hashable_dict(profile)

    canonical_json = json.dumps(payload_dict, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


def load_profile(path: Path) -> ProfileDocument:
    """Load and validate profile YAML into ProfileDocument."""
    return ProfileDocument.model_validate(_load_yaml_dict(path))


def render_profile_prompt(profile: ProfileDocument) -> str:
    """Deterministic Anthropic system prompt from profile fields (not hashed)."""
    sections: list[str] = [profile.context.rstrip()]

    sections.append("## Evaluation principles")
    sections.extend(f"- {principle}" for principle in profile.principles)

    sections.append("## Domain anchors")
    for anchor in profile.anchors:
        sections.append(f"### {anchor.label} (weight: {anchor.weight})")
        sections.append(anchor.rationale.rstrip())

    sections.append("## Exclusions")
    sections.extend(f"- {exclusion}" for exclusion in profile.exclusions)

    sections.append("## Output format")
    sections.append(profile.output.instruction.rstrip())

    return "\n\n".join(sections) + "\n"
