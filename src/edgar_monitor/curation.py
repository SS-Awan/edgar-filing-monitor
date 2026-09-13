"""Select, merge, and store curated EDGAR filing records."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import duckdb

from edgar_monitor.models import FilingRecord

TARGET_FORM_TYPES = frozenset({"10-K", "10-Q", "8-K"})


@dataclass(frozen=True)
class MergeMetrics:
    """Counts produced while merging incoming records into curated state."""

    inserted: int
    updated: int
    unchanged: int


@dataclass(frozen=True)
class MergeResult:
    """Canonical curated records and their merge metrics."""

    records: tuple[FilingRecord, ...]
    metrics: MergeMetrics


def filing_identity(record: FilingRecord) -> tuple[str, str]:
    """Return the EDGAR index identity for one company-filing relationship.

    An accession number can legitimately appear under multiple CIKs when one
    filing is associated with related legal entities. Therefore, accession
    number alone is not a safe unique key for the daily master index.
    """
    return record.cik, record.accession_number


def select_target_filings(
    records: tuple[FilingRecord, ...],
) -> tuple[FilingRecord, ...]:
    """Keep only the filing types monitored by this pipeline."""
    return tuple(
        record for record in records if record.form_type in TARGET_FORM_TYPES
    )


def merge_filing_records(
    existing_records: tuple[FilingRecord, ...],
    incoming_records: tuple[FilingRecord, ...],
) -> MergeResult:
    """Merge records idempotently using CIK plus accession number."""
    records_by_identity = {
        filing_identity(record): record for record in existing_records
    }

    inserted = 0
    updated = 0
    unchanged = 0

    for incoming_record in incoming_records:
        identity = filing_identity(incoming_record)
        existing_record = records_by_identity.get(identity)

        if existing_record is None:
            records_by_identity[identity] = incoming_record
            inserted += 1
        elif existing_record.model_dump() == incoming_record.model_dump():
            unchanged += 1
        else:
            records_by_identity[identity] = incoming_record
            updated += 1

    merged_records = tuple(
        sorted(
            records_by_identity.values(),
            key=lambda record: (
                record.filing_date,
                record.cik,
                record.accession_number,
            ),
        )
    )

    return MergeResult(
        records=merged_records,
        metrics=MergeMetrics(
            inserted=inserted,
            updated=updated,
            unchanged=unchanged,
        ),
    )


def read_partitioned_parquet(
    input_directory: Path,
) -> tuple[FilingRecord, ...]:
    """Restore curated filing records from partitioned Parquet state."""
    parquet_files = list(input_directory.rglob("*.parquet"))

    if not parquet_files:
        return ()

    parquet_glob = (input_directory / "**" / "*.parquet").as_posix()

    with duckdb.connect(database=":memory:") as connection:
        rows = connection.execute(
            """
            SELECT
                cik,
                company_name,
                form_type,
                filing_date,
                filename,
                accession_number,
                source_line_number
            FROM read_parquet(?)
            ORDER BY filing_date, cik, accession_number
            """,
            [parquet_glob],
        ).fetchall()

    return tuple(
        FilingRecord(
            cik=row[0],
            company_name=row[1],
            form_type=row[2],
            filing_date=row[3],
            filename=row[4],
            accession_number=row[5],
            source_line_number=row[6],
        )
        for row in rows
    )


def write_partitioned_parquet(
    records: tuple[FilingRecord, ...],
    output_directory: Path,
) -> None:
    """Write curated records as Parquet partitioned by year and form type."""
    if not records:
        raise ValueError("Cannot write an empty curated dataset.")

    output_directory.mkdir(parents=True, exist_ok=True)
    output_path = output_directory.as_posix().replace("'", "''")

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

    with duckdb.connect(database=":memory:") as connection:
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
            COPY filings TO '{output_path}'
            (
                FORMAT PARQUET,
                PARTITION_BY (filing_year, form_type),
                OVERWRITE_OR_IGNORE TRUE
            )
            """
        )