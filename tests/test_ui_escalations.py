"""Unit tests for UI /escalations page (M8 T6)."""

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
def escalations_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    _load_ui_app()
    saved = _clear_app_modules()
    path_str = str(_UI_ROOT)
    inserted = None
    if path_str not in sys.path:
        sys.path.insert(0, path_str)
        inserted = path_str

    try:
        import app.main as ui_main_live  # noqa: WPS433

        def _fake_request(method, path, *, params=None, body=None):
            if method == "GET" and path == "/escalations":
                return 200, {
                    "entries": [
                        {
                            "source_id": "arxiv:flagged",
                            "title": "Flagged paper",
                            "source": "arxiv",
                            "url": "https://example.test",
                            "processing_state": "ESCALATION_FLAGGED",
                            "error_log": [{"error_class": "EscalatableError", "message": "timeout"}],
                        }
                    ]
                }
            if method == "POST" and path == "/entries/arxiv%3Aflagged/retry":
                return 200, {"source_id": "arxiv:flagged", "processing_state": "CONTENT_QUEUED"}
            if method == "POST" and path == "/entries/arxiv%3Aflagged/permanent-fail":
                return 200, {"source_id": "arxiv:flagged", "processing_state": "PERMANENTLY_FAILED"}
            return 404, None

        monkeypatch.setattr(ui_main_live, "_query_api_request", _fake_request)
        monkeypatch.setattr(
            ui_main_live,
            "_query_api_get",
            lambda path, *, params=None: _fake_request("GET", path, params=params),
        )
        return TestClient(ui_main_live.app)
    finally:
        _restore_app_modules(saved, inserted)


def test_escalations_page_renders_rows(escalations_client: TestClient) -> None:
    response = escalations_client.get("/escalations")
    assert response.status_code == 200
    body = response.text
    assert "Flagged paper" in body
    assert "Retry" in body
    assert "Permanent fail" in body


def test_escalations_retry_posts_via_query_api(escalations_client: TestClient) -> None:
    response = escalations_client.post("/escalations/arxiv:flagged/retry")
    assert response.status_code == 200
    assert "Retry queued" in response.text


def test_escalations_permanent_fail_posts_via_query_api(
    escalations_client: TestClient,
) -> None:
    response = escalations_client.post("/escalations/arxiv:flagged/permanent-fail")
    assert response.status_code == 200
    assert "permanently failed" in response.text


def test_ui_escalations_does_not_call_state_worker(monkeypatch: pytest.MonkeyPatch) -> None:
    saved = _clear_app_modules()
    path_str = str(_UI_ROOT)
    inserted = None
    if path_str not in sys.path:
        sys.path.insert(0, path_str)
        inserted = path_str
    calls: list[tuple[str, str]] = []
    try:
        import app.main as ui_main_live  # noqa: WPS433

        def _recording_request(method, path, *, params=None, body=None):
            calls.append((method, path))
            if path == "/escalations":
                return 200, {"entries": []}
            return 200, {}

        monkeypatch.setattr(ui_main_live, "_query_api_request", _recording_request)
        monkeypatch.setattr(
            ui_main_live,
            "_query_api_get",
            lambda path, *, params=None: _recording_request("GET", path, params=params),
        )
        client = TestClient(ui_main_live.app)
        client.get("/escalations")
        assert all("state-worker" not in path for _, path in calls)
    finally:
        _restore_app_modules(saved, inserted)
