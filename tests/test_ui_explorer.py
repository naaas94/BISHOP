"""Unit tests for UI /explorer DB filter page (M8 T6)."""

from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType

import pytest
from fastapi.testclient import TestClient

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


@pytest.fixture
def explorer_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    saved = _clear_app_modules()
    path_str = str(_UI_ROOT)
    inserted = None
    if path_str not in sys.path:
        sys.path.insert(0, path_str)
        inserted = path_str

    try:
        import app.main as ui_main_live  # noqa: WPS433

        def _fake_get(path: str, *, params: dict[str, str] | None = None):
            if path == "/search":
                assert params is not None
                assert params["q"] == "retrieval"
                assert params["reading_status"] == "unread"
                assert params["source"] == "arxiv"
                return 200, {
                    "query": "retrieval",
                    "problem_shaped": False,
                    "channels_active": ["bm25_main", "dense"],
                    "hits": [
                        {
                            "source_id": "arxiv:1",
                            "rrf_score": 0.03,
                            "title": "Retrieval Paper",
                            "summary": "Sparse graphs.",
                            "relevance_score": 0.9,
                            "entry_type": "paper",
                            "tags": ["RAG"],
                        }
                    ],
                    "total": 1,
                }
            return 404, None

        monkeypatch.setattr(ui_main_live, "_query_api_get", _fake_get)
        return TestClient(ui_main_live.app)
    finally:
        _restore_app_modules(saved, inserted)


def test_explorer_page_renders_filter_form(explorer_client: TestClient) -> None:
    response = explorer_client.get("/explorer")
    assert response.status_code == 200
    body = response.text
    assert "DB Explorer" in body
    assert 'name="reading_status"' in body
    assert 'name="source"' in body


def test_explorer_search_forwards_metadata_params(explorer_client: TestClient) -> None:
    response = explorer_client.get(
        "/explorer",
        params={
            "q": "retrieval",
            "source": "arxiv",
            "reading_status": "unread",
        },
    )
    assert response.status_code == 200
    assert "Retrieval Paper" in response.text
    assert "/entries/arxiv:1" in response.text
