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
CALIBRATED_PROFILE_PATH = REPO_ROOT / "config/profiles/professional_v1.1.1.yaml"
SOFT_LAUNCH_PROFILE_PATH = REPO_ROOT / "config/profiles/professional_v1.2.0_soft_launch.yaml"
V1_2_PROFILE_PATH = REPO_ROOT / "config/profiles/professional_v1.2.0.yaml"


def test_resolve_profile_path_professional() -> None:
    path = resolve_profile_path(DomainEnum.PROFESSIONAL)
    assert path.as_posix() == "/app/config/profiles/professional_v1.2.0_soft_launch.yaml"


def test_resolve_profile_path_enrichment_pinned_separately() -> None:
    """Enrichment must not follow the gate-1 pin: the rendered output instruction is
    gate-1 specific, and profiles past 1.0.0 were only measured against the gate-1 eval."""
    prefilter = resolve_profile_path(DomainEnum.PROFESSIONAL, gate="prefilter")
    enrichment = resolve_profile_path(DomainEnum.PROFESSIONAL, gate="enrichment")
    assert enrichment.as_posix() == "/app/config/profiles/professional_v1.0.0.yaml"
    assert prefilter != enrichment


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


def test_v1_0_0_has_no_calibration_examples_and_renders_no_section() -> None:
    profile = load_profile(PROFESSIONAL_PROFILE_PATH)
    assert profile.calibration_examples == []
    assert "## Calibration examples" not in render_profile_prompt(profile)


def test_calibrated_profile_loads_with_examples_and_matching_hash() -> None:
    profile = load_profile(CALIBRATED_PROFILE_PATH)
    assert profile.version == "1.1.1"
    assert compute_profile_hash(CALIBRATED_PROFILE_PATH) == profile.canonical_hash
    assert profile.calibration_examples, "calibrated profile must carry boundary exemplars"
    assert any(example.decision == 0 for example in profile.calibration_examples)
    assert any(example.decision == 1 for example in profile.calibration_examples)


def test_calibration_examples_render_with_verdict_and_reason() -> None:
    profile = load_profile(CALIBRATED_PROFILE_PATH)
    rendered = render_profile_prompt(profile)
    assert "## Calibration examples" in rendered
    for example in profile.calibration_examples:
        assert example.title in rendered
    assert "-> reject" in rendered
    assert "-> pass (core)" in rendered
    assert "-> pass (peripheral)" in rendered


def test_calibration_examples_change_the_canonical_hash() -> None:
    data = yaml.safe_load(CALIBRATED_PROFILE_PATH.read_text(encoding="utf-8"))
    stripped = {key: value for key, value in data.items() if key != "calibration_examples"}
    assert compute_profile_hash(stripped) != compute_profile_hash(data)


def test_calibration_example_section_omitted_when_list_empty() -> None:
    data = yaml.safe_load(CALIBRATED_PROFILE_PATH.read_text(encoding="utf-8"))
    data["calibration_examples"] = []
    profile = ProfileDocument.model_validate(data)
    assert "## Calibration examples" not in render_profile_prompt(profile)


def test_render_is_deterministic_across_profiles() -> None:
    for path in (PROFESSIONAL_PROFILE_PATH, CALIBRATED_PROFILE_PATH):
        profile = load_profile(path)
        assert render_profile_prompt(profile) == render_profile_prompt(profile)


def test_hash_mismatch_detected_when_content_tampered() -> None:
    data = yaml.safe_load(PROFESSIONAL_PROFILE_PATH.read_text(encoding="utf-8"))
    tampered = dict(data)
    tampered["context"] = tampered["context"] + "\nTAMPER"
    assert compute_profile_hash(tampered) != data["canonical_hash"]


def test_soft_launch_profile_loads_and_parks_peripheral() -> None:
    profile = load_profile(SOFT_LAUNCH_PROFILE_PATH)
    assert profile.version == "1.2.0-soft-launch"
    assert profile.peripheral_disposition == "park"
    assert compute_profile_hash(SOFT_LAUNCH_PROFILE_PATH) == profile.canonical_hash
    rendered = render_profile_prompt(profile)
    assert "Park them with decision 1" in rendered
    assert "They do not proceed to enrichment" in rendered
    assert "park (peripheral)" in rendered
    assert "When genuinely uncertain, pass with tier peripheral" not in rendered


def test_legacy_profiles_default_peripheral_disposition_pass() -> None:
    profile = load_profile(V1_2_PROFILE_PATH)
    assert profile.peripheral_disposition == "pass"
    assert "Pass them with decision 1" in render_profile_prompt(profile)


# prompt-caching plan T1 — §2 row 3: render_profile_prompt(profile, *, include_output=True).
# Default True must be byte-for-byte identical to the pre-change render (pinned below).
_SOFT_LAUNCH_DEFAULT_RENDER_LEN = 10799
_SOFT_LAUNCH_DEFAULT_RENDER_SHA256 = (
    "2518f24b3df2736b19d34c6129bdc35a37529ce116902331c371e1df84d630fd"
)


def test_default_render_is_byte_identical_to_pre_change_pin() -> None:
    import hashlib

    profile = load_profile(SOFT_LAUNCH_PROFILE_PATH)
    rendered = render_profile_prompt(profile)
    assert len(rendered) == _SOFT_LAUNCH_DEFAULT_RENDER_LEN
    assert hashlib.sha256(rendered.encode("utf-8")).hexdigest() == _SOFT_LAUNCH_DEFAULT_RENDER_SHA256
    # include_output defaults to True and must match calling it explicitly.
    assert rendered == render_profile_prompt(profile, include_output=True)


def test_include_output_false_omits_output_section_and_nothing_else() -> None:
    profile = load_profile(SOFT_LAUNCH_PROFILE_PATH)
    with_output = render_profile_prompt(profile, include_output=True)
    without_output = render_profile_prompt(profile, include_output=False)

    assert "## Output format" in with_output
    assert "## Output format" not in without_output
    assert profile.output.instruction.strip() not in without_output

    # Nothing else differs: reconstruct with_output by re-appending the
    # output section that include_output=False dropped.
    output_block = "\n\n## Output format\n\n" + profile.output.instruction.rstrip()
    assert without_output.rstrip("\n") + output_block + "\n" == with_output


def test_include_output_false_does_not_change_hash_inputs() -> None:
    """include_output only changes rendering, never the profile's canonical_hash."""
    profile = load_profile(SOFT_LAUNCH_PROFILE_PATH)
    assert compute_profile_hash(SOFT_LAUNCH_PROFILE_PATH) == profile.canonical_hash
    render_profile_prompt(profile, include_output=False)
    assert compute_profile_hash(SOFT_LAUNCH_PROFILE_PATH) == profile.canonical_hash
