"""GitHub closed-range harvest tests. Incremental DISCOVERED path stays intact."""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import ModuleType
from unittest.mock import AsyncMock, patch
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from bishop_shared.enums import DomainEnum, SourceEnum
from bishop_shared.harvest_ledger import connect_rw, get_cursor, set_cursor

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRAPER_ROOT = _REPO_ROOT / "services" / "scraper"

_START = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)
_SEVEN = _START + timedelta(days=7)
_ONE = _START + timedelta(days=1)


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _load_harvest_stack() -> tuple[ModuleType, ModuleType]:
    """Load scraper harvest + github without shadowing state-worker ``app``."""
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
        import app.adapters.github as github  # noqa: WPS433
        import app.harvest_github as harvest  # noqa: WPS433
        import app.models as models  # noqa: WPS433

        github.ManifestIngestEntry = models.ManifestIngestEntry  # type: ignore[attr-defined]
    finally:
        for name in list(sys.modules):
            if name == "app" or name.startswith("app."):
                del sys.modules[name]
        sys.modules.update(saved_app_modules)
        for path_str in path_state:
            sys.path.remove(path_str)

    return github, harvest


def _load_scraper_loop_stack() -> tuple[ModuleType, ModuleType]:
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
        import app.loop as loop_mod  # noqa: WPS433
        import app.models as models  # noqa: WPS433
    finally:
        for name in list(sys.modules):
            if name == "app" or name.startswith("app."):
                del sys.modules[name]
        sys.modules.update(saved_app_modules)
        for path_str in path_state:
            sys.path.remove(path_str)

    return loop_mod, models


def _search_q(request: httpx.Request) -> str:
    return parse_qs(urlparse(str(request.url)).query)["q"][0]


def _params(request: httpx.Request) -> dict[str, list[str]]:
    return parse_qs(urlparse(str(request.url)).query)


def _repo_item(
    full_name: str,
    *,
    fork: bool = False,
    extra: dict[str, object] | None = None,
) -> dict[str, object]:
    owner, name = full_name.split("/", 1)
    item: dict[str, object] = {
        "id": abs(hash(full_name)) % 10_000_000,
        "full_name": full_name,
        "name": name,
        "description": "A repo.",
        "html_url": f"https://github.com/{full_name}",
        "fork": fork,
        "archived": False,
        "disabled": False,
        "language": "Python",
        "license": {"spdx_id": "MIT", "name": "MIT License"},
        "stargazers_count": 42,
        "forks_count": 3,
        "open_issues_count": 1,
        "size": 128,
        "topics": ["ml"],
        "homepage": "https://example.com",
        "default_branch": "main",
        "visibility": "public",
        "score": 1.5,
        "created_at": "2025-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
        "pushed_at": "2026-01-01T12:00:00Z",
        "owner": {"login": owner, "type": "Organization", "id": 99},
        "node_id": "R_extra",
    }
    if extra:
        item.update(extra)
    return item


async def _instant_acquire(self: object) -> None:
    return None


def test_build_harvest_query_closed_range_not_open_ended() -> None:
    github, _ = _load_harvest_stack()
    query = github.build_harvest_query(_START, _SEVEN)
    assert query == "pushed:2026-01-01..2026-01-08 stars:>10"
    assert "pushed:>" not in query


def test_parse_harvest_candidate_maps_stars_fork_language_license() -> None:
    github, _ = _load_harvest_stack()
    adapter = github.GitHubAdapter()
    item = _repo_item("acme/ml-tools", fork=True)
    candidate = github.parse_harvest_candidate(
        item,
        adapter=adapter,
        harvest_query_id="github-pushed-stars10-v1",
    )
    assert candidate.source_id == "github:acme/ml-tools"
    assert candidate.github_id == item["id"]
    assert candidate.stargazers_count == 42
    assert candidate.is_fork is True
    assert candidate.language == "Python"
    assert candidate.license_spdx == "MIT"
    assert candidate.full_name == "acme/ml-tools"
    extras = json.loads(candidate.extras_json or "{}")
    assert "full_name" not in extras
    assert extras.get("node_id") == "R_extra"


def test_fetch_manifest_query_still_open_ended_pushed_gt() -> None:
    github, _ = _load_harvest_stack()
    query = github.build_search_query(_START)
    assert query.startswith("pushed:>")
    assert "pushed:>2026-01-01" in query


@pytest.mark.asyncio
async def test_harvest_recursive_split_emits_distinct_closed_ranges(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, harvest = _load_harvest_stack()
    monkeypatch.setattr(harvest, "BISHOP_HARVEST_ENABLED", True)
    monkeypatch.setattr(harvest.TokenBucketRateLimiter, "acquire", _instant_acquire)

    queries: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        query = _search_q(request)
        queries.append(query)
        params = _params(request)
        per_page = int(params.get("per_page", ["100"])[0])
        if per_page == 1:
            return httpx.Response(
                200,
                json={"total_count": 2500, "incomplete_results": False, "items": []},
            )
        page = int(params.get("page", ["1"])[0])
        items = [_repo_item(f"acme/split-{page}")]
        return httpx.Response(
            200,
            json={"total_count": 2500, "incomplete_results": False, "items": items},
        )

    db = tmp_path / "ledger.sqlite"
    conn = connect_rw(db)
    try:
        set_cursor(
            conn,
            "github",
            next_window_start=_iso(_START),
            harvest_until=_iso(_SEVEN),
            now=_START,
        )
    finally:
        conn.close()

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        await harvest.harvest_github_slices(
            http_client=client,
            deadline=datetime.now(UTC) + timedelta(hours=1),
            db_path=db,
        )

    distinct = list(dict.fromkeys(queries))
    assert len(distinct) >= 2
    for query in distinct:
        assert query.startswith("pushed:")
        assert ".." in query
        assert "pushed:>" not in query
        assert "stars:>10" in query


@pytest.mark.asyncio
async def test_harvest_one_day_overflow_caps_pages_and_advances_cursor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, harvest = _load_harvest_stack()
    monkeypatch.setattr(harvest, "BISHOP_HARVEST_ENABLED", True)
    monkeypatch.setattr(harvest.TokenBucketRateLimiter, "acquire", _instant_acquire)

    item_pages: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        params = _params(request)
        per_page = int(params.get("per_page", ["100"])[0])
        page = int(params.get("page", ["1"])[0])
        if per_page == 1:
            return httpx.Response(
                200,
                json={"total_count": 5000, "incomplete_results": False, "items": []},
                headers={"X-RateLimit-Remaining": "20", "X-RateLimit-Reset": "1780000000"},
            )
        item_pages.append(page)
        items = [_repo_item(f"acme/day-{page}-{idx}", fork=True) for idx in range(100)]
        return httpx.Response(
            200,
            json={"total_count": 5000, "incomplete_results": False, "items": items},
        )

    db = tmp_path / "ledger.sqlite"
    conn = connect_rw(db)
    try:
        set_cursor(
            conn,
            "github",
            next_window_start=_iso(_START),
            harvest_until=_iso(_ONE),
            now=_START,
        )
    finally:
        conn.close()

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        await harvest.harvest_github_slices(
            http_client=client,
            deadline=datetime.now(UTC) + timedelta(hours=1),
            db_path=db,
        )

    assert item_pages == list(range(1, 11))
    conn = connect_rw(db)
    try:
        run = conn.execute(
            "SELECT incomplete_results, pages_fetched FROM harvest_runs"
        ).fetchone()
        assert run["incomplete_results"] == 1
        assert run["pages_fetched"] == 10
        cursor = get_cursor(conn, "github")
        assert cursor is not None
        advanced = datetime.fromisoformat(
            cursor["next_window_start"].replace("Z", "+00:00")
        )
        assert advanced == _ONE
        fork_row = conn.execute(
            "SELECT is_fork FROM candidates WHERE source_id = ?",
            ("github:acme/day-1-0",),
        ).fetchone()
        assert fork_row["is_fork"] == 1
    finally:
        conn.close()


@pytest.mark.asyncio
async def test_harvest_does_not_call_post_manifest_batch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, harvest = _load_harvest_stack()
    monkeypatch.setattr(harvest, "BISHOP_HARVEST_ENABLED", True)
    monkeypatch.setattr(harvest.TokenBucketRateLimiter, "acquire", _instant_acquire)
    source = Path(harvest.__file__).read_text(encoding="utf-8")
    assert "post_manifest_batch" not in source

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "total_count": 1,
                "incomplete_results": False,
                "items": [_repo_item("acme/one")],
            },
        )

    db = tmp_path / "ledger.sqlite"
    conn = connect_rw(db)
    try:
        set_cursor(
            conn,
            "github",
            next_window_start=_iso(_START),
            harvest_until=_iso(_ONE),
            now=_START,
        )
    finally:
        conn.close()

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        await harvest.harvest_github_slices(
            http_client=client,
            deadline=datetime.now(UTC) + timedelta(hours=1),
            db_path=db,
        )

    conn = connect_rw(db)
    try:
        row = conn.execute(
            "SELECT source_id FROM candidates WHERE source_id = ?",
            ("github:acme/one",),
        ).fetchone()
        assert row is not None
    finally:
        conn.close()


@pytest.mark.asyncio
async def test_harvest_uses_search_rate_limit_not_rest_budget(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Falsifier: Search harvest must not use GitHub REST 5000/hr SOURCE_RATE_LIMITS."""
    github, harvest = _load_harvest_stack()
    monkeypatch.setattr(harvest, "BISHOP_HARVEST_ENABLED", True)
    monkeypatch.setattr(harvest.TokenBucketRateLimiter, "acquire", _instant_acquire)
    captured: dict[str, object] = {}
    real_init = harvest.TokenBucketRateLimiter.__init__

    def _init(self: object, rate_limit: object, *args: object, **kwargs: object) -> None:
        captured["limit"] = rate_limit
        real_init(self, rate_limit)

    monkeypatch.setattr(harvest.TokenBucketRateLimiter, "__init__", _init)

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"total_count": 0, "incomplete_results": False, "items": []},
        )

    db = tmp_path / "ledger.sqlite"
    conn = connect_rw(db)
    try:
        set_cursor(
            conn,
            "github",
            next_window_start=_iso(_START),
            harvest_until=_iso(_ONE),
            now=_START,
        )
    finally:
        conn.close()

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        await harvest.harvest_github_slices(
            http_client=client,
            deadline=datetime.now(UTC) + timedelta(hours=1),
            db_path=db,
        )

    limit = captured["limit"]
    assert getattr(limit, "calls") == 1
    assert getattr(limit, "period_seconds") == 2
    rest = github.SOURCE_RATE_LIMITS[SourceEnum.GITHUB.value]
    assert getattr(limit, "calls") != rest.calls
    assert getattr(limit, "period_seconds") != rest.period_seconds


@pytest.mark.asyncio
async def test_scrape_cycle_harvest_failure_still_posts_discovered() -> None:
    """Harvest exceptions must not fail the incremental DISCOVERED scrape."""
    loop_mod, models = _load_scraper_loop_stack()
    entry = models.ManifestIngestEntry(
        source_id="arxiv:2406.00001",
        source=SourceEnum.ARXIV,
        url="http://arxiv.org/abs/2406.00001",
        title="Example Paper",
        domain=DomainEnum.PROFESSIONAL,
    )

    class _StubAdapter:
        source = SourceEnum.ARXIV
        domain = DomainEnum.PROFESSIONAL

        def __init__(self) -> None:
            self.fetch_manifest = AsyncMock(return_value=[entry])

    adapter = _StubAdapter()

    def _factory() -> object:
        return adapter

    client = AsyncMock()
    client.get_scraper_state.return_value = models.ScraperStateSnapshot(
        source=SourceEnum.ARXIV,
        last_successful_run_at=datetime(2026, 6, 10, 8, 0, 0, tzinfo=UTC),
        updated_at=datetime(2026, 6, 12, 12, 0, 0, tzinfo=UTC),
    )
    client.post_manifest_batch.return_value = models.ManifestBatchResult(
        inserted=1,
        skipped=0,
    )

    with (
        patch.object(loop_mod, "ADAPTER_REGISTRY", [_factory]),
        patch.object(loop_mod, "BISHOP_HARVEST_ENABLED", True),
        patch.object(
            loop_mod,
            "harvest_github_slices",
            AsyncMock(side_effect=RuntimeError("harvest boom")),
        ),
    ):
        await loop_mod.scrape_cycle(client)

    client.post_manifest_batch.assert_awaited_once_with([entry])
    client.post_scraper_state.assert_awaited_once()


def test_harvest_http_client_uses_30s_timeout() -> None:
    """Live GitHub Search exceeded httpx's 5s default; harvest must not."""
    source = (_REPO_ROOT / "services" / "scraper" / "app" / "loop.py").read_text(
        encoding="utf-8"
    )
    assert "httpx.Timeout(30.0)" in source
    assert "async with httpx.AsyncClient()" not in source
