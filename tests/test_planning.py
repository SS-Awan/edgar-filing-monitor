from datetime import date

import pytest

from edgar_monitor.planning import plan_backfill_dates, plan_lookback_dates


def test_plan_lookback_dates_uses_completed_recent_dates() -> None:
    planned_dates = plan_lookback_dates(
        run_date=date(2026, 9, 13),
        lookback_days=3,
    )

    assert planned_dates == (
        date(2026, 9, 10),
        date(2026, 9, 11),
        date(2026, 9, 12),
    )


def test_plan_lookback_dates_includes_older_failed_dates() -> None:
    planned_dates = plan_lookback_dates(
        run_date=date(2026, 9, 13),
        lookback_days=2,
        failed_source_dates=(
            date(2026, 8, 15),
            date(2026, 9, 13),
            date(2026, 9, 14),
        ),
    )

    assert planned_dates == (
        date(2026, 8, 15),
        date(2026, 9, 11),
        date(2026, 9, 12),
    )


def test_plan_lookback_dates_rejects_zero_day_window() -> None:
    with pytest.raises(ValueError, match="at least 1"):
        plan_lookback_dates(
            run_date=date(2026, 9, 13),
            lookback_days=0,
        )


def test_plan_backfill_dates_returns_inclusive_range() -> None:
    planned_dates = plan_backfill_dates(
        start_date=date(2026, 9, 10),
        end_date=date(2026, 9, 12),
    )

    assert planned_dates == (
        date(2026, 9, 10),
        date(2026, 9, 11),
        date(2026, 9, 12),
    )


def test_plan_backfill_dates_rejects_oversized_range() -> None:
    with pytest.raises(ValueError, match="cannot exceed"):
        plan_backfill_dates(
            start_date=date(2026, 1, 1),
            end_date=date(2026, 2, 1),
        )