"""Unit tests for scraper failure envelope and exception types (M2 T3)."""

from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from bishop_shared.enums import SourceEnum

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRAPER_ROOT = _REPO_ROOT / "services" / "scraper"


def _load_failure_envelope_stack() -> tuple[ModuleType, ModuleType, ModuleType]:
    """Load scraper failure envelope without shadowing state-worker ``app`` in sys.modules."""
    saved_app_modules = {
        name: module
        for name, module in sys.modules.items()
        if name == "app" or name.startswith("app.")
    }
    for name in saved_app_modules:
        del sys.modules[name]

    repo_str = str(_REPO_ROOT)
    scraper_str = str(_SCRAPER_ROOT)
    path_state: list[str] = []
    for path_str in (scraper_str, repo_str):
        if path_str not in sys.path:
            sys.path.insert(0, path_str)
            path_state.append(path_str)

    try:
        import app.exceptions as exceptions  # noqa: WPS433
        import app.failure_envelope as failure_envelope  # noqa: WPS433
        import app.rate_limit as rate_limit  # noqa: WPS433
    finally:
        for name in list(sys.modules):
            if name == "app" or name.startswith("app."):
                del sys.modules[name]
        sys.modules.update(saved_app_modules)
        for path_str in path_state:
            sys.path.remove(path_str)

    return exceptions, failure_envelope, rate_limit


def _http_status_error(status_code: int) -> httpx.HTTPStatusError:
    request = httpx.Request("GET", "http://example.com")
    response = httpx.Response(status_code, request=request)
    return httpx.HTTPStatusError("error", request=request, response=response)


def test_retriable_and_escalatable_http_sets() -> None:
    _, failure_envelope, _ = _load_failure_envelope_stack()
    assert failure_envelope.RETRIABLE_HTTP == frozenset({429, 500, 502, 503, 504})
    assert failure_envelope.ESCALATABLE_HTTP == frozenset({401, 403, 404, 422})


def test_compute_backoff_exponential_without_jitter() -> None:
    _, failure_envelope, rate_limit = _load_failure_envelope_stack()
    config = rate_limit.RateLimit(
        calls=1,
        period_seconds=1,
        backoff="exponential",
        max_retries=1,
        jitter=False,
    )
    with patch.object(failure_envelope.random, "uniform", return_value=0.0):
        assert failure_envelope.compute_backoff(config, 0) == 1.0
        assert failure_envelope.compute_backoff(config, 2) == 4.0


@pytest.mark.asyncio
async def test_429_retried() -> None:
    exceptions, failure_envelope, _ = _load_failure_envelope_stack()
    call_count = 0

    async def flaky() -> str:
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise _http_status_error(429)
        return "ok"

    with patch.object(failure_envelope.asyncio, "sleep", new_callable=AsyncMock):
        result = await failure_envelope.failure_envelope(
            flaky,
            source=SourceEnum.ARXIV,
        )

    assert result == "ok"
    assert call_count == 3


@pytest.mark.asyncio
async def test_403_escalatable() -> None:
    exceptions, failure_envelope, _ = _load_failure_envelope_stack()
    call_count = 0

    async def forbidden() -> None:
        nonlocal call_count
        call_count += 1
        raise _http_status_error(403)

    with pytest.raises(exceptions.EscalatableError) as exc_info:
        await failure_envelope.failure_envelope(
            forbidden,
            source=SourceEnum.ARXIV,
        )

    assert exc_info.value.http_status == 403
    assert call_count == 1


@pytest.mark.asyncio
async def test_400_raises_permanent_failure_immediately() -> None:
    exceptions, failure_envelope, _ = _load_failure_envelope_stack()
    call_count = 0

    async def bad_request() -> None:
        nonlocal call_count
        call_count += 1
        raise _http_status_error(400)

    with pytest.raises(exceptions.PermanentFailureError) as exc_info:
        await failure_envelope.failure_envelope(
            bad_request,
            source=SourceEnum.ARXIV,
        )

    assert exc_info.value.http_status == 400
    assert call_count == 1


@pytest.mark.asyncio
async def test_429_retry_exhausted_raises() -> None:
    exceptions, failure_envelope, rate_limit = _load_failure_envelope_stack()
    max_retries = rate_limit.SOURCE_RATE_LIMITS[SourceEnum.ARXIV.value].max_retries
    call_count = 0

    async def always_rate_limited() -> None:
        nonlocal call_count
        call_count += 1
        raise _http_status_error(429)

    with patch.object(failure_envelope.asyncio, "sleep", new_callable=AsyncMock):
        with pytest.raises(exceptions.RetryExhaustedError):
            await failure_envelope.failure_envelope(
                always_rate_limited,
                source=SourceEnum.ARXIV,
            )

    assert call_count == max_retries + 1


@pytest.mark.asyncio
async def test_network_error_retried() -> None:
    exceptions, failure_envelope, _ = _load_failure_envelope_stack()
    call_count = 0

    async def flaky_network() -> str:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise httpx.NetworkError("connection reset")
        return "recovered"

    with patch.object(failure_envelope.asyncio, "sleep", new_callable=AsyncMock):
        result = await failure_envelope.failure_envelope(
            flaky_network,
            source=SourceEnum.ARXIV,
        )

    assert result == "recovered"
    assert call_count == 2


def test_log_permanent_failure_emits_structured_log(
    caplog: pytest.LogCaptureFixture,
) -> None:
    exceptions, failure_envelope, _ = _load_failure_envelope_stack()
    cause = _http_status_error(410)
    error = exceptions.PermanentFailureError(SourceEnum.ARXIV, 410, cause)

    with caplog.at_level("ERROR"):
        failure_envelope.log_permanent_failure(SourceEnum.ARXIV, error)

    assert any("Permanent adapter failure" in record.message for record in caplog.records)
    assert caplog.records[-1].source == "arxiv"  # type: ignore[attr-defined]
    assert caplog.records[-1].http_status == 410  # type: ignore[attr-defined]
    assert caplog.records[-1].event == "permanent_failure"  # type: ignore[attr-defined]
