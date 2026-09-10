"""Unit tests for the gate 2 index policy loader and classification bands."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from bishop_shared.index_policy import (
    INDEX_POLICY_CONTAINER_PATH,
    IndexPolicy,
    load_index_policy,
    permissive_policy,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
INDEX_POLICY_PATH = REPO_ROOT / "config/index_policy.yaml"


def _policy(**overrides: object) -> IndexPolicy:
    fields: dict[str, object] = {
        "version": "0.1.0",
        "keep_min": 0.40,
        "skim_min": 0.25,
        "enforce": False,
    }
    fields.update(overrides)
    return IndexPolicy.model_validate(fields)


def test_container_path_matches_repo_config_filename() -> None:
    assert INDEX_POLICY_CONTAINER_PATH.as_posix() == "/app/config/index_policy.yaml"
    assert INDEX_POLICY_CONTAINER_PATH.name == INDEX_POLICY_PATH.name


def test_load_repo_index_policy_defaults() -> None:
    policy = load_index_policy(INDEX_POLICY_PATH)
    assert policy.version == "0.1.0"
    assert policy.keep_min == 0.40
    assert policy.skim_min == 0.25
    assert policy.enforce is False


def test_shipped_policy_does_not_enforce() -> None:
    """Falsifier: gate 2 must not drop content until it has independent labels."""
    raw = yaml.safe_load(INDEX_POLICY_PATH.read_text(encoding="utf-8"))
    assert raw["enforce"] is False


@pytest.mark.parametrize(
    "score,expected",
    [
        (1.0, "keep"),
        (0.72, "keep"),
        (0.41, "keep"),
        (0.40, "keep"),
        (0.39, "skim"),
        (0.35, "skim"),
        (0.26, "skim"),
        (0.25, "skim"),
        (0.24, "drop"),
        (0.0, "drop"),
    ],
)
def test_classify_bands_including_exact_boundaries(score: float, expected: str) -> None:
    assert _policy().classify(score) == expected


def test_classify_none_is_skim() -> None:
    """A missing enrichment_score is unknown, not bad."""
    assert _policy().classify(None) == "skim"


def test_classify_rejects_nothing_observed_wanted_at_lowest_labeled_score() -> None:
    """Falsifier: genuinely-wanted items scored as low as 0.25 must not land in drop."""
    assert _policy().classify(0.25) != "drop"


def test_skim_min_above_keep_min_rejected() -> None:
    with pytest.raises(ValidationError, match="skim_min"):
        _policy(skim_min=0.60, keep_min=0.40)


@pytest.mark.parametrize(
    "overrides",
    [
        {"keep_min": 1.5},
        {"keep_min": -0.1},
        {"skim_min": 1.2, "keep_min": 1.3},
        {"skim_min": -0.5},
    ],
)
def test_out_of_range_bounds_rejected(overrides: dict[str, object]) -> None:
    with pytest.raises(ValidationError, match="within 0.0-1.0"):
        _policy(**overrides)


def test_missing_config_falls_back_to_permissive_defaults(tmp_path: Path) -> None:
    policy = load_index_policy(tmp_path / "does_not_exist.yaml")
    assert policy == permissive_policy()
    assert policy.enforce is False
    assert policy.classify(0.72) == "keep"
    assert policy.classify(None) == "skim"


def test_non_mapping_config_rejected(tmp_path: Path) -> None:
    path = tmp_path / "index_policy.yaml"
    path.write_text("- not-a-mapping\n", encoding="utf-8")
    with pytest.raises(TypeError, match="must be a mapping"):
        load_index_policy(path)


def test_load_index_policy_reads_enforce_true(tmp_path: Path) -> None:
    path = tmp_path / "index_policy.yaml"
    path.write_text(
        yaml.safe_dump(
            {"version": "9.9.9", "keep_min": 0.40, "skim_min": 0.25, "enforce": True}
        ),
        encoding="utf-8",
    )
    policy = load_index_policy(path)
    assert policy.enforce is True
    assert policy.version == "9.9.9"
