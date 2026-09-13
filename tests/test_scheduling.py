from datetime import UTC, date, datetime
from pathlib import Path
from typing import Literal

from edgar_monitor.observability import PipelineRunRecord
from edgar_monitor.scheduling import (
    build_scheduled_source_plan,
    extract_failed_source_dates,
)


def make_run_record(
    *,
    status: Literal["succeeded", "failed"],
    error_message: str | None,
) -> PipelineRunRecord:
    return PipelineRunRecord(
        run_id="example-run",
        status=status,
        started_at=datetime(2026, 9, 13, 12, 0, tzinfo=UTC),
        finished_at=datetime(2026, 9, 13, 12, 1, tzinfo=UTC),
        source_dates_planned=1,
        source_dates_succeeded=0 if status == "failed" else 1,
        source_dates_failed=1 if status == "failed" else 0,
        raw_rows=0,
        validated_records=0,
        quarantined_records=0,
        target_records=0,
        inserted_records=0,
        updated_records=0,
        unchanged_records=0,
        error_message=error_message,
    )


def test_extract_failed_source_dates_uses_failed_run_errors() -> None:
    failed_record = make_run_record(
        status="failed",
        error_message=(
            "2026-09-09: SEC response failed; "
            "2026-09-10: Expected SEC master-index header was not found."
        ),
    )
    successful_record = make_run_record(
        status="succeeded",
        error_message=None,
    )

    failed_dates = extract_failed_source_dates(
        (failed_record, successful_record)
    )

    assert failed_dates == (
        date(2026, 9, 9),
        date(2026, 9, 10),
    )


def test_build_scheduled_source_plan_uses_lookback_without_ledger(
    tmp_path: Path,
) -> None:
    plan = build_scheduled_source_plan(
        run_date=date(2026, 9, 13),
        ledger_path=tmp_path / "missing_ledger.jsonl",
        lookback_days=3,
    )

    assert plan.failed_source_dates == ()
    assert plan.source_dates == (
        date(2026, 9, 9),
        date(2026, 9, 10),
        date(2026, 9, 11),
    )