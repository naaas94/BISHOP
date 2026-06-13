"""Map adapter-layer exceptions to state-worker ``POST /entries/failed`` payloads."""

from __future__ import annotations

import httpx

from app.models import FailedPostRequest, SCRAPE_QUEUED_STATE
from scraper_app.exceptions import EscalatableError, PermanentFailureError, RetryExhaustedError


def _http_status_from_cause(cause: BaseException) -> int | None:
    if isinstance(cause, httpx.HTTPStatusError):
        return cause.response.status_code
    return None


def map_adapter_exception_to_failed(source_id: str, exc: BaseException) -> FailedPostRequest:
    """Map adapter exceptions per M4 §6.3 binding table."""
    if isinstance(exc, RetryExhaustedError):
        return FailedPostRequest(
            source_id=source_id,
            state_at_failure=SCRAPE_QUEUED_STATE,
            error_class="RetryExhaustedError",
            http_status=_http_status_from_cause(exc.cause),
            message=str(exc),
            is_retriable=True,
        )
    if isinstance(exc, PermanentFailureError):
        return FailedPostRequest(
            source_id=source_id,
            state_at_failure=SCRAPE_QUEUED_STATE,
            error_class="PermanentFailureError",
            http_status=exc.http_status,
            message=str(exc),
            is_retriable=False,
        )
    if isinstance(exc, EscalatableError):
        return FailedPostRequest(
            source_id=source_id,
            state_at_failure=SCRAPE_QUEUED_STATE,
            error_class="EscalatableError",
            http_status=exc.http_status,
            message=str(exc),
            is_retriable=False,
        )
    return FailedPostRequest(
        source_id=source_id,
        state_at_failure=SCRAPE_QUEUED_STATE,
        error_class=type(exc).__name__,
        http_status=None,
        message=str(exc),
        is_retriable=False,
    )
