"""Unit tests for M0 service stub entry points (T2)."""

from __future__ import annotations

import importlib.util
import re
import socket
import threading
from http.client import HTTPConnection
from pathlib import Path

import pytest

from bishop_shared.constants import (
    BISHOP_SERVICES,
    QUERY_API_HOST_PORT,
    STATE_WORKER_INTERNAL_PORT,
    UI_HOST_PORT,
)

REPO_ROOT = Path(__file__).resolve().parent.parent

T2_WORKER_SERVICES = (
    "scraper",
    "pre-filter-worker",
    "content-scraper",
    "enrichment-batcher",
    "batch-poller",
    "vector-writer",
)

T2_HTTP_SERVICES = ("query-api", "ui")

T2_SERVICES = T2_WORKER_SERVICES + T2_HTTP_SERVICES

PORT_LITERAL_PATTERN = re.compile(
    r"\b(?:8000|8080|8081|80)\b",
)


def _load_stub_module(service_name: str):
    stub_path = REPO_ROOT / "services" / service_name / "stub_main.py"
    spec = importlib.util.spec_from_file_location(f"{service_name}_stub", stub_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _fetch_root(port: int) -> tuple[int, str]:
    conn = HTTPConnection("127.0.0.1", port, timeout=2)
    try:
        conn.request("GET", "/")
        response = conn.getresponse()
        body = response.read().decode("utf-8")
        return response.status, body
    finally:
        conn.close()


@pytest.mark.parametrize("service_name", T2_SERVICES)
def test_service_directory_matches_compose_key(service_name: str) -> None:
    """Falsifier: directory name drift breaks compose build context."""
    assert service_name in BISHOP_SERVICES
    service_dir = REPO_ROOT / "services" / service_name
    assert service_dir.is_dir()
    assert (service_dir / "Dockerfile").is_file()
    assert (service_dir / "stub_main.py").is_file()


@pytest.mark.parametrize("service_name", T2_WORKER_SERVICES)
def test_worker_stub_is_long_running(service_name: str) -> None:
    source = (REPO_ROOT / "services" / service_name / "stub_main.py").read_text(
        encoding="utf-8",
    )
    assert "while True" in source
    assert "time.sleep" in source
    assert f'SERVICE_NAME = "{service_name}"' in source


def test_query_api_binds_port_from_constants() -> None:
    module = _load_stub_module("query-api")
    source = (REPO_ROOT / "services" / "query-api" / "stub_main.py").read_text(
        encoding="utf-8",
    )
    assert "STATE_WORKER_INTERNAL_PORT" in source
    assert not PORT_LITERAL_PATTERN.search(source)

    port = _free_port()
    server = module.HTTPServer(("127.0.0.1", port), module.RootHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        status, body = _fetch_root(port)
        assert status == 200
        assert body == "ok"
    finally:
        server.shutdown()


def test_query_api_listen_port_matches_internal_constant() -> None:
    module = _load_stub_module("query-api")
    assert module.STATE_WORKER_INTERNAL_PORT == STATE_WORKER_INTERNAL_PORT


def test_ui_binds_port_from_constants() -> None:
    module = _load_stub_module("ui")
    source = (REPO_ROOT / "services" / "ui" / "stub_main.py").read_text(
        encoding="utf-8",
    )
    assert "QUERY_API_HOST_PORT" in source
    assert "STATE_WORKER_INTERNAL_PORT" in source
    assert not PORT_LITERAL_PATTERN.search(source)
    assert module.UI_CONTAINER_PORT == QUERY_API_HOST_PORT - STATE_WORKER_INTERNAL_PORT

    port = _free_port()
    server = module.HTTPServer(("127.0.0.1", port), module.RootHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        status, body = _fetch_root(port)
        assert status == 200
        assert body == "ok"
    finally:
        server.shutdown()


def test_ui_container_port_is_wire_eighty() -> None:
    """Falsifier: ui container must listen on 80 per plan §2 Wire."""
    module = _load_stub_module("ui")
    assert module.UI_CONTAINER_PORT == 80
    assert UI_HOST_PORT == 8081


def test_dockerfiles_use_python_slim_base() -> None:
    for service_name in T2_SERVICES:
        dockerfile = (REPO_ROOT / "services" / service_name / "Dockerfile").read_text(
            encoding="utf-8",
        )
        assert "python:3.12-slim" in dockerfile
