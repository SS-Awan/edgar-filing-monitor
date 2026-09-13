"""Run the EDGAR Filing Monitor pipeline from the command line."""
from __future__ import annotations

import argparse
import os
import shutil
import sys
import uuid
from datetime import date
from pathlib import Path

from edgar_monitor.curation import read_partitioned_parquet
from edgar_monitor.pipeline import run_pipeline
from edgar_monitor.sec_client import create_sec_client


def parse_source_date(value: str) -> date:
    """Parse a source date supplied as YYYY-MM-DD."""
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "Source date must use YYYY-MM-DD, for example 2026-09-10."
        ) from error


def promote_curated_state(
    next_curated_directory: Path,
    curated_directory: Path,
) -> bool:
    """Replace curated state only after a successful pipeline run.

    The previous state is temporarily retained as a rollback copy while the
    replacement directory is promoted.
    """
    if not next_curated_directory.exists():
        return False

    rollback_directory = curated_directory.with_name("curated_previous")

    if rollback_directory.exists():
        shutil.rmtree(rollback_directory)

    if curated_directory.exists():
        curated_directory.replace(rollback_directory)

    try:
        next_curated_directory.replace(curated_directory)
    except Exception:
        if rollback_directory.exists():
            rollback_directory.replace(curated_directory)
        raise
    else:
        if rollback_directory.exists():
            shutil.rmtree(rollback_directory)

    return True


def run_local_pipeline(
    source_date: date,
    user_agent: str,
    state_directory: Path,
    run_id: str | None = None,
) -> int:
    """Run one SEC source date and safely promote successful curated state."""
    state_directory.mkdir(parents=True, exist_ok=True)

    curated_directory = state_directory / "curated"
    next_curated_directory = state_directory / "next_curated"
    ledger_path = state_directory / "run_ledger.jsonl"

    if next_curated_directory.exists():
        shutil.rmtree(next_curated_directory)

    existing_records = read_partitioned_parquet(curated_directory)

    with create_sec_client(user_agent) as client:
        result = run_pipeline(
            source_dates=(source_date,),
            client=client,
            existing_records=existing_records,
            output_directory=next_curated_directory,
            ledger_path=ledger_path,
            run_id=run_id or str(uuid.uuid4()),
        )

    promoted = False
    if result.run_record.status == "succeeded":
        promoted = promote_curated_state(
            next_curated_directory,
            curated_directory,
        )
    elif next_curated_directory.exists():
        shutil.rmtree(next_curated_directory)

    print(f"Run ID: {result.run_record.run_id}")
    print(f"Status: {result.run_record.status}")
    print(f"Raw rows: {result.run_record.raw_row_count}")
    print(f"Validated rows: {result.run_record.validated_row_count}")
    print(f"Quarantined rows: {result.run_record.quarantined_row_count}")
    print(f"Target filings: {result.run_record.target_filing_count}")
    print(f"Inserted: {result.run_record.inserted_count}")
    print(f"Updated: {result.run_record.updated_count}")
    print(f"Unchanged: {result.run_record.unchanged_count}")
    print(f"Curated state promoted: {promoted}")

    if result.run_record.error_message:
        print(f"Error: {result.run_record.error_message}")

    return 0 if result.run_record.status == "succeeded" else 1


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser."""
    parser = argparse.ArgumentParser(
        description="Run the EDGAR Filing Monitor for one SEC daily index date."
    )
    parser.add_argument(
        "--source-date",
        required=True,
        type=parse_source_date,
        help="SEC daily-index date in YYYY-MM-DD format.",
    )
    parser.add_argument(
        "--state-dir",
        type=Path,
        default=Path("data/state"),
        help="Ignored local directory for Parquet state and the run ledger.",
    )
    return parser


def main() -> int:
    """Run the command-line application."""
    parser = build_parser()
    arguments = parser.parse_args()

    user_agent = os.getenv("SEC_USER_AGENT", "").strip()
    if not user_agent:
        parser.error(
            "SEC_USER_AGENT is required. Set it to an identifying value with "
            "your contact email before running the pipeline."
        )

    return run_local_pipeline(
        source_date=arguments.source_date,
        user_agent=user_agent,
        state_directory=arguments.state_dir,
    )


if __name__ == "__main__":
    sys.exit(main())