from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from edgar_monitor.observability import (
    PipelineRunRecord,
    append_run_record,
    read_run_records,
)


def make_run_record(run_id: str = "run-001") -> PipelineRunRecord:
    started_at = datetime(2026, 9, 13, 12, 0, tzinfo=UTC)

    return PipelineRunRecord(
        run_id=run_id,
        status="succeeded",
        started_at=started_at,
        finished_at=started_at + timedelta(seconds=5),
        source_dates_planned=7,
        source_dates_succeeded=5,
        source_dates_failed=2,
        raw_rows=100,
        validated_records=95,
        quarantined_records=5,
        target_records=60,
        inserted_records=50,
        updated_records=5,
        unchanged_records=5,
    )


def test_append_and_read_run_record(tmp_path: Path) -> None:
    ledger_path = tmp_path / "run_ledger.jsonl"
    record = make_run_record()

    append_run_record(ledger_path, record)

    records = read_run_records(ledger_path)

    assert records == (record,)


def test_run_ledger_preserves_multiple_records(tmp_path: Path) -> None:
    ledger_path = tmp_path / "run_ledger.jsonl"

    append_run_record(ledger_path, make_run_record("run-001"))
    append_run_record(ledger_path, make_run_record("run-002"))

    records = read_run_records(ledger_path)

    assert [record.run_id for record in records] == ["run-001", "run-002"]


def test_run_record_rejects_invalid_completion_time() -> None:
    started_at = datetime(2026, 9, 13, 12, 0, tzinfo=UTC)

    with pytest.raises(ValueError, match="finished_at"):
        PipelineRunRecord(
            run_id="invalid-run",
            status="failed",
            started_at=started_at,
            finished_at=started_at - timedelta(seconds=1),
            source_dates_planned=1,
            source_dates_succeeded=0,
            source_dates_failed=1,
            raw_rows=0,
            validated_records=0,
            quarantined_records=0,
            target_records=0,
            inserted_records=0,
            updated_records=0,
            unchanged_records=0,
            error_message="Example failure",
        )