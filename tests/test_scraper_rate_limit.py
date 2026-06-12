"""Unit tests for scraper rate limits and token bucket (M2 T2)."""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path
from types import ModuleType

import pytest

from bishop_shared.enums import SourceEnum

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRAPER_ROOT = _REPO_ROOT / "services" / "scraper"


def _load_rate_limit_module() -> ModuleType:
    """Load scraper rate_limit without shadowing state-worker ``app`` in sys.modules."""
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
        import app.rate_limit as rate_limit  # noqa: WPS433 — isolated import under scraper path
    finally:
        for name in list(sys.modules):
            if name == "app" or name.startswith("app."):
                del sys.modules[name]
        sys.modules.update(saved_app_modules)
        for path_str in path_state:
            sys.path.remove(path_str)

    return rate_limit


def test_rate_limit_dataclass_fields() -> None:
    rate_limit = _load_rate_limit_module()
    limit = rate_limit.RateLimit(
        calls=3,
        period_seconds=1,
        backoff="exponential",
        max_retries=4,
        jitter=True,
    )
    assert limit.calls == 3
    assert limit.period_seconds == 1
    assert limit.backoff == "exponential"
    assert limit.max_retries == 4
    assert limit.jitter is True


def test_arxiv_rate_limit_matches_spec() -> None:
    rate_limit = _load_rate_limit_module()
    arxiv = rate_limit.SOURCE_RATE_LIMITS[SourceEnum.ARXIV.value]
    assert arxiv == rate_limit.RateLimit(
        calls=3,
        period_seconds=1,
        backoff="exponential",
        max_retries=4,
        jitter=True,
    )


@pytest.mark.asyncio
async def test_token_bucket_throttles() -> None:
    rate_limit = _load_rate_limit_module()
    limiter = rate_limit.TokenBucketRateLimiter(
        rate_limit.RateLimit(calls=1, period_seconds=1, backoff="linear", max_retries=1),
    )
    await limiter.acquire()
    start = time.monotonic()
    await limiter.acquire()
    elapsed = time.monotonic() - start
    assert elapsed >= 0.9
