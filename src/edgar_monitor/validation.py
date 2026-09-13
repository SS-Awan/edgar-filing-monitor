"""Validate parsed SEC master-index rows and quarantine invalid records."""
from __future__ import annotations

import re
from datetime import date, datetime

from pydantic import ValidationError

from edgar_monitor.index_parser import RawIndexRow
from edgar_monitor.models import FilingRecord, QuarantineRecord

ACCESSION_NUMBER_PATTERN = re.compile(r"\d{10}-\d{2}-\d{6}")


def extract_accession_number(filename: str) -> str | None:
    """Extract an EDGAR accession number from an index filename."""
    match = ACCESSION_NUMBER_PATTERN.search(filename)
    return match.group(0) if match else None


def parse_filing_date(value: str) -> date:
    """Parse current SEC compact dates and legacy ISO-date fixture values."""
    for date_format in ("%Y%m%d", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, date_format).date()
        except ValueError:
            continue

    raise ValueError(
        f"Invalid filing date {value!r}; expected YYYYMMDD or YYYY-MM-DD."
    )


def validate_raw_rows(
    rows: tuple[RawIndexRow, ...],
) -> tuple[tuple[FilingRecord, ...], tuple[QuarantineRecord, ...]]:
    """Validate source rows and return valid filings plus quarantined rows."""
    valid_records: list[FilingRecord] = []
    quarantined_records: list[QuarantineRecord] = []

    for row in rows:
        if len(row.values) != 5:
            quarantined_records.append(
                QuarantineRecord(
                    source_line_number=row.line_number,
                    raw_line=row.raw_line,
                    reason="column_count",
                    detail=(
                        "Expected 5 pipe-delimited columns, "
                        f"received {len(row.values)}."
                    ),
                )
            )
            continue

        cik, company_name, form_type, raw_filing_date, filename = row.values
        accession_number = extract_accession_number(filename)

        if accession_number is None:
            quarantined_records.append(
                QuarantineRecord(
                    source_line_number=row.line_number,
                    raw_line=row.raw_line,
                    reason="missing_accession_number",
                    detail="Could not extract an accession number from filename.",
                )
            )
            continue

        try:
            filing_date = parse_filing_date(raw_filing_date)
        except ValueError as error:
            quarantined_records.append(
                QuarantineRecord(
                    source_line_number=row.line_number,
                    raw_line=row.raw_line,
                    reason="validation_error",
                    detail=str(error),
                )
            )
            continue

        try:
            valid_records.append(
                FilingRecord(
                    cik=cik,
                    company_name=company_name,
                    form_type=form_type,
                    filing_date=filing_date,
                    filename=filename,
                    accession_number=accession_number,
                    source_line_number=row.line_number,
                )
            )
        except ValidationError as error:
            quarantined_records.append(
                QuarantineRecord(
                    source_line_number=row.line_number,
                    raw_line=row.raw_line,
                    reason="validation_error",
                    detail=str(error),
                )
            )

    return tuple(valid_records), tuple(quarantined_records)