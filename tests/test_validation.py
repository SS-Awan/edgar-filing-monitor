from pathlib import Path

from edgar_monitor.index_parser import RawIndexRow, parse_master_index
from edgar_monitor.validation import validate_raw_rows

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "sample_master.idx"


def test_validate_raw_rows_returns_typed_records() -> None:
    document = parse_master_index(FIXTURE_PATH.read_text(encoding="utf-8"))

    valid_records, quarantined_rows = validate_raw_rows(document.rows)

    assert len(valid_records) == 4
    assert not quarantined_rows
    assert valid_records[0].cik == "0000320193"
    assert valid_records[0].accession_number == "0000320193-26-000001"


def test_validate_raw_rows_quarantines_wrong_column_count() -> None:
    rows = (
        RawIndexRow(
            line_number=10,
            raw_line="0000320193|Apple Inc.|10-K",
            values=("0000320193", "Apple Inc.", "10-K"),
        ),
    )

    valid_records, quarantined_rows = validate_raw_rows(rows)

    assert not valid_records
    assert quarantined_rows[0].reason == "column_count"


def test_validate_raw_rows_quarantines_invalid_values() -> None:
    rows = (
        RawIndexRow(
            line_number=11,
            raw_line="0000320193||10-K|not-a-date|edgar/data/320193/0000320193-26-000001.txt",
            values=(
                "0000320193",
                "",
                "10-K",
                "not-a-date",
                "edgar/data/320193/0000320193-26-000001.txt",
            ),
        ),
    )

    valid_records, quarantined_rows = validate_raw_rows(rows)

    assert not valid_records
    assert quarantined_rows[0].reason == "validation_error"


def test_validate_raw_rows_quarantines_missing_accession_number() -> None:
    rows = (
        RawIndexRow(
            line_number=12,
            raw_line="0000320193|Apple Inc.|10-K|2026-01-31|edgar/data/320193/report.txt",
            values=(
                "0000320193",
                "Apple Inc.",
                "10-K",
                "2026-01-31",
                "edgar/data/320193/report.txt",
            ),
        ),
    )

    valid_records, quarantined_rows = validate_raw_rows(rows)

    assert not valid_records
    assert quarantined_rows[0].reason == "missing_accession_number"