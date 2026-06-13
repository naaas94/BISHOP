"""Unit tests for GET /escalations proxy (M7 T5)."""

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


def _load_escalations_router():
    saved = _clear_app_modules()
    path_str = str(_QUERY_API_ROOT)
    inserted = None
    if path_str not in sys.path:
        sys.path.insert(0, path_str)
        inserted = path_str
    try:
        from app.routers import escalations as escalations_router  # noqa: WPS433
        import app.config as config_mod  # noqa: WPS433
    finally:
        _restore_app_modules(saved, inserted)
    return escalations_router, config_mod


@pytest.fixture
def escalations_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    escalations_router, config_mod = _load_escalations_router()
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
        app.include_router(escalations_router.router)

        payload = {"entries": [{"source_id": "arxiv:9", "title": "Flagged"}]}
        body = json.dumps(payload).encode()
        mock_response = MagicMock()
        mock_response.read.return_value = body
        mock_response.status = 200
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response):
            with TestClient(app) as client:
                yield client
    finally:
        _restore_app_modules(saved, inserted)


def test_escalations_proxies_state_worker(escalations_client: TestClient) -> None:
    response = escalations_client.get("/escalations")
    assert response.status_code == 200
    assert response.json()["entries"][0]["source_id"] == "arxiv:9"


def test_escalations_upstream_error() -> None:
    escalations_router, config_mod = _load_escalations_router()
    saved = _clear_app_modules()
    path_str = str(_QUERY_API_ROOT)
    inserted = None
    if path_str not in sys.path:
        sys.path.insert(0, path_str)
        inserted = path_str

    try:
        import urllib.error

        app = FastAPI()
        app.include_router(escalations_router.router)

        def _raise_http_error(*_args, **_kwargs):
            raise urllib.error.HTTPError(
                url="http://state-worker.test:8000/escalations",
                code=502,
                msg="bad gateway",
                hdrs=None,
                fp=BytesIO(b""),
            )

        with patch("urllib.request.urlopen", side_effect=_raise_http_error):
            with TestClient(app) as client:
                response = client.get("/escalations")
    finally:
        _restore_app_modules(saved, inserted)

    assert response.status_code == 502
    assert response.json() == {"error": "upstream_error", "status": 502}
