"""Adapter-layer failure types for scraper discovery (§6.3, Appendix C)."""

from __future__ import annotations

from bishop_shared.enums import SourceEnum


class PermanentFailureError(Exception):
    """Fatal HTTP or unrecoverable adapter failure (e.g. 400, 410)."""

    def __init__(
        self,
        source: SourceEnum,
        http_status: int | None,
        cause: BaseException,
    ) -> None:
        self.source = source
        self.http_status = http_status
        self.cause = cause
        status_part = f" HTTP {http_status}" if http_status is not None else ""
        super().__init__(f"Permanent failure for {source.value}{status_part}: {cause}")


class EscalatableError(Exception):
    """Non-retriable recoverable failure requiring escalation (401, 403, 404, 422)."""

    def __init__(
        self,
        source: SourceEnum,
        http_status: int,
        cause: BaseException,
    ) -> None:
        self.source = source
        self.http_status = http_status
        self.cause = cause
        super().__init__(
            f"Escalatable failure for {source.value} HTTP {http_status}: {cause}",
        )


class RetryExhaustedError(Exception):
    """Retriable failures exceeded ``max_retries`` for the source."""

    def __init__(
        self,
        source: SourceEnum,
        attempt: int,
        cause: BaseException,
    ) -> None:
        self.source = source
        self.attempt = attempt
        self.cause = cause
        super().__init__(
            f"Retry exhausted for {source.value} after {attempt} attempts: {cause}",
        )
