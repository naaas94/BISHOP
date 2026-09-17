"""GitHub harvest release tap — budget gate, skip-if-exists stamp, HTTP failure."""

from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import ModuleType
from unittest.mock import AsyncMock

import httpx
import pytest

from bishop_shared.enums import DomainEnum, SourceEnum
from bishop_shared.harvest_ledger import HarvestCandidate, connect_rw

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRAPER_ROOT = _REPO_ROOT / "services" / "scraper"
_ECON = _REPO_ROOT / "config" / "harvest" / "economics.yaml"
_NOW = datetime(2026, 9, 17, 15, 0, 0, tzinfo=UTC)
_PUSHED = (_NOW - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_harvest_release_stack() -> tuple[ModuleType, ModuleType]:
    """Load scraper harvest_release without shadowing state-worker ``app``."""
    saved_app_modules = {
        name: module
        for name, module in sys.modules.items()
        if name == "app" or name.startswith("app.")
    }
    for name in saved_app_modules:
        del sys.modules[name]

    repo_str = str(_REPO_ROOT)
    scraper_str = str(_SCRAPER_ROOT)
    path_state: list[str] = []
    for path_str in (scraper_str, repo_str):
        if path_str not in sys.path:
            sys.path.insert(0, path_str)
            path_state.append(path_str)

    try:
        import app.harvest_release as harvest_mod  # noqa: WPS433
        import app.models as models  # noqa: WPS433
    finally:
        for name in list(sys.modules):
            if name == "app" or name.startswith("app."):
                del sys.modules[name]
        sys.modules.update(saved_app_modules)
        for path_str in path_state:
            sys.path.remove(path_str)

    return harvest_mod, models


def _candidate(source_id: str) -> HarvestCandidate:
    return HarvestCandidate(
        source_id=source_id,
        source="github",
        url=f"https://github.com/{source_id.removeprefix('github:')}",
        title=source_id,
        abstract="tagline",
        pushed_at=_PUSHED,
    )


def _seed_ledger(path: Path, source_ids: list[str]) -> None:
    conn = connect_rw(path)
    try:
        from bishop_shared.harvest_ledger import upsert_candidates

        upsert_candidates(conn, [_candidate(sid) for sid in source_ids], now=_NOW)
    finally:
        conn.close()


def _released_at(path: Path, source_id: str) -> str | None:
    conn = connect_rw(path)
    try:
        row = conn.execute(
            "SELECT released_at FROM candidates WHERE source_id = ?",
            (source_id,),
        ).fetchone()
    finally:
        conn.close()
    assert row is not None
    return row["released_at"]


@pytest.mark.asyncio
async def test_release_once_n_cap_zero_does_not_post(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harvest_mod, _ = _load_harvest_release_stack()
    monkeypatch.setenv("BISHOP_HARVEST_ECONOMICS_PATH", str(_ECON))
    monkeypatch.setenv("BISHOP_HARVEST_DAILY_BUDGET_USD", "0")
    ledger = tmp_path / "ledger.sqlite"
    _seed_ledger(ledger, ["github:a/one"])
    client = AsyncMock()

    await harvest_mod.release_once(client, db_path=ledger)

    client.post_manifest_batch.assert_not_awaited()
    client.count_manifest.assert_not_awaited()
    assert _released_at(ledger, "github:a/one") is None


@pytest.mark.asyncio
async def test_release_once_queue_full_does_not_post(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harvest_mod, _ = _load_harvest_release_stack()
    monkeypatch.setenv("BISHOP_HARVEST_ECONOMICS_PATH", str(_ECON))
    monkeypatch.delenv("BISHOP_HARVEST_DAILY_BUDGET_USD", raising=False)
    ledger = tmp_path / "ledger.sqlite"
    _seed_ledger(ledger, ["github:a/one"])
    client = AsyncMock()
    client.count_manifest = AsyncMock(return_value=10_000)

    await harvest_mod.release_once(client, db_path=ledger)

    client.post_manifest_batch.assert_not_awaited()
    assert _released_at(ledger, "github:a/one") is None


@pytest.mark.asyncio
async def test_release_once_success_marks_skipped(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harvest_mod, models = _load_harvest_release_stack()
    monkeypatch.setenv("BISHOP_HARVEST_ECONOMICS_PATH", str(_ECON))
    monkeypatch.delenv("BISHOP_HARVEST_DAILY_BUDGET_USD", raising=False)
    ledger = tmp_path / "ledger.sqlite"
    source_id = "github:a/one"
    _seed_ledger(ledger, [source_id])
    client = AsyncMock()
    client.count_manifest = AsyncMock(return_value=0)
    client.post_manifest_batch = AsyncMock(
        return_value=models.ManifestBatchResult(inserted=0, skipped=1),
    )

    await harvest_mod.release_once(client, db_path=ledger)

    client.post_manifest_batch.assert_awaited_once()
    posted = client.post_manifest_batch.await_args.args[0]
    assert len(posted) == 1
    entry = posted[0]
    assert isinstance(entry, models.ManifestIngestEntry)
    assert entry.source_id == source_id
    assert entry.source == SourceEnum.GITHUB
    assert entry.url == "https://github.com/a/one"
    assert entry.title == source_id
    assert entry.abstract == "tagline"
    assert entry.published_at == datetime.fromisoformat(_PUSHED.replace("Z", "+00:00"))
    assert entry.domain == DomainEnum.PROFESSIONAL
    assert _released_at(ledger, source_id) is not None


@pytest.mark.asyncio
async def test_release_once_http_error_leaves_unreleased(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harvest_mod, _ = _load_harvest_release_stack()
    monkeypatch.setenv("BISHOP_HARVEST_ECONOMICS_PATH", str(_ECON))
    monkeypatch.delenv("BISHOP_HARVEST_DAILY_BUDGET_USD", raising=False)
    ledger = tmp_path / "ledger.sqlite"
    source_id = "github:a/one"
    _seed_ledger(ledger, [source_id])
    client = AsyncMock()
    client.count_manifest = AsyncMock(return_value=0)
    request = httpx.Request("POST", "http://state-worker:8000/manifest/batch")
    response = httpx.Response(500, request=request)
    client.post_manifest_batch = AsyncMock(
        side_effect=httpx.HTTPStatusError(
            "error",
            request=request,
            response=response,
        )
    )

    await harvest_mod.release_once(client, db_path=ledger)

    client.post_manifest_batch.assert_awaited_once()
    assert _released_at(ledger, source_id) is None


@pytest.mark.asyncio
async def test_release_once_caps_at_release_batch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Kill: a tick must not POST more than BISHOP_HARVEST_RELEASE_BATCH rows."""
    harvest_mod, models = _load_harvest_release_stack()
    monkeypatch.setenv("BISHOP_HARVEST_ECONOMICS_PATH", str(_ECON))
    monkeypatch.delenv("BISHOP_HARVEST_DAILY_BUDGET_USD", raising=False)
    monkeypatch.setattr(harvest_mod, "BISHOP_HARVEST_RELEASE_BATCH", 2)
    ledger = tmp_path / "ledger.sqlite"
    ids = [f"github:a/{i}" for i in range(5)]
    _seed_ledger(ledger, ids)
    client = AsyncMock()
    client.count_manifest = AsyncMock(return_value=0)
    client.post_manifest_batch = AsyncMock(
        return_value=models.ManifestBatchResult(inserted=2, skipped=0),
    )

    await harvest_mod.release_once(client, db_path=ledger)

    client.post_manifest_batch.assert_awaited_once()
    posted = client.post_manifest_batch.await_args.args[0]
    assert len(posted) == 2
    assert len(posted) <= harvest_mod.BISHOP_HARVEST_RELEASE_BATCH
