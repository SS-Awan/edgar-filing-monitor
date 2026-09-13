"""Plan recurring lookback and manual backfill source dates."""

from __future__ import annotations

from datetime import date, timedelta

DEFAULT_LOOKBACK_DAYS = 7
MAX_BACKFILL_DAYS = 31


def _nth_weekday_of_month(
    year: int,
    month: int,
    weekday: int,
    occurrence: int,
) -> date:
    """Return the requested weekday occurrence within a month."""
    first_day = date(year, month, 1)
    days_until_weekday = (weekday - first_day.weekday()) % 7
    return first_day + timedelta(days=days_until_weekday + 7 * (occurrence - 1))


def _last_weekday_of_month(year: int, month: int, weekday: int) -> date:
    """Return the final requested weekday within a month."""
    if month == 12:
        next_month = date(year + 1, 1, 1)
    else:
        next_month = date(year, month + 1, 1)

    final_day = next_month - timedelta(days=1)
    days_since_weekday = (final_day.weekday() - weekday) % 7
    return final_day - timedelta(days=days_since_weekday)


def _observed_date(holiday_date: date) -> date:
    """Return the weekday on which a fixed-date holiday is observed."""
    if holiday_date.weekday() == 5:
        return holiday_date - timedelta(days=1)
    if holiday_date.weekday() == 6:
        return holiday_date + timedelta(days=1)
    return holiday_date


def _sec_market_holidays(year: int) -> frozenset[date]:
    """Return SEC market holidays for a calendar year."""
    holidays = {
        _observed_date(date(year, 1, 1)),
        _nth_weekday_of_month(year, 1, weekday=0, occurrence=3),
        _nth_weekday_of_month(year, 2, weekday=0, occurrence=3),
        _last_weekday_of_month(year, 5, weekday=0),
        _observed_date(date(year, 6, 19)),
        _observed_date(date(year, 7, 4)),
        _nth_weekday_of_month(year, 9, weekday=0, occurrence=1),
        _nth_weekday_of_month(year, 11, weekday=3, occurrence=4),
        _observed_date(date(year, 12, 25)),
    }
    return frozenset(holidays)


def is_sec_market_holiday(source_date: date) -> bool:
    """Return whether the SEC daily filing index is unavailable for a holiday."""
    relevant_years = (
        source_date.year - 1,
        source_date.year,
        source_date.year + 1,
    )
    return any(
        source_date in _sec_market_holidays(year)
        for year in relevant_years
    )


def is_business_day(source_date: date) -> bool:
    """Return whether the SEC daily filing index should exist for a date."""
    return source_date.weekday() < 5 and not is_sec_market_holiday(source_date)


def plan_lookback_dates(
    run_date: date,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    failed_source_dates: tuple[date, ...] = (),
) -> tuple[date, ...]:
    """Return recent completed filing dates plus eligible failed source dates."""
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
    """Return an inclusive, bounded range of SEC filing dates for backfill."""
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