"""Plan recurring lookback and manual backfill source dates."""

from __future__ import annotations

from datetime import date, timedelta

DEFAULT_LOOKBACK_DAYS = 7
MAX_BACKFILL_DAYS = 31


def is_business_day(source_date: date) -> bool:
    """Return whether a date is Monday through Friday."""
    return source_date.weekday() < 5


def plan_lookback_dates(
    run_date: date,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    failed_source_dates: tuple[date, ...] = (),
) -> tuple[date, ...]:
    """Return recent completed business dates plus eligible failed source dates."""
    if lookback_days < 1:
        raise ValueError("lookback_days must be at least 1.")

    recent_dates: list[date] = []
    candidate_date = run_date - timedelta(days=1)

    while len(recent_dates) < lookback_days:
        if is_business_day(candidate_date):
            recent_dates.append(candidate_date)
        candidate_date -= timedelta(days=1)

    retry_dates = {
        source_date
        for source_date in failed_source_dates
        if source_date < run_date and is_business_day(source_date)
    }

    return tuple(sorted(set(recent_dates) | retry_dates))


def plan_backfill_dates(
    start_date: date,
    end_date: date,
    max_days: int = MAX_BACKFILL_DAYS,
) -> tuple[date, ...]:
    """Return an inclusive, bounded range of business dates for manual backfill."""
    if start_date > end_date:
        raise ValueError("start_date must be on or before end_date.")

    calendar_day_count = (end_date - start_date).days + 1
    if calendar_day_count > max_days:
        raise ValueError(f"Backfill cannot exceed {max_days} calendar days.")

    return tuple(
        start_date + timedelta(days=offset)
        for offset in range(calendar_day_count)
        if is_business_day(start_date + timedelta(days=offset))
    )