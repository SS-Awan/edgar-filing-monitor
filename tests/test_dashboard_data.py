from datetime import UTC, date, datetime
from pathlib import Path

from edgar_monitor.curation import write_partitioned_parquet
from edgar_monitor.dashboard_data import (
    build_dashboard_data,
    write_dashboard_data,
)
from edgar_monitor.models import FilingRecord
from edgar_monitor.observability import (
    PipelineRunRecord,
    append_run_record,
)


def make_record(
    *,
    cik: str,
    company_name: str,
    form_type: str,
    accession_number: str,
) -> FilingRecord:
    return FilingRecord(
        cik=cik,
        company_name=company_name,
        form_type=form_type,
        filing_date=date(2026, 9, 10),
        filename=f"edgar/data/{int(cik)}/{accession_number}.txt",
        accession_number=accession_number,
        source_line_number=1,
    )


def test_build_dashboard_data_queries_parquet_and_run_history(
    tmp_path: Path,
) -> None:
    curated_directory = tmp_path / "curated"
    ledger_path = tmp_path / "run_ledger.jsonl"

    write_partitioned_parquet(
        (
            make_record(
                cik="0000320193",
                company_name="APPLE INC",
                form_type="10-K",
                accession_number="0000320193-26-000001",
            ),
            make_record(
                cik="0000789019",
                company_name="MICROSOFT CORP",
                form_type="10-Q",
                accession_number="0000789019-26-000001",
            ),
        ),
        curated_directory,
    )
    append_run_record(
        ledger_path,
        PipelineRunRecord(
            run_id="dashboard-test",
            status="succeeded",
            started_at=datetime(2026, 9, 13, 12, 0, tzinfo=UTC),
            finished_at=datetime(2026, 9, 13, 12, 1, tzinfo=UTC),
            source_dates_planned=1,
            source_dates_succeeded=1,
            source_dates_failed=0,
            raw_rows=2,
            validated_records=2,
            quarantined_records=0,
            target_records=2,
            inserted_records=2,
            updated_records=0,
            unchanged_records=0,
            error_message=None,
        ),
    )

    dashboard_data = build_dashboard_data(
        curated_directory=curated_directory,
        ledger_path=ledger_path,
        generated_at=datetime(2026, 9, 13, 12, 2, tzinfo=UTC),
    )

    assert dashboard_data["dataset"]["curated_relationships"] == 2
    assert dashboard_data["dataset"]["unique_companies"] == 2
    assert dashboard_data["latest_run"]["status"] == "succeeded"
    assert dashboard_data["form_type_counts"] == [
        {"form_type": "10-K", "filing_count": 1},
        {"form_type": "10-Q", "filing_count": 1},
    ]


def test_write_dashboard_data_creates_json_file(tmp_path: Path) -> None:
    output_path = tmp_path / "site" / "data" / "dashboard.json"

    dashboard_data = write_dashboard_data(
        curated_directory=tmp_path / "missing_curated",
        ledger_path=tmp_path / "missing_ledger.jsonl",
        output_path=output_path,
        generated_at=datetime(2026, 9, 13, 12, 2, tzinfo=UTC),
    )

    assert output_path.exists()
    assert dashboard_data["dataset"]["curated_relationships"] == 0