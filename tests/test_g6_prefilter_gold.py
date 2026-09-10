"""G6 prefilter gold binding — consume landed eval/prefilter_v1 (M8 T7)."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_EVAL_DIR = _REPO_ROOT / "eval" / "prefilter_v1"
_CONTRACT_PATH = _EVAL_DIR / "contract.json"
_ITEMS_PATH = _EVAL_DIR / "items.json"
_LABELS_PATH = _EVAL_DIR / "labels.json"
_REPLAY_SCRIPT = _REPO_ROOT / "scripts" / "replay_prefilter.py"
_MIN_ITEM_COUNT = 129


def _load_replay_module():
    spec = importlib.util.spec_from_file_location("replay_prefilter", _REPLAY_SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_g6_prefilter_gold_artifacts_exist() -> None:
    for path in (_CONTRACT_PATH, _ITEMS_PATH, _LABELS_PATH, _REPLAY_SCRIPT):
        assert path.is_file(), f"missing G6 prefilter gold artifact: {path}"


def test_g6_prefilter_gold_item_count_at_least_129() -> None:
    payload = json.loads(_ITEMS_PATH.read_text(encoding="utf-8"))
    declared = int(payload.get("count", 0))
    items = payload.get("items")
    assert isinstance(items, list)
    assert declared >= _MIN_ITEM_COUNT, f"count field {declared} < {_MIN_ITEM_COUNT}"
    assert len(items) >= _MIN_ITEM_COUNT, f"items array length {len(items)} < {_MIN_ITEM_COUNT}"


def test_g6_prefilter_gold_labels_cover_items() -> None:
    items_payload = json.loads(_ITEMS_PATH.read_text(encoding="utf-8"))
    labels_payload = json.loads(_LABELS_PATH.read_text(encoding="utf-8"))
    item_ids = {item["id"] for item in items_payload["items"]}
    label_ids = set(labels_payload.get("labels", {}))
    assert len(label_ids) >= _MIN_ITEM_COUNT
    missing = item_ids - label_ids
    assert not missing, f"labels missing for {len(missing)} items: {sorted(missing)[:5]}"


def test_g6_prefilter_replay_script_importable() -> None:
    module = _load_replay_module()
    assert callable(getattr(module, "main", None))
    assert callable(getattr(module, "parse_decision", None))
