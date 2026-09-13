"""Plan recurring lookback and manual backfill source dates."""

from __future__ import annotations

from datetime import date, timedelta

DEFAULT_LOOKBACK_DAYS = 7
MAX_BACKFILL_DAYS = 31


def plan_lookback_dates(
    run_date: date,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    failed_source_dates: tuple[date, ...] = (),
) -> tuple[date, ...]:
    """Return completed recent dates plus any eligible failed source dates."""
    if lookback_days < 1:
        raise ValueError("lookback_days must be at least 1.")

    recent_dates = {
        run_date - timedelta(days=offset)
        for offset in range(1, lookback_days + 1)
    }

    retry_dates = {
        source_date
        for source_date in failed_source_dates
        if source_date < run_date
    }

    return tuple(sorted(recent_dates | retry_dates))


def plan_backfill_dates(
    start_date: date,
    end_date: date,
    max_days: int = MAX_BACKFILL_DAYS,
) -> tuple[date, ...]:
    """Return an inclusive, bounded range for an intentional manual backfill."""
    if start_date > end_date:
        raise ValueError("start_date must be on or before end_date.")

    date_count = (end_date - start_date).days + 1
    if date_count > max_days:
        raise ValueError(f"Backfill cannot exceed {max_days} calendar days.")

    return tuple(
        start_date + timedelta(days=offset)
        for offset in range(date_count)
    )