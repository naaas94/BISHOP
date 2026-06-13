"""M4 integration tests — mocked e2e across state-worker and content-scraper (T4)."""

from __future__ import annotations

import asyncio
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType
from unittest.mock import AsyncMock, patch

import aiosqlite
import httpx
import pytest
from fastapi.testclient import TestClient

from bishop_shared.enums import DomainEnum, SourceEnum

_REPO_ROOT = Path(__file__).resolve().parent.parent
_STATE_WORKER_ROOT = _REPO_ROOT / "services" / "state-worker"
_CONTENT_SCRAPER_ROOT = _REPO_ROOT / "services" / "content-scraper"
_SCRAPER_SRC = _REPO_ROOT / "services" / "scraper" / "app"

for path in (_STATE_WORKER_ROOT, _REPO_ROOT):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

from app.enums import ProcessingState  # noqa: E402
from app.main import app  # noqa: E402

_NOW = datetime(2026, 6, 13, 12, 0, 0, tzinfo=UTC)
_SOURCE = "arxiv:2301.00001"
_BATCH_ID = "m4-e2e-batch-1"
_CONTENT_RAW = "Full paper text from mocked ArXiv HTML fetch."


def _patch_db_path(monkeypatch: pytest.MonkeyPatch, db_path: Path) -> None:
    monkeypatch.setattr("app.db.SQLITE_DB_PATH", str(db_path))


def _manifest_batch_payload(source_id: str = _SOURCE) -> dict:
    return {
        "entries": [
            {
                "source_id": source_id,
                "source": SourceEnum.ARXIV.value,
                "url": f"https://arxiv.org/abs/{source_id.removeprefix('arxiv:')}",
                "title": "M4 Integration Paper",
                "abstract": "An abstract for content scrape.",
                "published_at": _NOW.isoformat().replace("+00:00", "Z"),
                "domain": DomainEnum.PROFESSIONAL.value,
            }
        ]
    }


def _pre_filter_payload(source_id: str = _SOURCE) -> dict:
    return {
        "batch_id": _BATCH_ID,
        "profile_version": "1.0.0",
        "entries": [
            {
                "source_id": source_id,
                "decision": 1,
                "pre_filter_rationale": "Relevant for M4 integration.",
            }
        ],
    }


def _seed_relevance_passed(client: TestClient, source_id: str = _SOURCE) -> None:
    ingest = client.post("/manifest/batch", json=_manifest_batch_payload(source_id))
    assert ingest.status_code == 200
    discovered = client.get(
        "/manifest/poll",
        params={"state": ProcessingState.DISCOVERED.value, "limit": 10},
    )
    assert discovered.status_code == 200
    assert discovered.json()["claimed_count"] == 1
    pre_filter = client.post("/manifest/pre-filter-results", json=_pre_filter_payload(source_id))
    assert pre_filter.status_code == 200


def _vendor_scraper_app(target_root: Path) -> None:
    scraper_dst = target_root / "scraper_app"
    if scraper_dst.exists():
        shutil.rmtree(scraper_dst)
    shutil.copytree(_SCRAPER_SRC, scraper_dst)
    for py_file in scraper_dst.rglob("*.py"):
        text = py_file.read_text(encoding="utf-8")
        text = text.replace("from app.", "from scraper_app.").replace(
            "import app.",
            "import scraper_app.",
        )
        py_file.write_text(text, encoding="utf-8")


def _load_content_scraper_stack(
    tmp_path: Path,
) -> tuple[ModuleType, ModuleType, ModuleType]:
    saved_modules = {
        name: module
        for name, module in sys.modules.items()
        if name == "app"
        or name.startswith("app.")
        or name == "scraper_app"
        or name.startswith("scraper_app.")
    }
    for name in saved_modules:
        del sys.modules[name]

    vendor_root = tmp_path / "vendor"
    vendor_root.mkdir()
    _vendor_scraper_app(vendor_root)

    repo_str = str(_REPO_ROOT)
    worker_str = str(_CONTENT_SCRAPER_ROOT)
    vendor_str = str(vendor_root)
    path_state: list[str] = []
    for path_str in (worker_str, vendor_str, repo_str):
        if path_str not in sys.path:
            sys.path.insert(0, path_str)
            path_state.append(path_str)

    try:
        import app.loop as loop_mod  # noqa: WPS433
        import app.state_worker_client as client_mod  # noqa: WPS433
        import scraper_app.exceptions as exceptions_mod  # noqa: WPS433
    finally:
        for name in list(sys.modules):
            if (
                name == "app"
                or name.startswith("app.")
                or name == "scraper_app"
                or name.startswith("scraper_app.")
            ):
                del sys.modules[name]
        sys.modules.update(saved_modules)
        for path_str in path_state:
            sys.path.remove(path_str)

    return loop_mod, client_mod, exceptions_mod


async def _entry_row(db_path: Path, source_id: str) -> tuple[str | None, str | None] | None:
    async with aiosqlite.connect(db_path) as conn:
        cursor = await conn.execute(
            "SELECT content_raw, processing_state FROM entries WHERE source_id = ?",
            (source_id,),
        )
        row = await cursor.fetchone()
    if row is None:
        return None
    return row[0], row[1]


async def _manifest_state(db_path: Path, source_id: str) -> str | None:
    async with aiosqlite.connect(db_path) as conn:
        cursor = await conn.execute(
            "SELECT processing_state FROM manifest WHERE source_id = ?",
            (source_id,),
        )
        row = await cursor.fetchone()
    return row[0] if row else None


async def _latest_error_log(db_path: Path, source_id: str) -> tuple[int, str] | None:
    async with aiosqlite.connect(db_path) as conn:
        cursor = await conn.execute(
            """
            SELECT is_retriable, state_at_failure
            FROM error_log
            WHERE source_id = ?
            ORDER BY timestamp DESC
            LIMIT 1
            """,
            (source_id,),
        )
        row = await cursor.fetchone()
    if row is None:
        return None
    return int(row[0]), row[1]


@pytest.fixture
def integration_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "bishop.db"
    _patch_db_path(monkeypatch, db_path)
    monkeypatch.setattr("app.sweeps.SWEEP_INTERVAL_SEC", 3600.0)
    with TestClient(app) as client:
        yield client, db_path


def test_m4_e2e_content_scrape_cycle_reaches_scraped_with_content_raw(
    integration_client: tuple[TestClient, Path],
    tmp_path: Path,
) -> None:
    """Contract: poll RELEVANCE_PASSED → fetch_content → POST content yields SCRAPED row."""
    client, db_path = integration_client
    _seed_relevance_passed(client)

    loop_mod, client_mod, _ = _load_content_scraper_stack(tmp_path)

    async def _run_cycle() -> None:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
            sw_client = client_mod.StateWorkerClient(client=http)
            with patch.object(
                loop_mod,
                "failure_envelope",
                new_callable=AsyncMock,
                return_value=_CONTENT_RAW,
            ):
                await loop_mod.content_scrape_cycle(sw_client)

    asyncio.run(_run_cycle())

    entry = asyncio.run(_entry_row(db_path, _SOURCE))
    assert entry is not None
    content_raw, processing_state = entry
    assert content_raw == _CONTENT_RAW
    assert processing_state == ProcessingState.SCRAPED.value

    manifest_state = asyncio.run(_manifest_state(db_path, _SOURCE))
    assert manifest_state == ProcessingState.SCRAPED.value


def test_m4_e2e_retriable_fetch_failure_yields_scrape_failed_and_error_log(
    integration_client: tuple[TestClient, Path],
    tmp_path: Path,
) -> None:
    """Contract: RetryExhaustedError → SCRAPE_FAILED manifest + error_log.is_retriable=1."""
    client, db_path = integration_client
    _seed_relevance_passed(client)

    loop_mod, client_mod, exceptions_mod = _load_content_scraper_stack(tmp_path)
    cause = httpx.HTTPStatusError(
        "service unavailable",
        request=httpx.Request("GET", "https://arxiv.org/html/2301.00001"),
        response=httpx.Response(503, request=httpx.Request("GET", "https://arxiv.org/html/2301.00001")),
    )
    retry_exc = exceptions_mod.RetryExhaustedError(SourceEnum.ARXIV, 4, cause)

    async def _run_cycle() -> None:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
            sw_client = client_mod.StateWorkerClient(client=http)
            with patch.object(
                loop_mod,
                "failure_envelope",
                new_callable=AsyncMock,
                side_effect=retry_exc,
            ):
                await loop_mod.content_scrape_cycle(sw_client)

    asyncio.run(_run_cycle())

    manifest_state = asyncio.run(_manifest_state(db_path, _SOURCE))
    assert manifest_state == ProcessingState.SCRAPE_FAILED.value

    error_log = asyncio.run(_latest_error_log(db_path, _SOURCE))
    assert error_log is not None
    is_retriable, state_at_failure = error_log
    assert is_retriable == 1
    assert state_at_failure == ProcessingState.SCRAPE_QUEUED.value

    entry = asyncio.run(_entry_row(db_path, _SOURCE))
    assert entry is None
