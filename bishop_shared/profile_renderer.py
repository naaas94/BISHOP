"""NL profile load, canonical hash, and deterministic system-prompt rendering (§11)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict

from bishop_shared.enums import DomainEnum

PROFILES_CONTAINER_DIR = Path("/app/config/profiles")

Gate = Literal["prefilter", "enrichment"]

# Gate 1 and enrichment Call 2 are pinned separately on purpose. The rendered prompt
# includes the profile's output instruction, and that instruction is gate-1 specific
# (a decision/tier verdict). Profile versions past 1.0.0 were tuned and measured against
# the gate-1 eval only, so advancing gate 1 must not silently change the enrichment
# prompt, which has no eval of its own. Advance the enrichment pin deliberately.
#
# AD HOC (2026-09-11): prefilter pin is the soft-launch overlay, not the intended
# calibrated pin (professional_v1.2.0.yaml). Revert with the overlay.
# See .dev/decision-logs/ops/soft-launch-precision-overlay.md.
_PROFILE_FILENAME: dict[Gate, dict[DomainEnum, str]] = {
    "prefilter": {
        DomainEnum.PROFESSIONAL: "professional_v1.2.0_soft_launch.yaml",
    },
    "enrichment": {
        DomainEnum.PROFESSIONAL: "professional_v1.0.0.yaml",
    },
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


class CalibrationExample(BaseModel):
    """Boundary case from a labeled eval set, rendered as a few-shot exemplar (§11.2)."""

    title: str
    decision: int
    tier: str | None = None
    why: str


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
    peripheral_classes: list[str] = []
    peripheral_disposition: Literal["pass", "park"] = "pass"
    calibration_examples: list[CalibrationExample] = []
    output: ProfileOutput


def resolve_profile_path(domain: DomainEnum, gate: Gate = "prefilter") -> Path:
    """Map domain and gate to container profile path; professional only."""
    filename = _PROFILE_FILENAME[gate].get(domain)
    if filename is None:
        msg = f"No {gate} profile configured for domain {domain.value!r}"
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


def render_profile_prompt(profile: ProfileDocument, *, include_output: bool = True) -> str:
    """Deterministic Anthropic system prompt from profile fields (not hashed).

    ``include_output`` defaults to ``True`` so every existing call site is
    byte-for-byte unchanged. Pass ``False`` to omit the "## Output format"
    section — used by enrichment Call 2, whose gate-1-specific output
    instruction (e.g. a binary decision) would otherwise contradict the
    relevance-scoring schema supplied elsewhere in that gate's prompt.
    """
    sections: list[str] = [profile.context.rstrip()]

    sections.append("## Evaluation principles")
    sections.extend(f"- {principle}" for principle in profile.principles)

    sections.append("## Domain anchors")
    for anchor in profile.anchors:
        sections.append(f"### {anchor.label} (weight: {anchor.weight})")
        sections.append(anchor.rationale.rstrip())

    sections.append("## Exclusions")
    sections.extend(f"- {' '.join(exclusion.split())}" for exclusion in profile.exclusions)

    if profile.peripheral_classes:
        if profile.peripheral_disposition == "park":
            peripheral_header = (
                "## Peripheral tier\n"
                "These classes are neither core nor excluded. Park them with decision 1 and "
                "tier peripheral. They do not proceed to enrichment. Do not reject them, "
                "and do not mark them core."
            )
        else:
            peripheral_header = (
                "## Peripheral tier\n"
                "These classes are neither core nor excluded. Pass them with decision 1 and "
                "tier peripheral. Do not reject them, and do not mark them core."
            )
        sections.append(peripheral_header)
        sections.extend(f"- {' '.join(item.split())}" for item in profile.peripheral_classes)

    if profile.calibration_examples:
        sections.append("## Calibration examples")
        for example in profile.calibration_examples:
            if example.decision == 0:
                verdict = "reject"
            elif example.tier == "peripheral" and profile.peripheral_disposition == "park":
                verdict = "park (peripheral)"
            else:
                verdict = f"pass ({example.tier or 'core'})"
            sections.append(
                f'- "{example.title}" -> {verdict}\n  {" ".join(example.why.split())}'
            )

    if include_output:
        sections.append("## Output format")
        sections.append(profile.output.instruction.rstrip())

    return "\n\n".join(sections) + "\n"
