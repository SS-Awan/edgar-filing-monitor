from datetime import date
from pathlib import Path

import duckdb

from edgar_monitor.curation import (
    merge_filing_records,
    read_partitioned_parquet,
    select_target_filings,
    write_partitioned_parquet,
)
from edgar_monitor.index_parser import parse_master_index
from edgar_monitor.models import FilingRecord
from edgar_monitor.validation import validate_raw_rows

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "sample_master.idx"


def make_record(
    accession_number: str,
    form_type: str = "8-K",
    company_name: str = "Example Company",
) -> FilingRecord:
    return FilingRecord(
        cik="320193",
        company_name=company_name,
        form_type=form_type,
        filing_date=date(2026, 5, 1),
        filename=f"edgar/data/320193/{accession_number}.txt",
        accession_number=accession_number,
        source_line_number=1,
    )


def test_select_target_filings_excludes_untracked_forms() -> None:
    document = parse_master_index(FIXTURE_PATH.read_text(encoding="utf-8"))
    valid_records, quarantined_rows = validate_raw_rows(document.rows)

    target_records = select_target_filings(valid_records)

    assert not quarantined_rows
    assert len(target_records) == 3
    assert {record.form_type for record in target_records} == {"10-K", "10-Q", "8-K"}


def test_merge_filing_records_is_idempotent_and_updates_changed_records() -> None:
    original_record = make_record("0000320193-26-000001")
    changed_record = make_record(
        "0000320193-26-000001",
        company_name="Updated Example Company",
    )
    new_record = make_record("0000320193-26-000002", form_type="10-Q")

    result = merge_filing_records(
        existing_records=(original_record,),
        incoming_records=(original_record, changed_record, new_record),
    )

    assert len(result.records) == 2
    assert result.metrics.inserted == 1
    assert result.metrics.updated == 1
    assert result.metrics.unchanged == 1
    assert result.records[0].company_name == "Updated Example Company"


def test_write_partitioned_parquet_creates_queryable_output(tmp_path: Path) -> None:
    output_directory = tmp_path / "curated"

    write_partitioned_parquet(
        records=(
            make_record("0000320193-26-000001", form_type="8-K"),
            make_record("0000320193-26-000002", form_type="10-Q"),
        ),
        output_directory=output_directory,
    )

    parquet_files = list(output_directory.rglob("*.parquet"))
    assert parquet_files

    parquet_glob = str(output_directory / "**" / "*.parquet").replace("\\", "/")

    with duckdb.connect() as connection:
        result = connection.execute(
            "SELECT COUNT(*) FROM read_parquet(?)",
            [parquet_glob],
        ).fetchone()

    assert result is not None
    assert result[0] == 2


def test_read_partitioned_parquet_restores_curated_records(tmp_path: Path) -> None:
    output_directory = tmp_path / "curated"
    original_records = (
        make_record("0000320193-26-000001", form_type="8-K"),
        make_record("0000320193-26-000002", form_type="10-Q"),
    )

    write_partitioned_parquet(original_records, output_directory)

    restored_records = read_partitioned_parquet(output_directory)

    assert restored_records == original_records