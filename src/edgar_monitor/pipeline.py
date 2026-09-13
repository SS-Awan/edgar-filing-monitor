"""Orchestrate SEC ingestion, validation, curation, and observability."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path

import httpx

from edgar_monitor.curation import (
    MergeResult,
    merge_filing_records,
    select_target_filings,
    write_partitioned_parquet,
)
from edgar_monitor.index_parser import (
    MasterIndexFormatError,
    parse_master_index,
)
from edgar_monitor.models import FilingRecord, QuarantineRecord
from edgar_monitor.observability import (
    PipelineRunRecord,
    append_run_record,
)
from edgar_monitor.raw_storage import (
    DEFAULT_RAW_RETENTION_DAYS,
    prune_raw_snapshots,
    write_raw_snapshot,
)
from edgar_monitor.sec_client import (
    FetchedSource,
    SourceFetchError,
    fetch_daily_master_index,
)
from edgar_monitor.validation import validate_raw_rows


@dataclass(frozen=True)
class PipelineRunResult:
    """Outputs retained from one pipeline run."""

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
    raw_directory: Path | None = None,
    raw_retention_days: int = DEFAULT_RAW_RETENTION_DAYS,
    retention_today: date | None = None,
) -> PipelineRunResult:
    """Run the filing-monitor pipeline for one or more SEC source dates."""
    started_at = datetime.now(UTC)
    fetched_sources: list[FetchedSource] = []
    valid_records: list[FilingRecord] = []
    quarantined_rows: list[QuarantineRecord] = []
    errors: list[str] = []
    succeeded_dates = 0
    failed_dates = 0

    for source_date in source_dates:
        try:
            fetched_source = fetch_daily_master_index(source_date, client)
            fetched_sources.append(fetched_source)

            if raw_directory is not None:
                write_raw_snapshot(fetched_source, raw_directory)

            document = parse_master_index(fetched_source.payload)
            validated_records, source_quarantine = validate_raw_rows(
                document.rows
            )

            valid_records.extend(validated_records)
            quarantined_rows.extend(source_quarantine)
            succeeded_dates += 1

        except (
            SourceFetchError,
            MasterIndexFormatError,
            ValueError,
        ) as error:
            failed_dates += 1
            errors.append(f"{source_date.isoformat()}: {error}")

    if raw_directory is not None:
        prune_raw_snapshots(
            raw_directory,
            today=retention_today or date.today(),
            retention_days=raw_retention_days,
        )

    target_records = select_target_filings(tuple(valid_records))
    merge_result = merge_filing_records(existing_records, target_records)

    if merge_result.records:
        write_partitioned_parquet(
            merge_result.records,
            output_directory,
        )

    finished_at = datetime.now(UTC)
    status = "succeeded" if not errors else "failed"
    error_message = "; ".join(errors) if errors else None

    run_record = PipelineRunRecord(
        run_id=run_id,
        status=status,
        started_at=started_at,
        finished_at=finished_at,
        source_dates_planned=len(source_dates),
        source_dates_succeeded=succeeded_dates,
        source_dates_failed=failed_dates,
        raw_rows=len(valid_records) + len(quarantined_rows),
        validated_records=len(valid_records),
        quarantined_records=len(quarantined_rows),
        target_records=len(target_records),
        inserted_records=merge_result.metrics.inserted,
        updated_records=merge_result.metrics.updated,
        unchanged_records=merge_result.metrics.unchanged,
        error_message=error_message,
    )
    append_run_record(ledger_path, run_record)

    return PipelineRunResult(
        run_record=run_record,
        fetched_sources=tuple(fetched_sources),
        quarantined_rows=tuple(quarantined_rows),
        merge_result=merge_result,
    )