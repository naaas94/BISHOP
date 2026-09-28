"""Walk-density forecast for the unwalked harvest window."""

from __future__ import annotations

from bishop_shared.harvest_forecast import MIN_COMPLETE_WINDOWS, compute_walk_forecast
from bishop_shared.harvest_ledger import HarvestCursor, HarvestRun

_BLENDED = 0.000764
_UPDATED = "2026-09-27T12:00:00Z"


def _cursor(
    *,
    direction: str,
    floor: str,
    until: str,
    high_water: str,
) -> HarvestCursor:
    return HarvestCursor(
        source="github",
        next_window_start=floor,
        harvest_until=until,
        updated_at=_UPDATED,
        walk_direction=direction,
        high_water=high_water,
    )


def _run(
    *,
    start: str,
    end: str,
    total: int,
    incomplete: bool = False,
) -> HarvestRun:
    return HarvestRun(
        source="github",
        query="pushed:x stars:>10",
        window_start=start,
        window_end=end,
        total_count=total,
        incomplete_results=incomplete,
        pages_fetched=1,
        items_upserted=total,
        http_status=200,
        ratelimit_remaining=10,
        ratelimit_reset=None,
        started_at=start,
        finished_at=end,
    )


def test_forecast_waiting_below_three_complete_windows() -> None:
    cursor = _cursor(
        direction="backward",
        floor="2024-12-15T00:00:00Z",
        until="2026-09-20T00:00:00Z",
        high_water="2026-09-27T00:00:00Z",
    )
    runs = [
        _run(start="2026-09-20T00:00:00Z", end="2026-09-23T00:00:00Z", total=300),
        _run(start="2026-09-23T00:00:00Z", end="2026-09-27T00:00:00Z", total=400),
    ]
    forecast = compute_walk_forecast(cursor, runs, blended_usd=_BLENDED)
    assert forecast.complete_windows == 2
    assert forecast.complete_windows < MIN_COMPLETE_WINDOWS
    assert forecast.forecast_ready is False
    assert forecast.median_usd == 0.0
    assert forecast.upper_usd == 0.0
    assert forecast.unwalked_days > 600


def test_forecast_censors_incomplete_and_uses_median_not_sum() -> None:
    cursor = _cursor(
        direction="backward",
        floor="2024-12-15T00:00:00Z",
        until="2026-09-20T00:00:00Z",
        high_water="2026-09-27T00:00:00Z",
    )
    runs = [
        _run(start="2026-09-20T00:00:00Z", end="2026-09-22T00:00:00Z", total=200),
        _run(start="2026-09-22T00:00:00Z", end="2026-09-24T00:00:00Z", total=400),
        _run(start="2026-09-24T00:00:00Z", end="2026-09-27T00:00:00Z", total=900),
        _run(
            start="2026-09-21T00:00:00Z",
            end="2026-09-23T00:00:00Z",
            total=1000,
            incomplete=True,
        ),
        _run(start="2024-12-20T00:00:00Z", end="2024-12-27T00:00:00Z", total=5000),
    ]
    forecast = compute_walk_forecast(cursor, runs, blended_usd=_BLENDED)
    assert forecast.incomplete_windows == 1
    assert forecast.complete_windows == 3
    assert forecast.forecast_ready is True
    assert forecast.median_rate == 200.0
    assert forecast.upper_rate == 300.0
    assert forecast.median_usd == forecast.median_rate * forecast.unwalked_days * _BLENDED
    assert forecast.upper_usd == forecast.upper_rate * forecast.unwalked_days * _BLENDED
    summed = (100 + 200 + 300) * forecast.unwalked_days * _BLENDED
    assert forecast.median_usd != summed


def test_forecast_forward_cursor_band_is_zero() -> None:
    cursor = _cursor(
        direction="forward",
        floor="2026-09-27T10:00:00Z",
        until="2026-09-27T10:00:00Z",
        high_water="2026-09-27T10:00:00Z",
    )
    runs = [
        _run(start="2026-09-20T00:00:00Z", end="2026-09-27T00:00:00Z", total=900),
        _run(start="2026-09-13T00:00:00Z", end="2026-09-20T00:00:00Z", total=800),
        _run(start="2026-09-06T00:00:00Z", end="2026-09-13T00:00:00Z", total=700),
    ]
    forecast = compute_walk_forecast(cursor, runs, blended_usd=_BLENDED)
    assert forecast.forecast_ready is True
    assert forecast.unwalked_days == 0.0
    assert forecast.median_usd == 0.0
    assert forecast.upper_usd == 0.0
    assert forecast.walked_pct == 100.0


def test_forecast_none_cursor_is_empty() -> None:
    forecast = compute_walk_forecast(None, [], blended_usd=_BLENDED)
    assert forecast.forecast_ready is False
    assert forecast.walk_direction is None
    assert forecast.median_usd == 0.0
