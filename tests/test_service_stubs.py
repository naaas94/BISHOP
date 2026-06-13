"""Unit tests for M0 service stub entry points (T2)."""

from __future__ import annotations

from pathlib import Path

import pytest

from bishop_shared.constants import BISHOP_SERVICES

REPO_ROOT = Path(__file__).resolve().parent.parent

T2_WORKER_STUB_SERVICES = (
    "enrichment-batcher",
)

T2_M6_REAL_WORKER_SERVICES = (
    "vector-writer",
)

T2_M7_REAL_HTTP_SERVICES = (
    "query-api",
    "ui",
)

T2_M3_REAL_WORKER_SERVICES = (
    "pre-filter-worker",
    "batch-poller",
)

T2_M4_REAL_WORKER_SERVICES = (
    "content-scraper",
)

T2_SERVICES = (
    T2_WORKER_STUB_SERVICES
    + T2_M3_REAL_WORKER_SERVICES
    + T2_M4_REAL_WORKER_SERVICES
    + T2_M6_REAL_WORKER_SERVICES
    + T2_M7_REAL_HTTP_SERVICES
)


@pytest.mark.parametrize("service_name", T2_SERVICES)
def test_service_directory_matches_compose_key(service_name: str) -> None:
    """Falsifier: directory name drift breaks compose build context."""
    assert service_name in BISHOP_SERVICES
    service_dir = REPO_ROOT / "services" / service_name
    assert service_dir.is_dir()
    assert (service_dir / "Dockerfile").is_file()
    assert (service_dir / "stub_main.py").is_file()


@pytest.mark.parametrize("service_name", T2_WORKER_STUB_SERVICES)
def test_worker_stub_is_long_running(service_name: str) -> None:
    source = (REPO_ROOT / "services" / service_name / "stub_main.py").read_text(
        encoding="utf-8",
    )
    assert "while True" in source
    assert "time.sleep" in source
    assert f'SERVICE_NAME = "{service_name}"' in source


def test_dockerfiles_use_python_slim_base() -> None:
    for service_name in T2_SERVICES:
        dockerfile = (REPO_ROOT / "services" / service_name / "Dockerfile").read_text(
            encoding="utf-8",
        )
        assert "python:3.12-slim" in dockerfile


def test_scraper_uses_real_main_entrypoint() -> None:
    """Falsifier: scraper must run app.main, not the M0 stub loop."""
    dockerfile = (REPO_ROOT / "services" / "scraper" / "Dockerfile").read_text(
        encoding="utf-8",
    )
    assert 'CMD ["python", "-m", "app.main"]' in dockerfile
    assert "stub_main.py" not in dockerfile
    assert (REPO_ROOT / "services" / "scraper" / "app" / "main.py").is_file()


@pytest.mark.parametrize("service_name", T2_M3_REAL_WORKER_SERVICES)
def test_m3_worker_uses_real_main_entrypoint(service_name: str) -> None:
    """Falsifier: M3 workers must run app.main, not the M0 stub loop."""
    dockerfile = (REPO_ROOT / "services" / service_name / "Dockerfile").read_text(
        encoding="utf-8",
    )
    assert 'CMD ["python", "-m", "app.main"]' in dockerfile
    assert "stub_main.py" not in dockerfile
    assert (REPO_ROOT / "services" / service_name / "app" / "main.py").is_file()


@pytest.mark.parametrize("service_name", T2_M4_REAL_WORKER_SERVICES)
def test_m4_worker_uses_real_main_entrypoint(service_name: str) -> None:
    """Falsifier: M4 content-scraper must run app.main, not the M0 stub loop."""
    dockerfile = (REPO_ROOT / "services" / service_name / "Dockerfile").read_text(
        encoding="utf-8",
    )
    assert 'CMD ["python", "-m", "app.main"]' in dockerfile
    assert "stub_main.py" not in dockerfile
    assert (REPO_ROOT / "services" / service_name / "app" / "main.py").is_file()


@pytest.mark.parametrize("service_name", T2_M6_REAL_WORKER_SERVICES)
def test_m6_worker_uses_real_main_entrypoint(service_name: str) -> None:
    """Falsifier: M6 vector-writer must run app.main, not the M0 stub loop."""
    dockerfile = (REPO_ROOT / "services" / service_name / "Dockerfile").read_text(
        encoding="utf-8",
    )
    assert 'CMD ["python", "-m", "app.main"]' in dockerfile
    assert "stub_main.py" not in dockerfile
    assert (REPO_ROOT / "services" / service_name / "app" / "main.py").is_file()


@pytest.mark.parametrize("service_name", T2_M7_REAL_HTTP_SERVICES)
def test_m7_http_service_uses_real_main_entrypoint(service_name: str) -> None:
    """Falsifier: M7 query-api/ui must run app.main, not the M0 stub loop."""
    dockerfile = (REPO_ROOT / "services" / service_name / "Dockerfile").read_text(
        encoding="utf-8",
    )
    assert 'CMD ["python", "-m", "app.main"]' in dockerfile
    assert "stub_main.py" not in dockerfile
    assert (REPO_ROOT / "services" / service_name / "app" / "main.py").is_file()
