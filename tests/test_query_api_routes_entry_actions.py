"""Unit tests for query-api entry write proxies (M8 T6)."""

from __future__ import annotations

import json
import sys
from io import BytesIO
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

_REPO_ROOT = Path(__file__).resolve().parent.parent
_QUERY_API_ROOT = _REPO_ROOT / "services" / "query-api"


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


def _load_entries_router():
    saved = _clear_app_modules()
    path_str = str(_QUERY_API_ROOT)
    inserted = None
    if path_str not in sys.path:
        sys.path.insert(0, path_str)
        inserted = path_str
    try:
        from app.routers import entries as entries_router  # noqa: WPS433
        import app.config as config_mod  # noqa: WPS433
    finally:
        _restore_app_modules(saved, inserted)
    return entries_router, config_mod


def _mock_upstream(payload: dict, *, status: int = 200) -> MagicMock:
    body = json.dumps(payload).encode()
    mock_response = MagicMock()
    mock_response.read.return_value = body
    mock_response.status = status
    mock_response.__enter__ = MagicMock(return_value=mock_response)
    mock_response.__exit__ = MagicMock(return_value=False)
    return mock_response


@pytest.fixture
def actions_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    entries_router, config_mod = _load_entries_router()
    saved = _clear_app_modules()
    path_str = str(_QUERY_API_ROOT)
    inserted = None
    if path_str not in sys.path:
        sys.path.insert(0, path_str)
        inserted = path_str

    try:
        monkeypatch.setattr(
            config_mod,
            "STATE_WORKER_BASE_URL",
            "http://state-worker.test:8000",
        )
        app = FastAPI()
        app.include_router(entries_router.router)
        with patch("urllib.request.urlopen", return_value=_mock_upstream(
            {"source_id": "arxiv:1", "processing_state": "CONTENT_QUEUED"},
        )):
            with TestClient(app) as client:
                yield client
    finally:
        _restore_app_modules(saved, inserted)


def test_post_retry_proxies_state_worker(actions_client: TestClient) -> None:
    response = actions_client.post("/entries/arxiv:1/retry")
    assert response.status_code == 200
    assert response.json()["processing_state"] == "CONTENT_QUEUED"


def test_post_permanent_fail_proxies_state_worker(actions_client: TestClient) -> None:
    response = actions_client.post("/entries/arxiv:1/permanent-fail")
    assert response.status_code == 200


def test_patch_reading_status_proxies_state_worker(actions_client: TestClient) -> None:
    with patch(
        "urllib.request.urlopen",
        return_value=_mock_upstream(
            {"source_id": "arxiv:1", "reading_status": "read"},
        ),
    ):
        response = actions_client.patch(
            "/entries/arxiv:1/reading-status",
            json={"reading_status": "read"},
        )
    assert response.status_code == 200
    assert response.json()["reading_status"] == "read"


def test_patch_reading_status_invalid_enum_returns_422(
    actions_client: TestClient,
) -> None:
    response = actions_client.patch(
        "/entries/arxiv:1/reading-status",
        json={"reading_status": "not_a_real_status"},
    )
    assert response.status_code == 422


def test_slash_source_id_retry_and_reading_status_match(
    actions_client: TestClient,
) -> None:
    retry = actions_client.post("/entries/github:owner/repo/retry")
    assert retry.status_code == 200

    with patch(
        "urllib.request.urlopen",
        return_value=_mock_upstream(
            {"source_id": "github:owner/repo", "reading_status": "read"},
        ),
    ):
        response = actions_client.patch(
            "/entries/github:owner/repo/reading-status",
            json={"reading_status": "read"},
        )
    assert response.status_code == 200
    assert response.json()["source_id"] == "github:owner/repo"
    assert response.json()["reading_status"] == "read"


def test_entry_action_upstream_error_envelope() -> None:
    entries_router, _config_mod = _load_entries_router()
    saved = _clear_app_modules()
    path_str = str(_QUERY_API_ROOT)
    inserted = None
    if path_str not in sys.path:
        sys.path.insert(0, path_str)
        inserted = path_str

    try:
        import urllib.error

        app = FastAPI()
        app.include_router(entries_router.router)

        def _raise_http_error(*_args, **_kwargs):
            raise urllib.error.HTTPError(
                url="http://state-worker.test:8000/entries/retry",
                code=409,
                msg="conflict",
                hdrs=None,
                fp=BytesIO(json.dumps({"error": "invalid_transition"}).encode()),
            )

        with patch("urllib.request.urlopen", side_effect=_raise_http_error):
            with TestClient(app) as client:
                response = client.post("/entries/arxiv:1/retry")
    finally:
        _restore_app_modules(saved, inserted)

    assert response.status_code == 409
    assert response.json()["error"] == "invalid_transition"


def test_retry_proxy_passes_source_id_in_body() -> None:
    entries_router, _config_mod = _load_entries_router()
    saved = _clear_app_modules()
    path_str = str(_QUERY_API_ROOT)
    inserted = None
    if path_str not in sys.path:
        sys.path.insert(0, path_str)
        inserted = path_str

    captured: dict[str, object] = {}

    def _capture_request(request, timeout=30):
        captured["method"] = request.get_method()
        captured["url"] = request.full_url
        captured["body"] = request.data
        return _mock_upstream({"source_id": "arxiv:9", "processing_state": "CONTENT_QUEUED"})

    try:
        app = FastAPI()
        app.include_router(entries_router.router)
        with patch("urllib.request.urlopen", side_effect=_capture_request):
            with TestClient(app) as client:
                client.post("/entries/arxiv:9/retry")
    finally:
        _restore_app_modules(saved, inserted)

    assert captured["method"] == "POST"
    assert captured["url"].endswith("/entries/retry")
    assert json.loads(captured["body"]) == {"source_id": "arxiv:9"}


def test_reading_status_proxy_quotes_slash_source_id() -> None:
    entries_router, _config_mod = _load_entries_router()
    saved = _clear_app_modules()
    path_str = str(_QUERY_API_ROOT)
    inserted = None
    if path_str not in sys.path:
        sys.path.insert(0, path_str)
        inserted = path_str

    captured: dict[str, object] = {}

    def _capture_request(request, timeout=30):
        captured["url"] = request.full_url
        return _mock_upstream({"source_id": "github:owner/repo", "reading_status": "read"})

    try:
        app = FastAPI()
        app.include_router(entries_router.router)
        with patch("urllib.request.urlopen", side_effect=_capture_request):
            with TestClient(app) as client:
                response = client.patch(
                    "/entries/github:owner/repo/reading-status",
                    json={"reading_status": "read"},
                )
    finally:
        _restore_app_modules(saved, inserted)

    assert response.status_code == 200
    assert "/entries/github%3Aowner%2Frepo/reading-status" in str(captured["url"])
