"""Build scheduled SEC source-date plans from pipeline state."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from edgar_monitor.observability import (
    PipelineRunRecord,
    read_run_records,
)
from edgar_monitor.planning import (
    DEFAULT_LOOKBACK_DAYS,
    plan_lookback_dates,
)

FAILED_SOURCE_DATE_PATTERN = re.compile(r"(\d{4}-\d{2}-\d{2}):")


@dataclass(frozen=True)
class ScheduledSourcePlan:
    """The SEC dates selected for one scheduled pipeline run."""

    run_date: date
    source_dates: tuple[date, ...]
    failed_source_dates: tuple[date, ...]


def extract_failed_source_dates(
    records: tuple[PipelineRunRecord, ...],
) -> tuple[date, ...]:
    """Recover failed SEC dates from previously recorded run errors."""
    failed_dates: set[date] = set()

    for record in records:
        if record.status != "failed" or not record.error_message:
            continue

        for matched_date in FAILED_SOURCE_DATE_PATTERN.findall(
            record.error_message
        ):
            failed_dates.add(date.fromisoformat(matched_date))

    return tuple(sorted(failed_dates))


def build_scheduled_source_plan(
    run_date: date,
    ledger_path: Path,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
) -> ScheduledSourcePlan:
    """Plan the rolling lookback plus retries from the run ledger."""
    records = read_run_records(ledger_path) if ledger_path.exists() else ()
    failed_source_dates = extract_failed_source_dates(records)

    source_dates = plan_lookback_dates(
        run_date=run_date,
        lookback_days=lookback_days,
        failed_source_dates=failed_source_dates,
    )

    return ScheduledSourcePlan(
        run_date=run_date,
        source_dates=source_dates,
        failed_source_dates=failed_source_dates,
    )