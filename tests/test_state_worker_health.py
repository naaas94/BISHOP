"""Unit tests for state-worker GET /health (M0 contract)."""

import asyncio
import sqlite3
import sys
from contextlib import asynccontextmanager
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
from app.models import DbHealthResponse, HealthResponse  # noqa: E402
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


def test_health_db_is_registered() -> None:
    routes = {route.path for route in app.routes if hasattr(route, "path")}
    assert "/health/db" in routes


def test_health_db_rejects_non_get(client: TestClient) -> None:
    assert client.post("/health/db").status_code == 405


def test_health_db_503_when_pool_not_initialized(client: TestClient) -> None:
    from app.db import close_pool

    asyncio.run(close_pool())
    response = client.get("/health/db")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "error"
    assert body["detail"]
    DbHealthResponse.model_validate(body)


def test_health_db_503_when_db_missing(tmp_path: Path) -> None:
    from app.db import close_pool, init_pool

    db_path = tmp_path / "missing.db"

    async def _setup() -> None:
        await init_pool(str(db_path), size=1)

    asyncio.run(_setup())
    try:
        response = TestClient(app).get("/health/db")
        assert response.status_code == 503
        body = response.json()
        assert body["status"] == "error"
        assert body["detail"]
        DbHealthResponse.model_validate(body)
    finally:
        asyncio.run(close_pool())


def test_health_db_503_when_alembic_version_empty(tmp_path: Path) -> None:
    """Falsifier: missing alembic_version row must 503, not 200 with detail=None."""
    from app.db import close_pool, init_pool, run_migrations

    db_path = tmp_path / "bishop.db"
    run_migrations(str(db_path))
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("DELETE FROM alembic_version")
        conn.commit()
    finally:
        conn.close()

    async def _setup() -> None:
        await init_pool(str(db_path), size=1)

    asyncio.run(_setup())
    try:
        response = TestClient(app).get("/health/db")
        assert response.status_code == 503
        body = response.json()
        assert body["status"] == "error"
        assert "empty" in body["detail"]
        DbHealthResponse.model_validate(body)
    finally:
        asyncio.run(close_pool())


def test_health_db_503_when_db_corrupt(monkeypatch: pytest.MonkeyPatch) -> None:
    @asynccontextmanager
    async def boom():
        raise sqlite3.DatabaseError("database disk image is malformed")
        yield  # pragma: no cover

    monkeypatch.setattr("app.main.get_db", boom)
    response = TestClient(app).get("/health/db")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "error"
    assert "malformed" in body["detail"]
    DbHealthResponse.model_validate(body)


def test_db_health_response_schema() -> None:
    ok = DbHealthResponse(status="ok", detail="m8_001")
    assert ok.model_dump() == {"status": "ok", "detail": "m8_001"}
    err = DbHealthResponse(status="error", detail="pool down")
    assert err.model_dump() == {"status": "error", "detail": "pool down"}


def test_db_health_response_rejects_invalid_status() -> None:
    with pytest.raises(ValidationError):
        DbHealthResponse(status="healthy")  # type: ignore[arg-type]
