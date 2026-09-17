"""Closeout checks for harvest mill loop (PB-011) narrative landing."""

from __future__ import annotations

from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent
_BACKLOG_PATH = _REPO_ROOT / "product-backlog.yaml"
_PICKUP_PATH = _REPO_ROOT / "harvest-pool-next.md"
_CHANGELOG_PATH = _REPO_ROOT / "CHANGELOG.MD"

_T4_MARKER = "`_mill_loop`, `BISHOP_HARVEST_MILL_INTERVAL_SEC` default 5s"


def _items_by_id() -> dict[str, dict[str, object]]:
    data = yaml.safe_load(_BACKLOG_PATH.read_text(encoding="utf-8"))
    return {item["id"]: item for item in data["items"]}


def test_pb011_is_shipped() -> None:
    item = _items_by_id()["PB-011"]
    assert item["status"] == "shipped"
    assert item["updated"] == "2026-09-17"


def test_pb012_status_remains_deferred() -> None:
    item = _items_by_id()["PB-012"]
    assert item["status"] == "deferred"


def test_harvest_pool_next_status_no_longer_hitchhiker() -> None:
    text = _PICKUP_PATH.read_text(encoding="utf-8")
    status_block = text.split("**Next:**", 1)[0]
    assert "90s hitchhiker" not in status_block
    assert ".dev/decision-logs/ops/harvest-mill-loop.md" in text
    assert "no longer coupled to `BISHOP_SCRAPER_SCHEDULE_INTERVAL_SEC`" in text


def test_changelog_t4_mill_bullet_is_in_exactly_one_dated_section() -> None:
    """Falsifier: the T4 mill-loop bullet must not be duplicated or split across dated sections."""
    text = _CHANGELOG_PATH.read_text(encoding="utf-8")
    sections = text.split("\n## ")
    matching = [section for section in sections if _T4_MARKER in section]
    assert len(matching) == 1
    assert matching[0].lstrip("# ").startswith("harvest-mill-loop — 2026-09-17")
    assert text.count(_T4_MARKER) == 1
