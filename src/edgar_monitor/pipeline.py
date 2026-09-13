"""Orchestrate one complete EDGAR Filing Monitor pipeline run."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Literal

import httpx

from edgar_monitor.curation import MergeResult, merge_filing_records, select_target_filings
from edgar_monitor.index_parser import MasterIndexFormatError, parse_master_index
from edgar_monitor.models import FilingRecord, QuarantineRecord
from edgar_monitor.observability import (
    PipelineRunRecord,
    append_run_record,
)
from edgar_monitor.sec_client import (
    FetchedSource,
    SourceFetchError,
    fetch_daily_master_index,
)
from edgar_monitor.validation import validate_raw_rows
from edgar_monitor.curation import write_partitioned_parquet


@dataclass(frozen=True)
class PipelineRunResult:
    """Outputs produced by one complete pipeline run."""

    run_record: PipelineRunRecord
    fetched_sources: tuple[FetchedSource, ...]
    quarantined_rows: tuple[QuarantineRecord, ...]
    merge_result: MergeResult


def run_pipeline(
    source_dates: tuple[date, ...],
    client: httpx.Client,
    existing_records: tuple[FilingRecord, ...],
    output_directory: Path,
    ledger_path: Path,
    run_id: str,
) -> PipelineRunResult:
    """Fetch, parse, validate, curate, store, and record one pipeline run."""
    started_at = datetime.now(UTC)
    fetched_sources: list[FetchedSource] = []
    validated_records: list[FilingRecord] = []
    quarantined_rows: list[QuarantineRecord] = []
    errors: list[str] = []
    raw_row_count = 0

    for source_date in source_dates:
        try:
            fetched_source = fetch_daily_master_index(source_date, client)
            document = parse_master_index(fetched_source.payload)
        except (SourceFetchError, MasterIndexFormatError) as error:
            errors.append(f"{source_date}: {error}")
            continue

        fetched_sources.append(fetched_source)
        raw_row_count += len(document.rows)

        valid_rows, rejected_rows = validate_raw_rows(document.rows)
        validated_records.extend(valid_rows)
        quarantined_rows.extend(rejected_rows)

    target_records = select_target_filings(tuple(validated_records))
    merge_result = merge_filing_records(existing_records, target_records)

    if merge_result.records:
        write_partitioned_parquet(merge_result.records, output_directory)

    finished_at = datetime.now(UTC)
    status: Literal["succeeded", "failed"] = "failed" if errors else "succeeded"

    run_record = PipelineRunRecord(
        run_id=run_id,
        status=status,
        started_at=started_at,
        finished_at=finished_at,
        source_dates_planned=len(source_dates),
        source_dates_succeeded=len(fetched_sources),
        source_dates_failed=len(errors),
        raw_rows=raw_row_count,
        validated_records=len(validated_records),
        quarantined_records=len(quarantined_rows),
        target_records=len(target_records),
        inserted_records=merge_result.metrics.inserted,
        updated_records=merge_result.metrics.updated,
        unchanged_records=merge_result.metrics.unchanged,
        error_message="; ".join(errors) if errors else None,
    )
    append_run_record(ledger_path, run_record)

    return PipelineRunResult(
        run_record=run_record,
        fetched_sources=tuple(fetched_sources),
        quarantined_rows=tuple(quarantined_rows),
        merge_result=merge_result,
    )