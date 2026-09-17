"""GitHub closed-range harvest into the sidecar ledger. Not DISCOVERED."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx

from bishop_shared.enums import SourceEnum
from bishop_shared.harvest_ledger import (
    HarvestRun,
    connect_rw,
    get_cursor,
    harvest_db_path,
    record_run,
    set_cursor,
    upsert_candidates,
)

from app.adapters.github import (
    GITHUB_SEARCH_REPOS_URL,
    GitHubAdapter,
    build_harvest_query,
    parse_harvest_candidate,
)
from app.config import (
    BISHOP_HARVEST_ENABLED,
    BISHOP_HARVEST_QUERY_ID,
    BISHOP_HARVEST_WINDOW_DAYS,
)
from app.rate_limit import RateLimit, TokenBucketRateLimiter

logger = logging.getLogger(__name__)

_SEARCH_SOURCE = SourceEnum.GITHUB.value
_SLICE_DAYS = 7
_MAX_SEARCH_PAGES = 10
_SEARCH_PER_PAGE = 100
_OVERFLOW_TOTAL_COUNT = 1000
_SEARCH_RATE_LIMIT = RateLimit(
    calls=1,
    period_seconds=2,
    backoff="linear",
    max_retries=5,
    jitter=True,
)


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _iso(value: datetime) -> str:
    return _as_utc(value).isoformat().replace("+00:00", "Z")


def _split_mid(start: datetime, end: datetime) -> datetime:
    mid = start + (end - start) / 2
    if mid <= start:
        mid = start + timedelta(days=1)
    if mid >= end:
        mid = start + timedelta(days=1)
    return mid


def _header_int(headers: httpx.Headers, name: str) -> int | None:
    raw = headers.get(name)
    if raw is None or raw == "":
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _header_reset_iso(headers: httpx.Headers) -> str | None:
    raw = headers.get("X-RateLimit-Reset")
    if raw is None or raw == "":
        return None
    try:
        epoch = int(raw)
    except ValueError:
        return raw
    return _iso(datetime.fromtimestamp(epoch, tz=UTC))


async def harvest_github_slices(
    *,
    http_client: httpx.AsyncClient,
    deadline: datetime,
    db_path: Path | str | None = None,
) -> None:
    """Walk closed ``pushed:START..END`` windows into the harvest sidecar.

    Incremental GitHub ``fetch_manifest`` still POSTs DISCOVERED elsewhere.
    """
    if not BISHOP_HARVEST_ENABLED:
        return

    path = Path(db_path) if db_path is not None else harvest_db_path()
    if db_path is None and not path.parent.exists():
        logger.info(
            "harvest sidecar directory missing",
            extra={"event": "harvest_skip", "path": str(path.parent)},
        )
        return

    conn = connect_rw(path)
    try:
        await _harvest_into(conn, http_client=http_client, deadline=_as_utc(deadline))
    finally:
        conn.close()


async def _harvest_into(
    conn,
    *,
    http_client: httpx.AsyncClient,
    deadline: datetime,
) -> None:
    adapter = GitHubAdapter(http_client=http_client)
    limiter = TokenBucketRateLimiter(_SEARCH_RATE_LIMIT)
    clock = _utc_now()
    row = get_cursor(conn, _SEARCH_SOURCE)
    if row is None or not row["next_window_start"] or not row["harvest_until"]:
        next_window_start = clock - timedelta(days=BISHOP_HARVEST_WINDOW_DAYS)
        harvest_until = clock
        set_cursor(
            conn,
            _SEARCH_SOURCE,
            next_window_start=_iso(next_window_start),
            harvest_until=_iso(harvest_until),
            now=clock,
        )
    else:
        next_window_start = _as_utc(_parse_iso(row["next_window_start"]))
        harvest_until = _as_utc(_parse_iso(row["harvest_until"]))

    if next_window_start >= harvest_until:
        bumped = _utc_now()
        if bumped > harvest_until:
            harvest_until = bumped
            set_cursor(
                conn,
                _SEARCH_SOURCE,
                next_window_start=_iso(next_window_start),
                harvest_until=_iso(harvest_until),
                now=bumped,
            )

    pending_end: datetime | None = None
    while _utc_now() < deadline and next_window_start < harvest_until:
        start = next_window_start
        end = (
            pending_end
            if pending_end is not None
            else min(start + timedelta(days=_SLICE_DAYS), harvest_until)
        )
        pending_end = None
        if end <= start:
            break

        slice_started = _utc_now()
        query = build_harvest_query(start, end)
        probe = await _search(
            http_client,
            adapter=adapter,
            limiter=limiter,
            query=query,
            per_page=1,
            page=1,
        )
        payload = probe.json()
        if not isinstance(payload, dict):
            payload = {}
        total_count_raw = payload.get("total_count")
        total_count = int(total_count_raw) if isinstance(total_count_raw, int) else 0
        width_days = (end - start).days
        if total_count > _OVERFLOW_TOTAL_COUNT and width_days > 1:
            pending_end = _split_mid(start, end)
            if pending_end <= start or pending_end >= end:
                pending_end = None
            else:
                continue

        incomplete = bool(payload.get("incomplete_results")) or (
            total_count > _OVERFLOW_TOTAL_COUNT
        )
        pages_fetched = 0
        items_upserted = 0
        last_response = probe
        if total_count > 0:
            seen: set[str] = set()
            batch = []
            for page in range(1, _MAX_SEARCH_PAGES + 1):
                if _utc_now() >= deadline:
                    break
                page_response = await _search(
                    http_client,
                    adapter=adapter,
                    limiter=limiter,
                    query=query,
                    per_page=_SEARCH_PER_PAGE,
                    page=page,
                )
                last_response = page_response
                pages_fetched += 1
                page_payload = page_response.json()
                if not isinstance(page_payload, dict):
                    break
                if page_payload.get("incomplete_results"):
                    incomplete = True
                raw_items = page_payload.get("items")
                if not isinstance(raw_items, list) or not raw_items:
                    break
                for item in raw_items:
                    if not isinstance(item, dict):
                        continue
                    full_name = item.get("full_name")
                    if not isinstance(full_name, str) or "/" not in full_name:
                        continue
                    candidate = parse_harvest_candidate(
                        item,
                        adapter=adapter,
                        harvest_query_id=BISHOP_HARVEST_QUERY_ID,
                    )
                    if candidate.source_id in seen:
                        continue
                    seen.add(candidate.source_id)
                    batch.append(candidate)
                if len(raw_items) < _SEARCH_PER_PAGE:
                    break
            if batch:
                items_upserted = upsert_candidates(conn, batch, now=_utc_now())

        finished = _utc_now()
        record_run(
            conn,
            HarvestRun(
                source=_SEARCH_SOURCE,
                query=query,
                window_start=_iso(start),
                window_end=_iso(end),
                total_count=total_count,
                incomplete_results=incomplete,
                pages_fetched=pages_fetched,
                items_upserted=items_upserted,
                http_status=last_response.status_code,
                ratelimit_remaining=_header_int(
                    last_response.headers, "X-RateLimit-Remaining"
                ),
                ratelimit_reset=_header_reset_iso(last_response.headers),
                started_at=_iso(slice_started),
                finished_at=_iso(finished),
            ),
        )
        logger.info(
            "harvest slice complete",
            extra={
                "event": "harvest_slice",
                "query": query,
                "total_count": total_count,
                "incomplete": incomplete,
                "upserted": items_upserted,
            },
        )
        next_window_start = end
        set_cursor(
            conn,
            _SEARCH_SOURCE,
            next_window_start=_iso(next_window_start),
            harvest_until=_iso(harvest_until),
            now=finished,
        )

    if next_window_start >= harvest_until:
        bumped = _utc_now()
        if bumped > harvest_until:
            harvest_until = bumped
            set_cursor(
                conn,
                _SEARCH_SOURCE,
                next_window_start=_iso(next_window_start),
                harvest_until=_iso(harvest_until),
                now=bumped,
            )


async def _search(
    http_client: httpx.AsyncClient,
    *,
    adapter: GitHubAdapter,
    limiter: TokenBucketRateLimiter,
    query: str,
    per_page: int,
    page: int,
) -> httpx.Response:
    await limiter.acquire()
    response = await http_client.get(
        GITHUB_SEARCH_REPOS_URL,
        params={
            "q": query,
            "sort": "updated",
            "order": "desc",
            "per_page": per_page,
            "page": page,
        },
        headers=adapter._auth_headers(),
    )
    response.raise_for_status()
    return response
