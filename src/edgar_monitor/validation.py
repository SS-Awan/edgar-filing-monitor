"""Validate raw SEC index rows and quarantine invalid records."""

from __future__ import annotations

from datetime import date
import re

from pydantic import ValidationError

from edgar_monitor.index_parser import RawIndexRow
from edgar_monitor.models import FilingRecord, QuarantineRecord

ACCESSION_FROM_FILENAME = re.compile(r"(\d{10}-\d{2}-\d{6})")


def extract_accession_number(filename: str) -> str | None:
    """Extract an SEC accession number from an EDGAR archive filename."""
    match = ACCESSION_FROM_FILENAME.search(filename)
    return match.group(1) if match else None


def validate_raw_rows(
    rows: tuple[RawIndexRow, ...],
) -> tuple[tuple[FilingRecord, ...], tuple[QuarantineRecord, ...]]:
    """Convert raw rows into validated records or explicit quarantine records."""
    valid_records: list[FilingRecord] = []
    quarantined_rows: list[QuarantineRecord] = []

    for row in rows:
        if len(row.values) != 5:
            quarantined_rows.append(
                QuarantineRecord(
                    source_line_number=row.line_number,
                    raw_line=row.raw_line,
                    reason="column_count",
                    detail=f"Expected 5 columns but found {len(row.values)}.",
                )
            )
            continue

        cik, company_name, form_type, filing_date, filename = row.values
        accession_number = extract_accession_number(filename)

        if accession_number is None:
            quarantined_rows.append(
                QuarantineRecord(
                    source_line_number=row.line_number,
                    raw_line=row.raw_line,
                    reason="missing_accession_number",
                    detail="Could not derive an accession number from the filename.",
                )
            )
            continue

        try:
            parsed_filing_date = date.fromisoformat(filing_date)
        except ValueError:
            quarantined_rows.append(
                QuarantineRecord(
                    source_line_number=row.line_number,
                    raw_line=row.raw_line,
                    reason="validation_error",
                    detail="filing_date: Input should be a valid ISO date.",
                )
            )
            continue

        try:
            valid_records.append(
                FilingRecord(
                    cik=cik,
                    company_name=company_name,
                    form_type=form_type,
                    filing_date=parsed_filing_date,
                    filename=filename,
                    accession_number=accession_number,
                    source_line_number=row.line_number,
                )
            )
        except ValidationError as error:
            details = "; ".join(
                f"{'.'.join(str(part) for part in item['loc'])}: {item['msg']}"
                for item in error.errors()
            )
            quarantined_rows.append(
                QuarantineRecord(
                    source_line_number=row.line_number,
                    raw_line=row.raw_line,
                    reason="validation_error",
                    detail=details,
                )
            )

    return tuple(valid_records), tuple(quarantined_rows)