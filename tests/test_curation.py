from datetime import date
from pathlib import Path

from edgar_monitor.curation import (
    merge_filing_records,
    read_partitioned_parquet,
    select_target_filings,
    write_partitioned_parquet,
)
from edgar_monitor.models import FilingRecord


def make_record(
    *,
    cik: str = "0000320193",
    company_name: str = "APPLE INC",
    form_type: str = "10-K",
    filing_date: date = date(2026, 9, 10),
    accession_number: str = "0000320193-26-000001",
    source_line_number: int = 10,
) -> FilingRecord:
    return FilingRecord(
        cik=cik,
        company_name=company_name,
        form_type=form_type,
        filing_date=filing_date,
        filename=(
            f"edgar/data/{int(cik)}/{accession_number}.txt"
        ),
        accession_number=accession_number,
        source_line_number=source_line_number,
    )


def test_select_target_filings_keeps_monitored_forms() -> None:
    target_record = make_record(form_type="10-Q")
    non_target_record = make_record(
        form_type="4",
        accession_number="0000320193-26-000002",
    )

    selected_records = select_target_filings(
        (target_record, non_target_record)
    )

    assert selected_records == (target_record,)


def test_merge_filing_records_is_idempotent_for_same_record() -> None:
    record = make_record()

    merge_result = merge_filing_records((record,), (record,))

    assert merge_result.records == (record,)
    assert merge_result.metrics.inserted == 0
    assert merge_result.metrics.updated == 0
    assert merge_result.metrics.unchanged == 1


def test_merge_filing_records_updates_changed_record() -> None:
    existing_record = make_record(source_line_number=10)
    incoming_record = make_record(source_line_number=20)

    merge_result = merge_filing_records(
        (existing_record,),
        (incoming_record,),
    )

    assert merge_result.records == (incoming_record,)
    assert merge_result.metrics.inserted == 0
    assert merge_result.metrics.updated == 1
    assert merge_result.metrics.unchanged == 0


def test_same_accession_for_different_ciks_is_preserved() -> None:
    first_record = make_record(
        cik="0001657853",
        company_name="HERTZ GLOBAL HOLDINGS, INC",
        form_type="8-K",
        accession_number="0001657853-26-000057",
        source_line_number=1226,
    )
    second_record = make_record(
        cik="0000047129",
        company_name="HERTZ CORP",
        form_type="8-K",
        accession_number="0001657853-26-000057",
        source_line_number=3295,
    )

    merge_result = merge_filing_records((), (first_record, second_record))

    assert len(merge_result.records) == 2
    assert merge_result.metrics.inserted == 2
    assert merge_result.metrics.updated == 0
    assert merge_result.metrics.unchanged == 0


def test_partitioned_parquet_can_be_restored(tmp_path: Path) -> None:
    first_record = make_record()
    second_record = make_record(
        cik="0000789019",
        company_name="MICROSOFT CORP",
        form_type="10-Q",
        accession_number="0000789019-26-000001",
    )
    output_directory = tmp_path / "curated"

    write_partitioned_parquet(
        (first_record, second_record),
        output_directory,
    )
    restored_records = read_partitioned_parquet(output_directory)

    assert restored_records == (first_record, second_record)