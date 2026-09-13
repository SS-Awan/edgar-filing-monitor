from datetime import date

import pytest

from edgar_monitor.planning import (
    is_business_day,
    plan_backfill_dates,
    plan_lookback_dates,
)


def test_is_business_day_excludes_labor_day() -> None:
    assert not is_business_day(date(2026, 9, 7))


def test_plan_lookback_dates_skips_weekends_and_sec_holidays() -> None:
    planned_dates = plan_lookback_dates(
        run_date=date(2026, 9, 13),
        lookback_days=4,
    )

    assert planned_dates == (
        date(2026, 9, 8),
        date(2026, 9, 9),
        date(2026, 9, 10),
        date(2026, 9, 11),
    )


def test_plan_lookback_dates_includes_older_failed_business_dates() -> None:
    planned_dates = plan_lookback_dates(
        run_date=date(2026, 9, 13),
        lookback_days=2,
        failed_source_dates=(
            date(2026, 8, 14),
            date(2026, 9, 7),
            date(2026, 9, 12),
            date(2026, 9, 13),
            date(2026, 9, 14),
        ),
    )

    assert planned_dates == (
        date(2026, 8, 14),
        date(2026, 9, 10),
        date(2026, 9, 11),
    )


def test_plan_lookback_dates_rejects_zero_day_window() -> None:
    with pytest.raises(ValueError, match="at least 1"):
        plan_lookback_dates(
            run_date=date(2026, 9, 13),
            lookback_days=0,
        )


def test_plan_backfill_dates_returns_only_business_dates() -> None:
    planned_dates = plan_backfill_dates(
        start_date=date(2026, 9, 7),
        end_date=date(2026, 9, 13),
    )

    assert planned_dates == (
        date(2026, 9, 8),
        date(2026, 9, 9),
        date(2026, 9, 10),
        date(2026, 9, 11),
    )


def test_plan_backfill_dates_rejects_oversized_range() -> None:
    with pytest.raises(ValueError, match="cannot exceed"):
        plan_backfill_dates(
            start_date=date(2026, 1, 1),
            end_date=date(2026, 2, 1),
        )