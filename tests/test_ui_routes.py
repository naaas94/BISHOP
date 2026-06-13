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
            if path == "/entries/arxiv:2401.00001":
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


def test_root_redirects_to_batches(ui_client: TestClient) -> None:
    response = ui_client.get("/", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/batches"


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


def test_ui_main_has_no_direct_store_imports() -> None:
    """Kill criterion: UI must not read LanceDB/BM25/SQLite directly."""
    source = (_UI_ROOT / "app" / "main.py").read_text(encoding="utf-8")
    forbidden = (
        "lancedb",
        "duckdb",
        "rank_bm25",
        "aiosqlite",
        "sqlite3",
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
