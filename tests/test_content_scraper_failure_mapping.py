"""Unit tests for adapter exception → failed POST mapping (M4 T2)."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path
from types import ModuleType

import httpx
import pytest

from bishop_shared.enums import SourceEnum

_REPO_ROOT = Path(__file__).resolve().parent.parent
_CONTENT_SCRAPER_ROOT = _REPO_ROOT / "services" / "content-scraper"
_SCRAPER_SRC = _REPO_ROOT / "services" / "scraper" / "app"


def _vendor_scraper_app(target_root: Path) -> None:
    """Mirror Docker COPY+sed vendoring into a temp directory."""
    scraper_dst = target_root / "scraper_app"
    if scraper_dst.exists():
        shutil.rmtree(scraper_dst)
    shutil.copytree(_SCRAPER_SRC, scraper_dst)
    for py_file in scraper_dst.rglob("*.py"):
        text = py_file.read_text(encoding="utf-8")
        text = text.replace("from app.", "from scraper_app.").replace(
            "import app.",
            "import scraper_app.",
        )
        py_file.write_text(text, encoding="utf-8")


def _load_failure_mapping_stack(tmp_path: Path) -> tuple[ModuleType, ModuleType]:
    saved_app_modules = {
        name: module
        for name, module in sys.modules.items()
        if name == "app" or name.startswith("app.") or name.startswith("scraper_app")
    }
    for name in saved_app_modules:
        del sys.modules[name]

    vendor_root = tmp_path / "vendor"
    vendor_root.mkdir()
    _vendor_scraper_app(vendor_root)

    repo_str = str(_REPO_ROOT)
    worker_str = str(_CONTENT_SCRAPER_ROOT)
    vendor_str = str(vendor_root)
    path_state: list[str] = []
    for path_str in (worker_str, vendor_str, repo_str):
        if path_str not in sys.path:
            sys.path.insert(0, path_str)
            path_state.append(path_str)

    try:
        import app.failure_mapping as mapping_mod  # noqa: WPS433
        import scraper_app.exceptions as exceptions  # noqa: WPS433
    finally:
        for name in list(sys.modules):
            if (
                name == "app"
                or name.startswith("app.")
                or name == "scraper_app"
                or name.startswith("scraper_app.")
            ):
                del sys.modules[name]
        sys.modules.update(saved_app_modules)
        for path_str in path_state:
            sys.path.remove(path_str)

    return mapping_mod, exceptions


def _http_status_error(status_code: int) -> httpx.HTTPStatusError:
    request = httpx.Request("GET", "http://example.com")
    response = httpx.Response(status_code, request=request)
    return httpx.HTTPStatusError("error", request=request, response=response)


def test_map_retry_exhausted_error_is_retriable(tmp_path: Path) -> None:
    mapping_mod, exceptions = _load_failure_mapping_stack(tmp_path)
    cause = _http_status_error(503)
    exc = exceptions.RetryExhaustedError(SourceEnum.ARXIV, 4, cause)
    body = mapping_mod.map_adapter_exception_to_failed("arxiv:2301.00001", exc)
    assert body.state_at_failure == "SCRAPE_QUEUED"
    assert body.error_class == "RetryExhaustedError"
    assert body.http_status == 503
    assert body.is_retriable is True


def test_map_retry_exhausted_network_cause_null_http_status(tmp_path: Path) -> None:
    mapping_mod, exceptions = _load_failure_mapping_stack(tmp_path)
    exc = exceptions.RetryExhaustedError(SourceEnum.ARXIV, 4, TimeoutError("timed out"))
    body = mapping_mod.map_adapter_exception_to_failed("arxiv:2301.00001", exc)
    assert body.http_status is None
    assert body.is_retriable is True


def test_map_permanent_failure_error_not_retriable(tmp_path: Path) -> None:
    mapping_mod, exceptions = _load_failure_mapping_stack(tmp_path)
    cause = _http_status_error(400)
    exc = exceptions.PermanentFailureError(SourceEnum.ARXIV, 400, cause)
    body = mapping_mod.map_adapter_exception_to_failed("arxiv:2301.00001", exc)
    assert body.error_class == "PermanentFailureError"
    assert body.http_status == 400
    assert body.is_retriable is False


def test_map_escalatable_error_not_retriable(tmp_path: Path) -> None:
    mapping_mod, exceptions = _load_failure_mapping_stack(tmp_path)
    cause = _http_status_error(404)
    exc = exceptions.EscalatableError(SourceEnum.ARXIV, 404, cause)
    body = mapping_mod.map_adapter_exception_to_failed("arxiv:2301.00001", exc)
    assert body.error_class == "EscalatableError"
    assert body.http_status == 404
    assert body.is_retriable is False


def test_map_generic_exception_not_retriable(tmp_path: Path) -> None:
    mapping_mod, _ = _load_failure_mapping_stack(tmp_path)
    body = mapping_mod.map_adapter_exception_to_failed("arxiv:2301.00001", RuntimeError("boom"))
    assert body.error_class == "RuntimeError"
    assert body.http_status is None
    assert body.is_retriable is False
