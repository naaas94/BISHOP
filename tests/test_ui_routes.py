"""Unit tests for HTMX UI routes (M7 T7)."""

from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType
import pytest
from fastapi.testclient import TestClient

from bishop_shared.constants import QUERY_API_HOST_PORT

_REPO_ROOT = Path(__file__).resolve().parent.parent
_UI_ROOT = _REPO_ROOT / "services" / "ui"


def _clear_app_modules() -> dict[str, ModuleType]:
    saved = {
        name: module
        for name, module in sys.modules.items()
        if name == "app" or name.startswith("app.")
    }
    for name in saved:
        del sys.modules[name]
    return saved


def _restore_app_modules(saved: dict[str, ModuleType], inserted_path: str | None) -> None:
    for name in list(sys.modules):
        if name == "app" or name.startswith("app."):
            del sys.modules[name]
    sys.modules.update(saved)
    if inserted_path is not None:
        sys.path.remove(inserted_path)


def _fake_stats_overview_payload() -> dict:
    en_dash = "\u2013"
    funnel_labels = [
        "Discovered",
        "Relevance queued",
        "Relevance passed",
        "Relevance rejected",
        "Relevance parked",
        "Scrape",
        "Enrichment stage 1",
        "Enrichment stage 2",
        "Vector write queued",
        "Indexed",
        "Failed",
        "Escalated",
        "Permanently failed",
    ]
    funnel = [{"label": label, "count": 0} for label in funnel_labels]
    funnel[0] = {"label": "Discovered", "count": 8}
    funnel[3] = {"label": "Relevance rejected", "count": 40}
    funnel[9] = {"label": "Indexed", "count": 12}
    funnel[11] = {"label": "Escalated", "count": 2}
    hist = [
        {"label": f"{i / 10:.1f}{en_dash}{(i + 1) / 10:.1f}", "count": 0}
        for i in range(10)
    ]
    return {
        "generated_at": "2026-06-02T12:00:00Z",
        "manifest_total": 100,
        "entries_total": 50,
        "indexed_total": 12,
        "pre_filter_decided": 20,
        "pre_filter_passed": 15,
        "pre_filter_parked": 4,
        "pre_filter_proceeded": 11,
        "funnel": funnel,
        "queue_depth": [{"label": "SCRAPE_QUEUED", "count": 3}],
        "relevance_histogram": hist,
        "by_domain": [{"label": "professional", "count": 12}],
        "by_source": [{"label": "arxiv", "count": 8}],
        "by_entry_type": [{"label": "paper", "count": 10}],
        "top_tags": [{"label": "RAG", "count": 9}],
        "reading_status": [{"label": "unread", "count": 7}],
        "ingest_by_day": [
            {
                "date": "2026-06-01",
                "count": 2,
                "by_source": [{"label": "arxiv", "count": 2}],
            },
            {
                "date": "2026-06-02",
                "count": 5,
                "by_source": [
                    {"label": "arxiv", "count": 3},
                    {"label": "github", "count": 2},
                ],
            },
        ],
        "batches_total": 4,
        "batches_by_status": [{"label": "complete", "count": 4}],
        "batches_by_type": [{"label": "pre_filter", "count": 3}],
        "recent_errors": [{"label": "http_error", "count": 1}],
        "harvest_pool_size": 0,
        "harvest_unreleased": 0,
        "harvest_released_today": 0,
        "harvest_n_cap": 0,
        "harvest_budget_usd": 0.0,
        "harvest_projected_usd_today": 0.0,
        "harvest_sidecar_present": False,
        "harvest_unreleased_liability_usd": 0.0,
        "harvest_tap_open": False,
        "scrape_max_lag_hours": 20.0,
        "scrape_lag_source": "github",
        "scrape_caught_up": False,
        "scrape_exceptions": [
            {
                "source": "github",
                "lag_hours": 20.0,
                "discovered_today": 2,
                "in_queue": 2,
                "stale": True,
            }
        ],
        "today_discovered": 12,
    }


def _fake_harvest_stats_payload() -> dict:
    return {
        "generated_at": "2026-09-27T12:00:00Z",
        "sidecar_present": True,
        "pool_size": 126818,
        "unreleased": 103417,
        "unreleased_liability_usd": 79.01,
        "pool_modeled_usd": 96.89,
        "blended_github_usd": 0.000764,
        "days_to_drain": 22,
        "n_cap": 4712,
        "budget_usd": 4.52,
        "paper_reserve_usd": 0.92,
        "github_budget_usd": 3.60,
        "released_today": 14136,
        "github_in_queue": 150,
        "slots_remaining": 0,
        "tap_open": False,
        "tap_killed": False,
        "released_overshoot": True,
        "released_fill_pct": 100.0,
        "modeled_usd_today": 10.80,
        "walk_direction": "backward",
        "floor_at": "2024-12-15T20:18:40Z",
        "harvest_until": "2026-09-25T16:07:56Z",
        "high_water": "2026-09-27T10:07:56Z",
        "cursor_updated_at": "2026-09-27T10:07:56Z",
        "unwalked_days": 649.8,
        "walked_recent_days": 1.7,
        "window_span_days": 651.5,
        "walked_pct": 0.3,
        "forecast_ready": False,
        "forecast_complete_windows": 1,
        "forecast_incomplete_windows": 0,
        "forecast_median_rate": 0.0,
        "forecast_upper_rate": 0.0,
        "forecast_median_usd": 0.0,
        "forecast_upper_usd": 0.0,
    }


def _fake_scrape_stats_payload() -> dict:
    return {
        "generated_at": "2026-09-27T12:00:00Z",
        "schedule_interval_sec": 21600,
        "overlay_window_days": 60,
        "backfill_enabled": True,
        "max_lag_hours": 20.0,
        "lag_source": "github",
        "caught_up": False,
        "discovered_today": 12,
        "in_queue": 4,
        "github_released_today": 14136,
        "sources": [
            {
                "source": "arxiv",
                "last_successful_run_at": "2026-09-27T11:00:00Z",
                "updated_at": "2026-09-27T11:00:00Z",
                "lag_hours": 1.0,
                "lag_fill_pct": 8.3,
                "pin_window_days": 60,
                "discovered_today": 10,
                "in_queue": 2,
                "dead": False,
                "stale": False,
                "note": None,
            },
            {
                "source": "github",
                "last_successful_run_at": "2026-09-26T16:00:00Z",
                "updated_at": "2026-09-26T16:00:00Z",
                "lag_hours": 20.0,
                "lag_fill_pct": 100.0,
                "pin_window_days": 30,
                "discovered_today": 2,
                "in_queue": 2,
                "dead": False,
                "stale": True,
                "note": "Incremental still writes DISCOVERED. Harvest mill is a sibling.",
            },
            {
                "source": "paperswithcode",
                "last_successful_run_at": None,
                "updated_at": None,
                "lag_hours": None,
                "lag_fill_pct": 0.0,
                "pin_window_days": 60,
                "discovered_today": 0,
                "in_queue": 0,
                "dead": True,
                "stale": False,
                "note": "API dead.",
            },
        ],
    }


def _fake_today_stats_payload() -> dict:
    return {
        "generated_at": "2026-09-27T12:00:00Z",
        "utc_day": "2026-09-27",
        "utc_midnight": "2026-09-27T00:00:00+00:00",
        "discovered_today": 12,
        "discovered_by_source": [{"label": "github", "count": 10}, {"label": "arxiv", "count": 2}],
        "in_queue_today": 4,
        "indexed_cohort_today": 1,
        "entries_ingested_today": 3,
        "batches_completed_today": 2,
        "batches_by_status": [{"label": "complete", "count": 2}],
        "batches_by_type": [{"label": "pre_filter", "count": 2}],
        "errors_today": [],
        "funnel": [{"label": "Discovered", "count": 12}],
        "queue_depth": [{"label": "DISCOVERED", "count": 4}],
        "harvest_sidecar_present": True,
        "harvest_released_today": 14136,
        "harvest_modeled_usd_today": 10.80,
        "harvest_n_cap": 4712,
        "harvest_tap_open": False,
        "harvest_tap_killed": False,
        "harvest_released_overshoot": True,
        "harvest_released_fill_pct": 100.0,
        "scrape_caught_up": False,
        "scrape_max_lag_hours": 20.0,
        "scrape_lag_source": "github",
        "scrape_in_queue": 4,
        "scrape_exceptions": [
            {
                "source": "github",
                "lag_hours": 20.0,
                "discovered_today": 2,
                "in_queue": 2,
                "stale": True,
            }
        ],
        "overlay_window_days": 60,
        "schedule_interval_sec": 21600,
    }


def _load_ui_app():
    saved = _clear_app_modules()
    path_str = str(_UI_ROOT)
    inserted = None
    if path_str not in sys.path:
        sys.path.insert(0, path_str)
        inserted = path_str
    try:
        from app import main as ui_main  # noqa: WPS433
    finally:
        _restore_app_modules(saved, inserted)
    return ui_main


@pytest.fixture
def ui_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    ui_main = _load_ui_app()
    saved = _clear_app_modules()
    path_str = str(_UI_ROOT)
    inserted = None
    if path_str not in sys.path:
        sys.path.insert(0, path_str)
        inserted = path_str

    try:
        import app.main as ui_main_live  # noqa: WPS433

        def _fake_query_api_get(path: str, *, params: dict[str, str] | None = None):
            if path == "/batches":
                assert params == {"status": "complete"}
                return 200, {
                    "batches": [
                        {
                            "batch_id": "b-old",
                            "batch_type": "pre_filter",
                            "domain": "professional",
                            "profile_version": "1.0.0",
                            "completed_at": "2026-06-01T10:00:00",
                            "entry_count": 5,
                            "passed_count": 4,
                        },
                        {
                            "batch_id": "b-new",
                            "batch_type": "enrichment_stage2",
                            "domain": "professional",
                            "profile_version": "1.0.0",
                            "completed_at": "2026-06-02T12:00:00",
                            "entry_count": 3,
                            "passed_count": 3,
                        },
                    ]
                }
            if path == "/batches/b-new":
                return 200, {
                    "batch": {
                        "batch_id": "b-new",
                        "batch_type": "enrichment_stage2",
                        "domain": "professional",
                        "profile_version": "1.0.0",
                        "status": "complete",
                        "completed_at": "2026-06-02T12:00:00",
                        "entry_count": 3,
                        "passed_count": 3,
                        "failed_count": 0,
                    },
                    "entries": [
                        {
                            "source_id": "arxiv:2401.00001",
                            "title": "Hybrid Retrieval",
                            "relevance_score": 0.91,
                            "entry_type": "paper",
                            "tags": ["RAG"],
                        }
                    ],
                }
            if path == "/entries/arxiv%3A2401.00001":
                return 200, {
                    "source_id": "arxiv:2401.00001",
                    "title": "Hybrid Retrieval",
                    "url": "https://arxiv.org/abs/2401.00001",
                    "source": "arxiv",
                    "domain": "professional",
                    "content_raw": "Full paper text.",
                    "ingested_at": "2026-06-02T11:00:00",
                    "reading_status": "unread",
                    "processing_state": "INDEXED",
                    "profile_version": "1.0.0",
                    "pre_filter_batch_id": "b-new",
                    "pre_filter_rationale": "relevant",
                    "flagged_for_review": False,
                    "id": "1",
                }
            if path == "/entries/github%3Aowner%2Frepo":
                return 200, {
                    "source_id": "github:owner/repo",
                    "title": "owner/repo",
                    "url": "https://github.com/owner/repo",
                    "source": "github",
                    "domain": "professional",
                    "content_raw": "README body.",
                    "ingested_at": "2026-06-02T11:00:00",
                    "reading_status": "unread",
                    "processing_state": "INDEXED",
                    "profile_version": "1.0.0",
                    "pre_filter_batch_id": "b-new",
                    "pre_filter_rationale": "relevant",
                    "flagged_for_review": False,
                    "id": "2",
                }
            if path == "/stats/overview":
                return 200, _fake_stats_overview_payload()
            if path == "/stats/harvest":
                return 200, _fake_harvest_stats_payload()
            if path == "/stats/scrape":
                return 200, _fake_scrape_stats_payload()
            if path == "/stats/today":
                return 200, _fake_today_stats_payload()
            if path == "/recent":
                return 200, {
                    "total": 1,
                    "entries": [
                        {
                            "source_id": "arxiv:2401.00001",
                            "source": "arxiv",
                            "title": "Hybrid Retrieval",
                            "ingested_at": "2026-06-02T11:00:00",
                            "domain": "professional",
                            "entry_type": "paper",
                            "relevance_score": 0.91,
                            "summary": "Sparse graphs.",
                        }
                    ],
                }
            if path == "/parked":
                return 200, {
                    "entries": [
                        {
                            "source_id": "github:acme/parked",
                            "title": "parked repo",
                            "abstract": "maybe",
                            "source": "github",
                            "url": "https://github.com/acme/parked",
                            "pre_filter_rationale": "shape",
                        },
                        {
                            "source_id": "arxiv:2401.park",
                            "title": "parked paper",
                            "abstract": "maybe",
                            "source": "arxiv",
                            "url": "https://arxiv.org/abs/2401.park",
                            "pre_filter_rationale": "shape",
                        },
                    ]
                }
            if path == "/search":
                assert params and params.get("q") == "hybrid retrieval"
                return 200, {
                    "query": "hybrid retrieval",
                    "problem_shaped": True,
                    "channels_active": ["bm25_main", "dense", "bm25_hooks"],
                    "hits": [
                        {
                            "source_id": "arxiv:2401.00001",
                            "rrf_score": 0.032,
                            "title": "Hybrid Retrieval",
                            "summary": "Sparse graphs.",
                            "relevance_score": 0.91,
                            "entry_type": "paper",
                            "tags": ["RAG"],
                        }
                    ],
                    "total": 1,
                }
            return 404, None

        monkeypatch.setattr(ui_main_live, "_query_api_get", _fake_query_api_get)
        return TestClient(ui_main_live.app)
    finally:
        _restore_app_modules(saved, inserted)


def test_root_redirects_to_dashboard(ui_client: TestClient) -> None:
    response = ui_client.get("/", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/dashboard"


def test_dashboard_renders_stats(ui_client: TestClient) -> None:
    response = ui_client.get("/dashboard")
    assert response.status_code == 200
    body = response.text
    assert "Dashboard" in body
    assert "Pipeline funnel" in body
    assert "Indexed" in body
    assert "12" in body
    assert "SCRAPE_QUEUED" in body
    assert "75%" in body
    assert "RAG" in body
    assert "Total batches" in body
    assert "Unreleased liability" not in body
    assert "Harvest sidecar not mounted." not in body
    assert 'href="/harvest"' in body
    assert "No scrape cursor yet" not in body
    assert "20.0h behind" not in body
    assert "20.0h" not in body
    assert "queue 2" not in body
    assert "github" in body
    assert "4 parked" in body
    assert "11 proceeded" in body
    assert "In queue" in body
    assert 'href="/landed?days=1"' not in body
    assert "Indexed today" not in body
    assert 'href="/scrape"' in body
    assert 'href="/today"' in body
    assert "12 discovered" not in body
    assert "ingest-fill" in body
    assert 'style="width: 40.0%"' in body
    assert "Relevance rejected" in body
    assert "333" not in body
    assert "Harvest pool" not in body
    assert "Projected $ today" not in body
    assert 'id="dashboard-stats"' in body


def test_dashboard_htmx_returns_partial(ui_client: TestClient) -> None:
    response = ui_client.get("/dashboard", headers={"HX-Request": "true"})
    assert response.status_code == 200
    body = response.text
    assert 'id="dashboard-stats"' in body
    assert "<html" not in body.lower()


def test_harvest_page_renders_liability(ui_client: TestClient) -> None:
    response = ui_client.get("/harvest")
    assert response.status_code == 200
    body = response.text
    assert "Unreleased modeled liability" in body
    assert "$79" in body
    assert "103417 unreleased" in body
    assert "22 days to drain" in body
    assert "103417 unreleased" in body
    assert "Does not price" in body
    assert "Cursor 2026-09-27T10:07:56Z" in body
    assert "Tap closed until UTC midnight" in body
    assert "Modeled cost of today's releases" in body
    assert "harvest formula, not the Anthropic console" in body
    assert 'id="harvest-stats"' in body
    assert 'href="/harvest"' in body
    assert "bar-row is-bad" in body
    assert 'href="/harvest" aria-current="page"' in body


def test_harvest_htmx_returns_partial(ui_client: TestClient) -> None:
    response = ui_client.get("/harvest", headers={"HX-Request": "true"})
    assert response.status_code == 200
    body = response.text
    assert 'id="harvest-stats"' in body
    assert "<html" not in body.lower()
    assert "Unreleased modeled liability" in body


def test_harvest_upstream_error_shows_message(monkeypatch: pytest.MonkeyPatch) -> None:
    saved = _clear_app_modules()
    path_str = str(_UI_ROOT)
    inserted = None
    if path_str not in sys.path:
        sys.path.insert(0, path_str)
        inserted = path_str
    try:
        import app.main as ui_main_live  # noqa: WPS433

        monkeypatch.setattr(
            ui_main_live,
            "_query_api_get",
            lambda path, *, params=None: (502, None),
        )
        client = TestClient(ui_main_live.app)
        response = client.get("/harvest")
        assert response.status_code == 200
        assert "query-api returned status 502" in response.text
    finally:
        _restore_app_modules(saved, inserted)


def test_scrape_page_renders_lag(ui_client: TestClient) -> None:
    response = ui_client.get("/scrape")
    assert response.status_code == 200
    body = response.text
    assert "Behind (github)" in body
    assert "20.0h" in body
    assert "12 discovered" in body
    assert 'href="/today"' in body
    assert "API dead." in body
    assert "Incremental still writes DISCOVERED" in body
    assert "tap released 14136" in body
    assert 'id="scrape-stats"' in body
    assert 'href="/scrape"' in body
    assert "harvest-hero is-bad" in body
    assert "is-warn" in body
    assert "is-dead" in body
    assert 'href="/scrape" aria-current="page"' in body


def test_today_page_renders_utc_day(ui_client: TestClient) -> None:
    response = ui_client.get("/today")
    assert response.status_code == 200
    body = response.text
    assert "Discovered (UTC 2026-09-27)" in body
    assert "14136 harvest released" in body
    assert "entries created" in body
    assert "already INDEXED" in body
    assert "no indexed_at stamp" in body
    assert "Scrape 20.0h behind (github)" in body
    assert "overlay 60d" in body
    assert "tick 21600s" in body
    assert "queue 4" in body
    assert 'href="/scrape"' in body
    assert "github stale" in body
    assert "14136 / 4712 released" in body
    assert "tap" in body
    assert "closed" in body
    assert 'href="/harvest"' in body
    assert "Modeled cost of today's releases" not in body
    assert "bar-row is-bad" not in body
    assert 'id="today-stats"' in body
    assert 'href="/today" aria-current="page"' in body
    assert "Walk and pool stay on Harvest" not in body


def test_today_htmx_returns_partial(ui_client: TestClient) -> None:
    response = ui_client.get("/today", headers={"HX-Request": "true"})
    assert response.status_code == 200
    body = response.text
    assert 'id="today-stats"' in body
    assert "<html" not in body.lower()
    assert "Discovered (UTC 2026-09-27)" in body


def test_today_upstream_error_shows_message(monkeypatch: pytest.MonkeyPatch) -> None:
    saved = _clear_app_modules()
    path_str = str(_UI_ROOT)
    inserted = None
    if path_str not in sys.path:
        sys.path.insert(0, path_str)
        inserted = path_str
    try:
        import app.main as ui_main_live  # noqa: WPS433

        monkeypatch.setattr(
            ui_main_live,
            "_query_api_get",
            lambda path, *, params=None: (502, None),
        )
        client = TestClient(ui_main_live.app)
        response = client.get("/today")
        assert response.status_code == 200
        assert "query-api returned status 502" in response.text
    finally:
        _restore_app_modules(saved, inserted)


def test_scrape_htmx_returns_partial(ui_client: TestClient) -> None:
    response = ui_client.get("/scrape", headers={"HX-Request": "true"})
    assert response.status_code == 200
    body = response.text
    assert 'id="scrape-stats"' in body
    assert "<html" not in body.lower()
    assert "Behind (github)" in body


def test_scrape_upstream_error_shows_message(monkeypatch: pytest.MonkeyPatch) -> None:
    saved = _clear_app_modules()
    path_str = str(_UI_ROOT)
    inserted = None
    if path_str not in sys.path:
        sys.path.insert(0, path_str)
        inserted = path_str
    try:
        import app.main as ui_main_live  # noqa: WPS433

        monkeypatch.setattr(
            ui_main_live,
            "_query_api_get",
            lambda path, *, params=None: (502, None),
        )
        client = TestClient(ui_main_live.app)
        response = client.get("/scrape")
        assert response.status_code == 200
        assert "query-api returned status 502" in response.text
    finally:
        _restore_app_modules(saved, inserted)


def test_dashboard_upstream_timeout_shows_message(monkeypatch: pytest.MonkeyPatch) -> None:
    saved = _clear_app_modules()
    path_str = str(_UI_ROOT)
    inserted = None
    if path_str not in sys.path:
        sys.path.insert(0, path_str)
        inserted = path_str
    try:
        import app.main as ui_main_live  # noqa: WPS433

        def _timeout(*_args: object, **_kwargs: object) -> None:
            raise TimeoutError("timed out")

        monkeypatch.setattr(ui_main_live.urllib.request, "urlopen", _timeout)
        client = TestClient(ui_main_live.app)
        response = client.get("/dashboard")
        assert response.status_code == 200
        assert "query-api returned status 504" in response.text
        assert "Internal Server Error" not in response.text
    finally:
        _restore_app_modules(saved, inserted)


def test_dashboard_upstream_error_shows_message(monkeypatch: pytest.MonkeyPatch) -> None:
    saved = _clear_app_modules()
    path_str = str(_UI_ROOT)
    inserted = None
    if path_str not in sys.path:
        sys.path.insert(0, path_str)
        inserted = path_str
    try:
        import app.main as ui_main_live  # noqa: WPS433

        monkeypatch.setattr(
            ui_main_live,
            "_query_api_get",
            lambda path, *, params=None: (502, None),
        )
        client = TestClient(ui_main_live.app)
        response = client.get("/dashboard")
        assert response.status_code == 200
        assert "query-api returned status 502" in response.text
    finally:
        _restore_app_modules(saved, inserted)


def test_batch_list_filters_complete_and_sorts_desc(ui_client: TestClient) -> None:
    response = ui_client.get("/batches")
    assert response.status_code == 200
    body = response.text
    assert "Completed batches" in body
    assert body.index("b-new") < body.index("b-old")


def test_batch_detail_renders_entries(ui_client: TestClient) -> None:
    response = ui_client.get("/batches/b-new")
    assert response.status_code == 200
    assert "Hybrid Retrieval" in response.text
    assert "/entries/arxiv:2401.00001" in response.text


def test_entry_detail_renders_content_raw(ui_client: TestClient) -> None:
    response = ui_client.get("/entries/arxiv:2401.00001")
    assert response.status_code == 200
    assert "Raw content" in response.text
    assert "Full paper text." in response.text


def test_entry_detail_slash_source_id_renders(ui_client: TestClient) -> None:
    response = ui_client.get("/entries/github:owner/repo")
    assert response.status_code == 200
    assert "README body." in response.text
    assert "Entry not found" not in response.text


def test_search_page_and_htmx_partial(ui_client: TestClient) -> None:
    page = ui_client.get("/search")
    assert page.status_code == 200
    assert 'id="search-q"' in page.text

    partial = ui_client.get(
        "/search",
        params={"q": "hybrid retrieval"},
        headers={"HX-Request": "true"},
    )
    assert partial.status_code == 200
    assert "Hybrid Retrieval" in partial.text
    assert "bm25_hooks" in partial.text


def test_batch_list_upstream_error_shows_message(monkeypatch: pytest.MonkeyPatch) -> None:
    saved = _clear_app_modules()
    path_str = str(_UI_ROOT)
    inserted = None
    if path_str not in sys.path:
        sys.path.insert(0, path_str)
        inserted = path_str
    try:
        import app.main as ui_main_live  # noqa: WPS433

        monkeypatch.setattr(
            ui_main_live,
            "_query_api_get",
            lambda path, *, params=None: (502, None),
        )
        client = TestClient(ui_main_live.app)
        response = client.get("/batches")
        assert response.status_code == 200
        assert "query-api returned status 502" in response.text
    finally:
        _restore_app_modules(saved, inserted)


def test_landed_page_renders_recent(ui_client: TestClient) -> None:
    response = ui_client.get("/landed")
    assert response.status_code == 200
    body = response.text
    assert "Hybrid Retrieval" in body
    assert "arxiv:2401.00001" in body or 'href="/entries/arxiv:2401.00001"' in body
    assert 'href="/landed" aria-current="page"' in body
    response_today = ui_client.get("/landed", params={"days": "1"})
    assert response_today.status_code == 200
    assert "Hybrid Retrieval" in response_today.text


def test_landed_upstream_error_shows_message(monkeypatch: pytest.MonkeyPatch) -> None:
    saved = _clear_app_modules()
    path_str = str(_UI_ROOT)
    inserted = None
    if path_str not in sys.path:
        sys.path.insert(0, path_str)
        inserted = path_str
    try:
        import app.main as ui_main_live  # noqa: WPS433

        monkeypatch.setattr(
            ui_main_live,
            "_query_api_get",
            lambda path, *, params=None: (502, None),
        )
        client = TestClient(ui_main_live.app)
        response = client.get("/landed")
        assert response.status_code == 200
        assert "query-api returned status 502" in response.text
    finally:
        _restore_app_modules(saved, inserted)


def test_parked_page_counts_by_source(ui_client: TestClient) -> None:
    response = ui_client.get("/parked")
    assert response.status_code == 200
    body = response.text
    assert "2 parked" in body
    assert "github 1" in body
    assert "arxiv 1" in body


def test_ui_main_has_no_direct_store_imports() -> None:
    """Kill criterion: UI must not read LanceDB/BM25/SQLite directly."""
    source = (_UI_ROOT / "app" / "main.py").read_text(encoding="utf-8")
    forbidden = (
        "lancedb",
        "duckdb",
        "rank_bm25",
        "aiosqlite",
        "sqlite3",
        "harvest_ledger",
        "STATE_WORKER_URL",
        "state-worker",
    )
    for token in forbidden:
        assert token not in source


def test_ui_search_uses_query_api_not_state_worker(monkeypatch: pytest.MonkeyPatch) -> None:
    saved = _clear_app_modules()
    path_str = str(_UI_ROOT)
    inserted = None
    if path_str not in sys.path:
        sys.path.insert(0, path_str)
        inserted = path_str
    calls: list[str] = []
    try:
        import app.main as ui_main_live  # noqa: WPS433

        def _recording_get(path: str, *, params: dict[str, str] | None = None):
            calls.append(path)
            return 200, {
                "query": params.get("q", "") if params else "",
                "problem_shaped": False,
                "channels_active": ["bm25_main", "dense"],
                "hits": [],
                "total": 0,
            }

        monkeypatch.setattr(ui_main_live, "_query_api_get", _recording_get)
        client = TestClient(ui_main_live.app)
        client.get("/search", params={"q": "test"})
        assert calls == ["/search"]
        assert not any("state-worker" in call for call in calls)
    finally:
        _restore_app_modules(saved, inserted)


def test_dockerfile_uses_real_main_entrypoint() -> None:
    """Kill criterion: Dockerfile must not CMD stub_main.py."""
    dockerfile = (_UI_ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert 'CMD ["python", "-m", "app.main"]' in dockerfile
    assert "stub_main.py" not in dockerfile


def test_ui_container_port_matches_wire_eighty() -> None:
    ui_main = _load_ui_app()
    assert ui_main.UI_CONTAINER_PORT == 80
    assert QUERY_API_HOST_PORT == 8080
