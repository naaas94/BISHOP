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
_FLOOR = datetime(2024, 12, 15, 20, 18, 40, tzinfo=UTC)
_FROZEN_CEILING = datetime(2026, 9, 17, 14, 18, 40, tzinfo=UTC)
_NOW = datetime(2026, 9, 27, 12, 0, 0, tzinfo=UTC)


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


def _seed_cursor(
    db: Path,
    *,
    next_window_start: datetime,
    harvest_until: datetime,
    now: datetime,
    walk_direction: str | None = None,
    high_water: datetime | None = None,
) -> None:
    conn = connect_rw(db)
    try:
        set_cursor(
            conn,
            "github",
            next_window_start=_iso(next_window_start),
            harvest_until=_iso(harvest_until),
            now=now,
            walk_direction=walk_direction,
            high_water=_iso(high_water) if high_water is not None else None,
        )
    finally:
        conn.close()


def _stop_after_first_slice(harvest: ModuleType, monkeypatch: pytest.MonkeyPatch, now: datetime) -> datetime:
    """Freeze harvest clock at ``now`` until the first slice is recorded, then expire the deadline."""
    state = {"after_slice": False}
    real_record = harvest.record_run

    def _record(*args: object, **kwargs: object) -> None:
        real_record(*args, **kwargs)
        state["after_slice"] = True

    monkeypatch.setattr(harvest, "record_run", _record)

    def _frozen() -> datetime:
        if state["after_slice"]:
            return now + timedelta(hours=2)
        return now

    monkeypatch.setattr(harvest, "_utc_now", _frozen)
    return now + timedelta(hours=1)


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
    _seed_cursor(
        db,
        next_window_start=_START,
        harvest_until=_SEVEN,
        now=_START,
        walk_direction="backward",
        high_water=_SEVEN,
    )
    deadline = _stop_after_first_slice(harvest, monkeypatch, _SEVEN)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        await harvest.harvest_github_slices(
            http_client=client,
            deadline=deadline,
            db_path=db,
        )

    distinct = list(dict.fromkeys(queries))
    assert len(distinct) >= 2
    for query in distinct:
        assert query.startswith("pushed:")
        assert ".." in query
        assert "pushed:>" not in query
        assert "stars:>10" in query
    full = "pushed:2026-01-01..2026-01-08 stars:>10"
    newer = "pushed:2026-01-04..2026-01-08 stars:>10"
    assert distinct[0] == full
    after_full = [query for query in distinct if query != full]
    assert after_full[0] == newer


@pytest.mark.asyncio
async def test_harvest_one_day_overflow_caps_pages_and_retreats_cursor(
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
    _seed_cursor(
        db,
        next_window_start=_START,
        harvest_until=_ONE,
        now=_START,
        walk_direction="backward",
        high_water=_NOW,
    )
    deadline = _stop_after_first_slice(harvest, monkeypatch, _ONE)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        await harvest.harvest_github_slices(
            http_client=client,
            deadline=deadline,
            db_path=db,
        )

    assert item_pages == list(range(1, 11))
    conn = connect_rw(db)
    try:
        run = conn.execute(
            "SELECT incomplete_results, pages_fetched, window_start, window_end "
            "FROM harvest_runs"
        ).fetchone()
        assert run["incomplete_results"] == 1
        assert run["pages_fetched"] == 10
        cursor = get_cursor(conn, "github")
        assert cursor is not None
        # 1-day remaining gap retreats then meets the floor → done writes high_water.
        assert cursor["walk_direction"] == "forward"
        assert cursor["next_window_start"] == _iso(_NOW)
        assert cursor["harvest_until"] == _iso(_NOW)
        assert cursor["next_window_start"] != _iso(_ONE) or cursor["walk_direction"] == "forward"
        fork_row = conn.execute(
            "SELECT is_fork FROM candidates WHERE source_id = ?",
            ("github:acme/day-1-0",),
        ).fetchone()
        assert fork_row["is_fork"] == 1
        leftover = conn.execute("SELECT COUNT(*) FROM candidates").fetchone()[0]
        assert leftover > 0
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
    _seed_cursor(
        db,
        next_window_start=_START,
        harvest_until=_ONE,
        now=_START,
        walk_direction="backward",
        high_water=_NOW,
    )

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


def test_scrape_cycle_no_longer_calls_harvest_github_slices() -> None:
    """Falsifier: hitchhike removed — scrape_cycle must not import/call the mill."""
    source = (
        _REPO_ROOT / "services" / "scraper" / "app" / "loop.py"
    ).read_text(encoding="utf-8")
    assert "harvest_github_slices" not in source


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
    _seed_cursor(
        db,
        next_window_start=_START,
        harvest_until=_ONE,
        now=_START,
        walk_direction="backward",
        high_water=_NOW,
    )

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


def test_harvest_http_client_uses_30s_timeout() -> None:
    """Live GitHub Search exceeded httpx's 5s default; harvest must not."""
    source = (_REPO_ROOT / "services" / "scraper" / "app" / "main.py").read_text(
        encoding="utf-8"
    )
    assert "httpx.Timeout(30.0)" in source
    assert "async with httpx.AsyncClient()" not in source


def _ok_item_handler(full_name: str = "acme/now"):
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "total_count": 1,
                "incomplete_results": False,
                "items": [_repo_item(full_name)],
            },
        )

    return handler


@pytest.mark.asyncio
async def test_legacy_forward_cursor_first_tick_ends_at_now_without_raising_floor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, harvest = _load_harvest_stack()
    monkeypatch.setattr(harvest, "BISHOP_HARVEST_ENABLED", True)
    monkeypatch.setattr(harvest.TokenBucketRateLimiter, "acquire", _instant_acquire)
    queries: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        queries.append(_search_q(request))
        return _ok_item_handler()(request)

    db = tmp_path / "ledger.sqlite"
    _seed_cursor(
        db,
        next_window_start=_FLOOR,
        harvest_until=_FROZEN_CEILING,
        now=_FLOOR,
    )
    deadline = _stop_after_first_slice(harvest, monkeypatch, _NOW)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        await harvest.harvest_github_slices(
            http_client=client,
            deadline=deadline,
            db_path=db,
        )

    expected = "pushed:2026-09-20..2026-09-27 stars:>10"
    assert expected in queries
    conn = connect_rw(db)
    try:
        cursor = get_cursor(conn, "github")
        assert cursor is not None
        assert cursor["next_window_start"] == _iso(_FLOOR)
        retreated = datetime.fromisoformat(
            cursor["harvest_until"].replace("Z", "+00:00")
        )
        assert retreated == _NOW - timedelta(days=7)
        assert cursor["walk_direction"] == "backward"
        assert cursor["high_water"] == _iso(_NOW)
    finally:
        conn.close()


@pytest.mark.asyncio
async def test_second_tick_is_next_older_window(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, harvest = _load_harvest_stack()
    monkeypatch.setattr(harvest, "BISHOP_HARVEST_ENABLED", True)
    monkeypatch.setattr(harvest.TokenBucketRateLimiter, "acquire", _instant_acquire)
    db = tmp_path / "ledger.sqlite"
    _seed_cursor(
        db,
        next_window_start=_FLOOR,
        harvest_until=_FROZEN_CEILING,
        now=_FLOOR,
    )

    first_deadline = _stop_after_first_slice(harvest, monkeypatch, _NOW)
    transport = httpx.MockTransport(_ok_item_handler("acme/first"))
    async with httpx.AsyncClient(transport=transport) as client:
        await harvest.harvest_github_slices(
            http_client=client,
            deadline=first_deadline,
            db_path=db,
        )

    queries: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        queries.append(_search_q(request))
        return _ok_item_handler("acme/second")(request)

    second_deadline = _stop_after_first_slice(harvest, monkeypatch, _NOW)
    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        await harvest.harvest_github_slices(
            http_client=client,
            deadline=second_deadline,
            db_path=db,
        )

    assert "pushed:2026-09-13..2026-09-20 stars:>10" in queries
    conn = connect_rw(db)
    try:
        cursor = get_cursor(conn, "github")
        assert cursor is not None
        assert cursor["next_window_start"] == _iso(_FLOOR)
        retreated = datetime.fromisoformat(
            cursor["harvest_until"].replace("Z", "+00:00")
        )
        assert retreated == _NOW - timedelta(days=14)
    finally:
        conn.close()


@pytest.mark.asyncio
async def test_restart_does_not_jump_high_edge_back_to_now(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, harvest = _load_harvest_stack()
    monkeypatch.setattr(harvest, "BISHOP_HARVEST_ENABLED", True)
    monkeypatch.setattr(harvest.TokenBucketRateLimiter, "acquire", _instant_acquire)
    retreated_until = _NOW - timedelta(days=7)
    later_now = _NOW + timedelta(days=3)
    queries: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        queries.append(_search_q(request))
        return _ok_item_handler("acme/restart")(request)

    db = tmp_path / "ledger.sqlite"
    _seed_cursor(
        db,
        next_window_start=_FLOOR,
        harvest_until=retreated_until,
        now=retreated_until,
        walk_direction="backward",
        high_water=_NOW,
    )
    deadline = _stop_after_first_slice(harvest, monkeypatch, later_now)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        await harvest.harvest_github_slices(
            http_client=client,
            deadline=deadline,
            db_path=db,
        )

    assert "pushed:2026-09-23..2026-09-30 stars:>10" not in queries
    assert "pushed:2026-09-13..2026-09-20 stars:>10" in queries
    conn = connect_rw(db)
    try:
        cursor = get_cursor(conn, "github")
        assert cursor is not None
        assert cursor["next_window_start"] == _iso(_FLOOR)
        assert cursor["walk_direction"] == "backward"
        high = datetime.fromisoformat(cursor["harvest_until"].replace("Z", "+00:00"))
        assert high == retreated_until - timedelta(days=7)
        assert high < later_now
    finally:
        conn.close()


@pytest.mark.asyncio
async def test_overflow_split_fetches_newer_half_first(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, harvest = _load_harvest_stack()
    monkeypatch.setattr(harvest, "BISHOP_HARVEST_ENABLED", True)
    monkeypatch.setattr(harvest.TokenBucketRateLimiter, "acquire", _instant_acquire)
    queries: list[str] = []
    full = "pushed:2026-01-01..2026-01-08 stars:>10"
    newer = "pushed:2026-01-04..2026-01-08 stars:>10"

    def handler(request: httpx.Request) -> httpx.Response:
        query = _search_q(request)
        queries.append(query)
        params = _params(request)
        per_page = int(params.get("per_page", ["100"])[0])
        if query == full and per_page == 1:
            return httpx.Response(
                200,
                json={"total_count": 2500, "incomplete_results": False, "items": []},
            )
        return httpx.Response(
            200,
            json={
                "total_count": 10,
                "incomplete_results": False,
                "items": [_repo_item("acme/newer-half")],
            },
        )

    db = tmp_path / "ledger.sqlite"
    _seed_cursor(
        db,
        next_window_start=_START,
        harvest_until=_SEVEN,
        now=_START,
        walk_direction="backward",
        high_water=_SEVEN,
    )
    deadline = _stop_after_first_slice(harvest, monkeypatch, _SEVEN)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        await harvest.harvest_github_slices(
            http_client=client,
            deadline=deadline,
            db_path=db,
        )

    assert queries[0] == full
    after_full = [query for query in queries if query != full]
    assert after_full[0] == newer
    conn = connect_rw(db)
    try:
        cursor = get_cursor(conn, "github")
        assert cursor is not None
        assert cursor["next_window_start"] == _iso(_START)
        retreated = datetime.fromisoformat(
            cursor["harvest_until"].replace("Z", "+00:00")
        )
        assert retreated == datetime(2026, 1, 4, 12, 0, 0, tzinfo=UTC)
        run = conn.execute("SELECT query FROM harvest_runs").fetchone()
        assert run["query"] == newer
    finally:
        conn.close()
