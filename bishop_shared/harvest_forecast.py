"""Walk-density forecast for the unwalked GitHub harvest window.

Complete Search windows in the walked recent span set a per-day rate.
Incomplete (Search-capped) windows are counted, not used as rates.
Fewer than three complete windows is waiting, not a point estimate.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from datetime import UTC, datetime

from bishop_shared.harvest_ledger import HarvestCursor, HarvestRun

MIN_COMPLETE_WINDOWS = 3
_SECONDS_PER_DAY = 86400.0


@dataclass(frozen=True)
class WalkForecast:
    walk_direction: str | None
    floor_at: str | None
    harvest_until: str | None
    high_water: str | None
    cursor_updated_at: str | None
    unwalked_days: float
    walked_recent_days: float
    window_span_days: float
    walked_pct: float
    forecast_ready: bool
    complete_windows: int
    incomplete_windows: int
    median_rate: float
    upper_rate: float
    median_usd: float
    upper_usd: float


def parse_harvest_iso(value: str | None) -> datetime | None:
    if value is None or value == "":
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def span_days(start: datetime, end: datetime) -> float:
    return max(0.0, (end - start).total_seconds() / _SECONDS_PER_DAY)


def empty_walk_forecast() -> WalkForecast:
    return WalkForecast(
        walk_direction=None,
        floor_at=None,
        harvest_until=None,
        high_water=None,
        cursor_updated_at=None,
        unwalked_days=0.0,
        walked_recent_days=0.0,
        window_span_days=0.0,
        walked_pct=0.0,
        forecast_ready=False,
        complete_windows=0,
        incomplete_windows=0,
        median_rate=0.0,
        upper_rate=0.0,
        median_usd=0.0,
        upper_usd=0.0,
    )


def _window_in_walked_span(
    start: datetime,
    end: datetime,
    *,
    span_start: datetime,
    span_end: datetime,
) -> bool:
    return start >= span_start and end <= span_end


def compute_walk_forecast(
    cursor: HarvestCursor | None,
    runs: list[HarvestRun],
    *,
    blended_usd: float,
) -> WalkForecast:
    """Median/upper modeled $ of the unwalked gap from complete walked windows."""
    if cursor is None:
        return empty_walk_forecast()

    floor = parse_harvest_iso(cursor.next_window_start)
    until = parse_harvest_iso(cursor.harvest_until)
    high_water = parse_harvest_iso(cursor.high_water)
    direction = cursor.walk_direction

    if direction == "forward":
        window_span = (
            span_days(floor, high_water) if floor is not None and high_water is not None else 0.0
        )
        walked_recent = (
            span_days(until, high_water) if until is not None and high_water is not None else 0.0
        )
        return WalkForecast(
            walk_direction=direction,
            floor_at=cursor.next_window_start,
            harvest_until=cursor.harvest_until,
            high_water=cursor.high_water,
            cursor_updated_at=cursor.updated_at,
            unwalked_days=0.0,
            walked_recent_days=walked_recent,
            window_span_days=window_span,
            walked_pct=100.0,
            forecast_ready=True,
            complete_windows=0,
            incomplete_windows=0,
            median_rate=0.0,
            upper_rate=0.0,
            median_usd=0.0,
            upper_usd=0.0,
        )

    if direction != "backward" or floor is None or until is None or high_water is None:
        return WalkForecast(
            walk_direction=direction,
            floor_at=cursor.next_window_start,
            harvest_until=cursor.harvest_until,
            high_water=cursor.high_water,
            cursor_updated_at=cursor.updated_at,
            unwalked_days=0.0,
            walked_recent_days=0.0,
            window_span_days=0.0,
            walked_pct=0.0,
            forecast_ready=False,
            complete_windows=0,
            incomplete_windows=0,
            median_rate=0.0,
            upper_rate=0.0,
            median_usd=0.0,
            upper_usd=0.0,
        )

    unwalked = span_days(floor, until)
    walked_recent = span_days(until, high_water)
    window_span = span_days(floor, high_water)
    walked_pct = (walked_recent / window_span * 100.0) if window_span > 0 else 0.0

    complete_rates: list[float] = []
    incomplete = 0
    for run in runs:
        start = parse_harvest_iso(run.window_start)
        end = parse_harvest_iso(run.window_end)
        if start is None or end is None:
            continue
        if not _window_in_walked_span(
            start, end, span_start=until, span_end=high_water
        ):
            continue
        days = span_days(start, end)
        if days <= 0:
            continue
        if run.incomplete_results:
            incomplete += 1
            continue
        if run.total_count is None:
            continue
        complete_rates.append(run.total_count / days)

    complete = len(complete_rates)
    ready = complete >= MIN_COMPLETE_WINDOWS and blended_usd > 0
    median_rate = 0.0
    upper_rate = 0.0
    median_usd = 0.0
    upper_usd = 0.0
    if ready:
        median_rate = float(statistics.median(complete_rates))
        upper_rate = float(max(complete_rates))
        median_usd = median_rate * unwalked * blended_usd
        upper_usd = upper_rate * unwalked * blended_usd

    return WalkForecast(
        walk_direction=direction,
        floor_at=cursor.next_window_start,
        harvest_until=cursor.harvest_until,
        high_water=cursor.high_water,
        cursor_updated_at=cursor.updated_at,
        unwalked_days=unwalked,
        walked_recent_days=walked_recent,
        window_span_days=window_span,
        walked_pct=walked_pct,
        forecast_ready=ready,
        complete_windows=complete,
        incomplete_windows=incomplete,
        median_rate=median_rate,
        upper_rate=upper_rate,
        median_usd=median_usd,
        upper_usd=upper_usd,
    )
