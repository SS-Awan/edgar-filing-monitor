"""Select, merge, and store curated EDGAR filing records."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import duckdb

from edgar_monitor.models import FilingRecord

TARGET_FORM_TYPES = frozenset({"10-K", "10-Q", "8-K"})


@dataclass(frozen=True)
class MergeMetrics:
    """Counts produced by one accession-number merge operation."""

    inserted: int
    updated: int
    unchanged: int


@dataclass(frozen=True)
class MergeResult:
    """Canonical records and metrics after an idempotent merge."""

    records: tuple[FilingRecord, ...]
    metrics: MergeMetrics


def select_target_filings(
    records: tuple[FilingRecord, ...],
) -> tuple[FilingRecord, ...]:
    """Keep only the filing forms represented by this project."""
    return tuple(record for record in records if record.form_type in TARGET_FORM_TYPES)


def merge_filing_records(
    existing_records: tuple[FilingRecord, ...],
    incoming_records: tuple[FilingRecord, ...],
) -> MergeResult:
    """Merge records by accession number without creating duplicates."""
    records_by_accession = {
        record.accession_number: record for record in existing_records
    }

    inserted = 0
    updated = 0
    unchanged = 0

    for incoming_record in incoming_records:
        existing_record = records_by_accession.get(incoming_record.accession_number)

        if existing_record is None:
            records_by_accession[incoming_record.accession_number] = incoming_record
            inserted += 1
        elif existing_record.model_dump() == incoming_record.model_dump():
            unchanged += 1
        else:
            records_by_accession[incoming_record.accession_number] = incoming_record
            updated += 1

    canonical_records = tuple(
        sorted(
            records_by_accession.values(),
            key=lambda record: (record.filing_date, record.accession_number),
        )
    )

    return MergeResult(
        records=canonical_records,
        metrics=MergeMetrics(
            inserted=inserted,
            updated=updated,
            unchanged=unchanged,
        ),
    )


def write_partitioned_parquet(
    records: tuple[FilingRecord, ...],
    output_directory: Path,
) -> None:
    """Write curated records to Parquet partitions with DuckDB."""
    if not records:
        raise ValueError("Cannot write an empty curated dataset.")

    output_directory.mkdir(parents=True, exist_ok=True)

    rows = [
        (
            record.cik,
            record.company_name,
            record.form_type,
            record.filing_date,
            record.filename,
            record.accession_number,
            record.source_line_number,
            record.filing_date.year,
        )
        for record in records
    ]

    escaped_output_directory = str(output_directory.resolve()).replace("'", "''")

    with duckdb.connect() as connection:
        connection.execute(
            """
            CREATE TABLE filings (
                cik VARCHAR,
                company_name VARCHAR,
                form_type VARCHAR,
                filing_date DATE,
                filename VARCHAR,
                accession_number VARCHAR,
                source_line_number INTEGER,
                filing_year INTEGER
            )
            """
        )
        connection.executemany(
            """
            INSERT INTO filings VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        connection.execute(
            f"""
            COPY filings TO '{escaped_output_directory}'
            (
                FORMAT PARQUET,
                PARTITION_BY (filing_year, form_type),
                OVERWRITE_OR_IGNORE TRUE
            )
            """
        )