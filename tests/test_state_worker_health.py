"""Unit tests for state-worker GET /health (M0 contract)."""

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

_STATE_WORKER_ROOT = Path(__file__).resolve().parent.parent / "services" / "state-worker"
_REPO_ROOT = Path(__file__).resolve().parent.parent

for path in (_STATE_WORKER_ROOT, _REPO_ROOT):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

from app.main import app  # noqa: E402
from app.models import HealthResponse  # noqa: E402
from bishop_shared.constants import STATE_WORKER_INTERNAL_PORT  # noqa: E402


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_health_returns_200_ok(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_response_schema() -> None:
    model = HealthResponse(status="ok")
    assert model.model_dump() == {"status": "ok"}


def test_health_response_rejects_invalid_status() -> None:
    """Falsifier: response body deviates from {"status":"ok"} at the schema layer."""
    with pytest.raises(ValidationError):
        HealthResponse(status="healthy")  # type: ignore[arg-type]


def test_run_binds_internal_port(monkeypatch: pytest.MonkeyPatch) -> None:
    """Falsifier: uvicorn listens on a port other than STATE_WORKER_INTERNAL_PORT."""
    captured: dict[str, object] = {}

    def fake_run(_app, host: str, port: int, **_kwargs) -> None:
        captured["host"] = host
        captured["port"] = port

    monkeypatch.setattr("uvicorn.run", fake_run)
    from app.main import run

    run()
    assert captured["host"] == "0.0.0.0"
    assert captured["port"] == STATE_WORKER_INTERNAL_PORT


def test_health_rejects_non_get(client: TestClient) -> None:
    """Falsifier: /health accepts mutating methods."""
    assert client.post("/health").status_code == 405
