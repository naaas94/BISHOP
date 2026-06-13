"""Unit tests for bishop_shared profile renderer (M3 T2)."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
import yaml

from bishop_shared.enums import DomainEnum
from bishop_shared.profile_renderer import (
    ProfileDocument,
    compute_profile_hash,
    load_profile,
    render_profile_prompt,
    resolve_profile_path,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
PROFESSIONAL_PROFILE_PATH = REPO_ROOT / "config/profiles/professional_v1.0.0.yaml"


def test_resolve_profile_path_professional() -> None:
    path = resolve_profile_path(DomainEnum.PROFESSIONAL)
    assert path.as_posix() == "/app/config/profiles/professional_v1.0.0.yaml"


def test_resolve_profile_path_personal_not_configured() -> None:
    with pytest.raises(ValueError, match="personal"):
        resolve_profile_path(DomainEnum.PERSONAL)


def test_load_professional_profile() -> None:
    profile = load_profile(PROFESSIONAL_PROFILE_PATH)
    assert profile.version == "1.0.0"
    assert profile.domain == "professional"
    assert profile.canonical_hash != "placeholder_compute_on_first_render"
    assert len(profile.principles) == 5
    assert len(profile.anchors) == 5
    assert profile.output.format == "integer"


def test_profile_document_round_trip() -> None:
    profile = load_profile(PROFESSIONAL_PROFILE_PATH)
    restored = ProfileDocument.model_validate(profile.model_dump())
    assert restored == profile


def test_hash_matches_canonical_in_yaml() -> None:
    profile = load_profile(PROFESSIONAL_PROFILE_PATH)
    assert compute_profile_hash(PROFESSIONAL_PROFILE_PATH) == profile.canonical_hash


def test_hash_uses_json_canonical_dict_not_raw_yaml_bytes() -> None:
    raw_bytes = PROFESSIONAL_PROFILE_PATH.read_bytes()
    computed = compute_profile_hash(PROFESSIONAL_PROFILE_PATH)
    assert hashlib.sha256(raw_bytes).hexdigest() != computed


def test_hash_excludes_canonical_hash_field() -> None:
    data = yaml.safe_load(PROFESSIONAL_PROFILE_PATH.read_text(encoding="utf-8"))
    tampered = dict(data)
    tampered["canonical_hash"] = "deadbeef"
    assert compute_profile_hash(tampered) == compute_profile_hash(data)


def test_prompt_deterministic() -> None:
    profile = load_profile(PROFESSIONAL_PROFILE_PATH)
    first = render_profile_prompt(profile)
    second = render_profile_prompt(profile)
    assert first == second
    assert profile.context.strip() in first
    assert "## Evaluation principles" in first
    assert "## Domain anchors" in first
    assert "## Exclusions" in first
    assert "## Output format" in first
    assert profile.output.instruction.strip() in first


def test_hash_mismatch_detected_when_content_tampered() -> None:
    data = yaml.safe_load(PROFESSIONAL_PROFILE_PATH.read_text(encoding="utf-8"))
    tampered = dict(data)
    tampered["context"] = tampered["context"] + "\nTAMPER"
    assert compute_profile_hash(tampered) != data["canonical_hash"]
