"""Per-source rate limit configuration and token-bucket enforcement (§15.1, §15.3)."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Literal

from bishop_shared.enums import SourceEnum


@dataclass(frozen=True)
class RateLimit:
    calls: int
    period_seconds: int
    backoff: Literal["exponential", "linear"]
    max_retries: int
    jitter: bool = True


SOURCE_RATE_LIMITS: dict[str, RateLimit] = {
    SourceEnum.ARXIV.value: RateLimit(
        calls=3,
        period_seconds=1,
        backoff="exponential",
        max_retries=4,
        jitter=True,
    ),
}


class TokenBucketRateLimiter:
    """Async token bucket enforcing ``calls`` per ``period_seconds``."""

    def __init__(self, rate_limit: RateLimit) -> None:
        self._rate_limit = rate_limit
        self._max_tokens = float(rate_limit.calls)
        self._tokens = self._max_tokens
        self._refill_rate = rate_limit.calls / rate_limit.period_seconds
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Wait until a call token is available, then consume one."""
        async with self._lock:
            while True:
                now = time.monotonic()
                elapsed = now - self._last_refill
                if elapsed > 0:
                    self._tokens = min(
                        self._max_tokens,
                        self._tokens + elapsed * self._refill_rate,
                    )
                    self._last_refill = now
                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return
                deficit = 1.0 - self._tokens
                await asyncio.sleep(deficit / self._refill_rate)
