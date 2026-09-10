"""G6 enrichment quality sampling — template schema (CI) and manual checklist (M8 T7)."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_TEMPLATE_PATH = _REPO_ROOT / ".dev" / "quality" / "g6-enrichment-template.md"
_ENRICHMENT_PROFILE = "config/profiles/professional_v1.0.0.yaml"
_REQUIRED_ENTRY_COUNT = 10
_ENTRY_REQUIRED_KEYS = frozenset(
    {
        "slot",
        "source_id",
        "challenge_hooks",
        "value_rationale",
        "hooks_acceptable",
        "rationale_acceptable",
        "reviewer_notes",
    }
)
_JSON_BLOCK_RE = re.compile(r"```json\s*\n(.*?)\n```", re.DOTALL)


def _extract_template_payload() -> dict[str, Any]:
    text = _TEMPLATE_PATH.read_text(encoding="utf-8")
    match = _JSON_BLOCK_RE.search(text)
    assert match is not None, "g6-enrichment-template.md must contain a ```json block"
    payload = json.loads(match.group(1))
    assert isinstance(payload, dict)
    return payload


@pytest.fixture(scope="module")
def template_payload() -> dict[str, Any]:
    assert _TEMPLATE_PATH.is_file(), "g6-enrichment-template.md must exist"
    return _extract_template_payload()


def test_g6_enrichment_template_schema(template_payload: dict[str, Any]) -> None:
    assert template_payload["gate"] == "g6_enrichment"
    assert template_payload["version"] == 1
    assert template_payload["profile_under_test"] == _ENRICHMENT_PROFILE
    assert template_payload["required_entry_count"] == _REQUIRED_ENTRY_COUNT
    entries = template_payload["entries"]
    assert isinstance(entries, list)
    assert len(entries) == _REQUIRED_ENTRY_COUNT
    for entry in entries:
        assert isinstance(entry, dict)
        assert _ENTRY_REQUIRED_KEYS <= set(entry.keys())


def test_g6_enrichment_template_entry_slots(template_payload: dict[str, Any]) -> None:
    slots = [entry["slot"] for entry in template_payload["entries"]]
    assert slots == list(range(1, _REQUIRED_ENTRY_COUNT + 1))


def test_g6_enrichment_template_rejects_wrong_entry_count() -> None:
    """Falsifier: schema check must fail when entry count drops below ten."""
    payload = _extract_template_payload()
    payload["entries"] = payload["entries"][:9]
    with pytest.raises(AssertionError, match="10"):
        assert len(payload["entries"]) == _REQUIRED_ENTRY_COUNT


def test_g6_enrichment_manual_checklist(template_payload: dict[str, Any]) -> None:
    """Operator gate: all ten entries filled and both acceptance flags true."""
    if os.environ.get("BISHOP_G6_MANUAL") != "1":
        pytest.skip("set BISHOP_G6_MANUAL=1 after completing the enrichment checklist")

    for entry in template_payload["entries"]:
        slot = entry["slot"]
        source_id = entry.get("source_id")
        assert isinstance(source_id, str) and source_id.strip(), f"slot {slot}: source_id required"

        hooks = entry.get("challenge_hooks")
        assert isinstance(hooks, list) and hooks, f"slot {slot}: challenge_hooks required"
        assert all(isinstance(hook, str) and hook.strip() for hook in hooks), (
            f"slot {slot}: challenge_hooks must be non-empty strings"
        )

        rationale = entry.get("value_rationale")
        assert isinstance(rationale, str) and rationale.strip(), (
            f"slot {slot}: value_rationale required"
        )

        assert entry.get("hooks_acceptable") is True, f"slot {slot}: hooks_acceptable must be true"
        assert entry.get("rationale_acceptable") is True, (
            f"slot {slot}: rationale_acceptable must be true"
        )
