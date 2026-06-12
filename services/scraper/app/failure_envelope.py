"""Async retry wrapper with HTTP/network failure classification (§6.3, §10.4, §15.2)."""

from __future__ import annotations

import asyncio
import logging
import random
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

import httpx

from bishop_shared.enums import SourceEnum

from app.exceptions import (
    EscalatableError,
    PermanentFailureError,
    RetryExhaustedError,
)
from app.rate_limit import RateLimit, SOURCE_RATE_LIMITS

logger = logging.getLogger(__name__)

RETRIABLE_HTTP: frozenset[int] = frozenset({429, 500, 502, 503, 504})
ESCALATABLE_HTTP: frozenset[int] = frozenset({401, 403, 404, 422})

RETRIABLE_EXC: tuple[type[BaseException], ...] = (
    TimeoutError,
    ConnectionError,
    httpx.TimeoutException,
    httpx.NetworkError,
    httpx.RemoteProtocolError,
)

BASE_DELAY_SECONDS = 1.0
JITTER_FRACTION = 0.2

_T = TypeVar("_T")


def compute_backoff(config: RateLimit, attempt: int) -> float:
    """Compute sleep delay for retry attempt per §15.2."""
    if config.backoff == "exponential":
        delay = BASE_DELAY_SECONDS * (2**attempt)
    else:
        delay = BASE_DELAY_SECONDS * attempt
    if config.jitter:
        jitter_range = JITTER_FRACTION * delay
        delay += random.uniform(-jitter_range, jitter_range)
    return max(0.0, delay)


def log_permanent_failure(source: SourceEnum, error: PermanentFailureError) -> None:
    """Emit structured ERROR log for fatal adapter failures."""
    logger.error(
        "Permanent adapter failure",
        extra={
            "source": source.value,
            "http_status": error.http_status,
            "event": "permanent_failure",
        },
    )


async def failure_envelope(
    fn: Callable[..., Awaitable[_T]],
    *args: Any,
    source: SourceEnum,
    **kwargs: Any,
) -> _T:
    """Wrap an adapter call with per-source retry and failure classification."""
    config = SOURCE_RATE_LIMITS[source.value]
    attempt = 0
    while attempt <= config.max_retries:
        try:
            return await fn(*args, **kwargs)
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            if status in RETRIABLE_HTTP:
                if attempt == config.max_retries:
                    raise RetryExhaustedError(source, attempt, exc) from exc
                delay = compute_backoff(config, attempt)
                await asyncio.sleep(delay)
                attempt += 1
            elif status in ESCALATABLE_HTTP:
                raise EscalatableError(source, status, exc) from exc
            else:
                raise PermanentFailureError(source, status, exc) from exc
        except RETRIABLE_EXC as exc:
            if attempt == config.max_retries:
                raise RetryExhaustedError(source, attempt, exc) from exc
            delay = compute_backoff(config, attempt)
            await asyncio.sleep(delay)
            attempt += 1
