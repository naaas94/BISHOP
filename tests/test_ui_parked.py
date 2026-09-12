"""Unit tests for UI /parked inbox."""

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
def parked_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    saved = _clear_app_modules()
    path_str = str(_UI_ROOT)
    inserted = None
    if path_str not in sys.path:
        sys.path.insert(0, path_str)
        inserted = path_str

    try:
        import app.main as ui_main_live  # noqa: WPS433

        def _fake_request(method, path, *, params=None, body=None):
            if method == "GET" and path == "/parked":
                return 200, {
                    "entries": [
                        {
                            "source_id": "arxiv:parked",
                            "title": "Parked paper",
                            "abstract": "Skim me later",
                            "source": "arxiv",
                            "url": "https://example.test",
                            "pre_filter_rationale": "Interesting, not core.",
                            "pre_filter_tier": "peripheral",
                            "processing_state": "RELEVANCE_PARKED",
                        }
                    ]
                }
            if method == "POST" and path == "/parked/promote":
                assert body == {"source_id": "arxiv:parked"}
                return 200, {
                    "source_id": "arxiv:parked",
                    "processing_state": "RELEVANCE_PASSED",
                }
            return 500, None

        monkeypatch.setattr(ui_main_live, "_query_api_request", _fake_request)
        monkeypatch.setattr(ui_main_live, "_query_api_get", lambda path, params=None: _fake_request("GET", path))
        with TestClient(ui_main_live.app) as client:
            yield client
    finally:
        _restore_app_modules(saved, inserted)


def test_parked_page_renders_rows(parked_client: TestClient) -> None:
    response = parked_client.get("/parked")
    assert response.status_code == 200
    assert "Parked paper" in response.text
    assert "Skim me later" in response.text
    assert "Promote" in response.text


def test_parked_promote_posts_via_query_api(parked_client: TestClient) -> None:
    response = parked_client.post("/parked/arxiv:parked/promote")
    assert response.status_code == 200
    assert "Promoted arxiv:parked" in response.text
